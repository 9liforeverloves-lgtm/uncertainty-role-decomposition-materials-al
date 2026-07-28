"""Regenerate the accepted sentinel DRAFT map solely from compact tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in os.sys.path:
    os.sys.path.insert(0, str(SRC))

from transportability_v6.selection import fit_matched_beta_map


TABLES = ROOT / "tables"
ARCHIVE = ROOT / "analysis_plan" / "v6_selection_map_SENTINEL_DRAFT.json"


def canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def write_once(path: Path, payload: dict[str, Any], *, refresh: bool = False) -> None:
    content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            if not refresh:
                raise FileExistsError(f"refusing to overwrite divergent regeneration artifact: {path}")
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(content)
            os.replace(temporary, path)
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def balanced_simple(frame: pd.DataFrame) -> tuple[str, dict[str, float], dict[str, int]]:
    scores = {
        str(strategy): float(group.groupby("environment", sort=True)["l1_campaign_mace"].median().median())
        for strategy, group in frame.groupby("strategy", sort=True)
    }
    winner = min(scores, key=lambda key: (scores[key], key))
    wins: dict[str, int] = {}
    for seed in sorted(set(frame.seed.astype(int))):
        leave_one = frame.loc[frame.seed.astype(int) != seed]
        leave_scores = {
            str(strategy): float(group.groupby("environment", sort=True)["l1_campaign_mace"].median().median())
            for strategy, group in leave_one.groupby("strategy", sort=True)
        }
        chosen = min(leave_scores, key=lambda key: (leave_scores[key], key))
        wins[chosen] = wins.get(chosen, 0) + 1
    return winner, scores, wins


def main(*, refresh: bool = False) -> None:
    beta = pd.read_csv(TABLES / "v6_p0_sentinel_round_effective_beta.csv")
    simple = pd.read_csv(TABLES / "v6_p0_sentinel_simple_scaler_inputs.csv")
    summary = pd.read_csv(TABLES / "v6_p0_sentinel_selection_summary.csv")
    metadata_row = summary.loc[(summary.record_type == "metadata") & (summary.name == "draft_payload_metadata")]
    if len(metadata_row) != 1:
        raise ValueError("selection-summary compact table lacks unique DRAFT metadata")
    metadata = json.loads(str(metadata_row.iloc[0].value_json))
    required_beta = {"source_row_order", "budget_fraction_hex", "effective_beta_hex"}
    required_simple = {"source_row_order", "l1_campaign_mace_hex"}
    if not required_beta <= set(beta.columns):
        raise ValueError(f"round-effective-beta compact table lacks lossless fields: {sorted(required_beta - set(beta.columns))}")
    if not required_simple <= set(simple.columns):
        raise ValueError(f"simple-scaler compact table lacks lossless fields: {sorted(required_simple - set(simple.columns))}")
    # Decode the exact IEEE-754 values and restore the collector's original row
    # order.  Decimal CSV parsing is intentionally not used for the reductions.
    beta_exact = beta.sort_values("source_row_order", kind="stable").loc[:, ["environment", "seed", "budget_fraction_hex", "effective_beta_hex"]].copy()
    beta_exact["budget_fraction"] = beta_exact["budget_fraction_hex"].map(lambda value: float.fromhex(str(value)))
    beta_exact["effective_beta"] = beta_exact["effective_beta_hex"].map(lambda value: float.fromhex(str(value)))
    simple_exact = simple.sort_values("source_row_order", kind="stable").loc[:, ["environment", "seed", "strategy", "l1_campaign_mace_hex"]].copy()
    simple_exact["l1_campaign_mace"] = simple_exact["l1_campaign_mace_hex"].map(lambda value: float.fromhex(str(value)))
    selection = fit_matched_beta_map(beta_exact[["environment", "budget_fraction", "effective_beta", "seed"]])
    winner, scores, wins = balanced_simple(simple_exact)
    payload: dict[str, Any] = {
        **metadata,
        "selection": selection,
        "simple_scaling_development_summary": {
            "criterion": "minimum environment-balanced median L1 MACE; development only",
            "selected_strategy_draft": winner,
            "environment_balanced_median_l1": scores,
        },
    }
    payload["draft_selection_map_sha256"] = canonical_hash(payload)
    archived = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    expected_row = summary.loc[(summary.record_type == "expected") & (summary.name == "selection_values")]
    if len(expected_row) != 1:
        raise ValueError("selection-summary compact table lacks expected selection values")
    expected = json.loads(str(expected_row.iloc[0].value_json))
    checks = {
        "semantic_payload_equal": payload == archived,
        "draft_hash_equal": payload["draft_selection_map_sha256"] == archived["draft_selection_map_sha256"],
        "fixed_beta_equal": float(selection["fixed_matched_beta"]) == float(expected["fixed_matched_beta"]),
        "stage_betas_equal": selection["stage_matched_beta"] == expected["stage_matched_beta"],
        "simple_scores_equal": scores == expected["simple_scaling_environment_balanced_median_l1"],
        "loo_winner_counts_equal": wins == expected["simple_scaling_leave_one_seed_out_winner_count"],
        "observed_descriptive_minimum_equal": winner == expected["simple_scaling_observed_descriptive_minimum"],
    }
    regenerated = TABLES / "v6_p0_sentinel_selection_map_regenerated.json"
    write_once(regenerated, payload, refresh=refresh)
    audit = {
        "schema_version": "v6-p0-sentinel-selection-regeneration-audit-v1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "fixed_matched_beta": selection["fixed_matched_beta"],
        "stage_matched_beta": selection["stage_matched_beta"],
        "simple_scaler_l1": scores,
        "leave_one_seed_out_winner_count": wins,
        "regenerated_path": regenerated.relative_to(ROOT).as_posix(),
        "archived_sentinel_path": ARCHIVE.relative_to(ROOT).as_posix(),
    }
    write_once(TABLES / "v6_p0_sentinel_selection_regeneration_audit.json", audit, refresh=refresh)
    if audit["status"] != "PASS":
        raise SystemExit(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="replace only prior generated regeneration artifacts")
    main(refresh=parser.parse_args().refresh)
