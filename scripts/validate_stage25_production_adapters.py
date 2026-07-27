"""Read-only validation of actual V5-backed V6 production strategy adapters."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

import joblib
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transportability_v6.canonical_adapter import CanonicalV5Adapter
from transportability_v6.production_strategies import (
    PRODUCTION_STRATEGIES,
    fit_and_apply_production_scale,
)


def main() -> None:
    adapter = CanonicalV5Adapter(ROOT)
    adapter.assert_source_lock()
    adapter.validate_pymatgen()
    frame, X, split, config = adapter.v5_run_config(
        "matbench_expt_gap", "iid_record", 5000, "raw_ucb_beta_1"
    )
    checkpoint = adapter.paths.v5_reference_trajectory / "checkpoint_initial.joblib"
    model = joblib.load(checkpoint)
    target = np.asarray(split.target, int)[:64]
    diagnostic = np.asarray(split.diagnostic, int)[:32]
    target_mean, target_sigma = model.predict_mean_std(X[target])
    diagnostic_mean, diagnostic_sigma = model.predict_mean_std(X[diagnostic])
    floor = float(config["oob"]["uncertainty_floor"])
    strategy_ids = (
        "ORIGINAL_GG",
        "SELECTED_GG",
        "HISTORICAL_CS",
        "SELECTED_CS",
        "SCALAR_TEMPERATURE_NLL",
        "SCALAR_TEMPERATURE_RESIDUAL_RATIO",
        "POWER_SCALING",
        "ISOTONIC_ABS_RESIDUAL",
        "CONFORMAL_INTERVAL_ONLY",
        "CONFORMAL_GAUSSIAN_EQUIVALENT",
        "SELECTED_CS_EQUIVALENT_DOF_CONTROL",
        "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL",
        "IDENTITY_CONTROL",
    )
    checked: dict[str, object] = {}
    for index, strategy_id in enumerate(strategy_ids):
        application = fit_and_apply_production_scale(
            PRODUCTION_STRATEGIES[strategy_id],
            adapter=adapter,
            model=model,
            X_query=X[target],
            query_mean=target_mean,
            query_raw_sigma=target_sigma,
            X_diagnostic=X[diagnostic],
            diagnostic_mean=diagnostic_mean,
            diagnostic_raw_sigma=diagnostic_sigma,
            seed=int(np.random.SeedSequence([91000, index]).generate_state(1)[0]),
            floor=floor,
        )
        if not np.isfinite(application.query_sigma).all() or np.any(application.query_sigma <= 0):
            raise RuntimeError(f"{strategy_id}: invalid query sigma")
        if application.diagnostic_sigma is None or not np.isfinite(application.diagnostic_sigma).all():
            raise RuntimeError(f"{strategy_id}: invalid diagnostic sigma")
        if strategy_id == "CONFORMAL_INTERVAL_ONLY":
            if application.diagnostic_interval_half_widths is None:
                raise RuntimeError("conformal strategy omitted coverage-specific intervals")
            if set(application.diagnostic_interval_half_widths) != {0.50, 0.80, 0.90, 0.95}:
                raise RuntimeError("conformal strategy omitted a registered coverage")
        checked[strategy_id] = {
            "status": application.status,
            "query_count": len(application.query_sigma),
            "diagnostic_count": len(application.diagnostic_sigma),
            "query_scale_min": float(np.min(application.query_scale_factor)),
            "query_scale_max": float(np.max(application.query_scale_factor)),
            "fit_metadata": application.fit_metadata,
        }
    print(
        json.dumps(
            {
                "schema_version": "v6-stage25-production-adapter-validation-v1",
                "read_only_v5_job": "matbench_expt_gap__iid_record__random_forest__raw_ucb_beta_1__seed5000",
                "strategies_checked": checked,
                "passed": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
