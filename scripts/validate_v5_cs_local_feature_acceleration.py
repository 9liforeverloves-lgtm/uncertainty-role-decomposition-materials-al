"""Validate the exact V5 local-feature acceleration before broad execution.

The production adapter retains the frozen V5 candidate-specific optimizer.  It
only replaces its deterministic per-candidate local-feature helper while the
optimizer is executing.  This script compares unmodified and accelerated V5
scale vectors bit-for-bit at the initial acquisition round for every task,
split, model, and both historical candidate-specific configurations.

It is a development-engineering validation only.  It uses frozen historical
seed 5000 and neither reads nor writes confirmation seeds 7000--7039.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.production_strategies import (
    _candidate_config,
    _candidate_specific_scale_with_exact_v5_local_features,
)


SEED = 5000
TASKS = (
    "matbench_expt_gap",
    "matbench_mp_gap",
    "matbench_log_gvrh",
    "matbench_log_kvrh",
)
SPLITS = ("iid_record", "chemical_system_ood")
MODELS = ("random_forest", "extra_randomized_bagging")
CS_CONFIGURATIONS = (
    ("HISTORICAL_CS", "cs_da_oob_hist", False),
    ("SELECTED_CS", "cs_da_oob_parsimonious_f1", True),
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _surrogate_seed(seed: int, round_index: int, model: str) -> int:
    code = 11 if model == "random_forest" else 17
    return int(np.random.SeedSequence([seed, round_index, code]).generate_state(1)[0])


def _initial_round_case(
    adapter: CanonicalV5Adapter,
    *,
    task: str,
    split_protocol: str,
    model_name: str,
    label: str,
    v5_strategy: str,
    selected: bool,
) -> dict[str, object]:
    frame, X, split, canonical = adapter.v5_run_config(
        task, split_protocol, SEED, v5_strategy, model=model_name
    )
    y = frame.target.to_numpy(float)
    stable = np.arange(len(frame), dtype=np.int64)
    initial = np.sort(
        np.random.default_rng(SEED).choice(
            split.source, size=int(canonical["campaign"]["initial_count"]), replace=False
        )
    ).astype(int)
    fitted_seed = _surrogate_seed(SEED, 0, model_name)
    surrogate = adapter.modules["surrogates"].make_surrogate(
        model_name,
        n_estimators=int(canonical["model"]["n_estimators"]),
        min_samples_leaf=int(canonical["model"]["min_samples_leaf"]),
        n_jobs=1,
    )
    model = surrogate.fit(X[initial], y[initial], fitted_seed, stable[initial])
    candidates = np.array(
        sorted(set(map(int, split.target)) - set(map(int, initial))), dtype=int
    )
    candidate_mean, candidate_sigma = model.predict_mean_std(X[candidates])
    oob_mean, oob_sigma, oob_counts = model.oob_or_crossfit_predict_mean_std()
    config = _candidate_config(adapter, selected)
    v5 = adapter.modules["strategies"]
    original_helper = v5._local_features
    arguments = (
        model,
        oob_mean,
        oob_sigma,
        oob_counts,
        y[initial],
        X[candidates],
        candidate_mean,
        candidate_sigma,
        fitted_seed,
        config,
        float(canonical["oob"]["uncertainty_floor"]),
    )
    started = time.perf_counter()
    baseline_scale, baseline_status = v5.candidate_specific_scale(*arguments)
    baseline_seconds = time.perf_counter() - started
    started = time.perf_counter()
    accelerated_scale, accelerated_status = _candidate_specific_scale_with_exact_v5_local_features(
        v5, *arguments
    )
    accelerated_seconds = time.perf_counter() - started
    scale_exact = bool(np.array_equal(baseline_scale, accelerated_scale))
    status_exact = bool(baseline_status == accelerated_status)
    helper_restored = bool(v5._local_features is original_helper)
    maximum_absolute_difference = float(
        np.max(np.abs(np.asarray(baseline_scale) - np.asarray(accelerated_scale)))
    )
    return {
        "task": task,
        "split": split_protocol,
        "model": model_name,
        "strategy": label,
        "historical_v5_strategy": v5_strategy,
        "seed": SEED,
        "initial_labeled_count": int(len(initial)),
        "candidate_count": int(len(candidates)),
        "baseline_status": str(baseline_status),
        "accelerated_status": str(accelerated_status),
        "status_exact": status_exact,
        "scale_exact": scale_exact,
        "maximum_absolute_scale_difference": maximum_absolute_difference,
        "v5_helper_restored": helper_restored,
        "baseline_seconds": baseline_seconds,
        "accelerated_seconds": accelerated_seconds,
        "speedup": baseline_seconds / accelerated_seconds if accelerated_seconds > 0 else np.nan,
        "passed": bool(scale_exact and status_exact and helper_restored),
    }


def main() -> None:
    if SEED >= 7000:
        raise RuntimeError("local-feature validation must never use a confirmation seed")
    adapter = CanonicalV5Adapter(ROOT)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    authority = adapter.validate_v5_authority_locks()
    if not authority["passed"]:
        raise RuntimeError("V5 authority locks failed before local-feature validation")

    rows: list[dict[str, object]] = []
    for task in TASKS:
        for split_protocol in SPLITS:
            for model_name in MODELS:
                for label, v5_strategy, selected in CS_CONFIGURATIONS:
                    row = _initial_round_case(
                        adapter,
                        task=task,
                        split_protocol=split_protocol,
                        model_name=model_name,
                        label=label,
                        v5_strategy=v5_strategy,
                        selected=selected,
                    )
                    rows.append(row)
                    print(
                        f"{task}/{split_protocol}/{model_name}/{label}: "
                        f"passed={row['passed']} speedup={float(row['speedup']):.3f}"
                    )

    table = pd.DataFrame(rows).sort_values(
        ["task", "split", "model", "strategy"], kind="stable"
    ).reset_index(drop=True)
    table_path = ROOT / "tables" / "v6_v5_cs_local_feature_acceleration_validation.csv"
    table_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_table = table_path.with_suffix(table_path.suffix + ".tmp")
    table.to_csv(temporary_table, index=False, float_format="%.17g", lineterminator="\n")
    os.replace(temporary_table, table_path)
    table_hash = _sha256_file(table_path)
    passed = int(table["passed"].sum())
    summary = {
        "schema_version": "v6-v5-cs-local-feature-exact-acceleration-validation-v1",
        "status": "PASS" if passed == len(table) == 32 else "FAIL",
        "purpose": (
            "Validate bitwise equivalence of the frozen V5 candidate-specific scale output "
            "before using the deterministic local-feature acceleration in V6 development."
        ),
        "confirmation_seed_range_not_read_or_run": [7000, 7039],
        "historical_seed": SEED,
        "coverage": {
            "tasks": list(TASKS),
            "splits": list(SPLITS),
            "models": list(MODELS),
            "candidate_specific_configurations": [item[0] for item in CS_CONFIGURATIONS],
            "expected_cases": 32,
            "passed_cases": passed,
            "failed_cases": len(table) - passed,
        },
        "strict_criteria": [
            "np.array_equal on every candidate scale",
            "identical V5 fit status",
            "temporary V5 helper restoration",
        ],
        "median_speedup": float(table["speedup"].median()),
        "table": table_path.relative_to(ROOT).as_posix(),
        "table_sha256": table_hash,
        "v5_authority": authority,
    }
    result_path = ROOT / "results" / "v6_v5_strategy_replay_audit" / "cs_local_feature_acceleration_validation.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_result = result_path.with_suffix(result_path.suffix + ".tmp")
    temporary_result.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary_result, result_path)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
