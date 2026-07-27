"""Production V6 strategy adapters built on canonical V5 algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .calibration import (
    ConformalGaussianEquivalent,
    ConformalIntervalOnly,
    IdentityScale,
    fit_conformal_gaussian_equivalent,
    fit_conformal_interval_only,
    fit_historical_cs_equivalent_dof,
    fit_isotonic_abs_residual,
    fit_power_nll,
    fit_scalar_nll,
    fit_scalar_residual_ratio,
    fit_selected_cs_equivalent_dof,
    validate_sigma,
)
from .canonical_adapter import CanonicalV5Adapter


@dataclass(frozen=True)
class ProductionStrategySpec:
    id: str
    fitting_data: str
    min_oob: int
    fallback: str
    scale_bounds: tuple[float, float] | None
    acquisition_mapping: str
    evaluation_mapping: str
    nominal_parameter_count: int
    objective: str
    evidence_class: str = "V6-MECH"
    conformal_reference_coverage: float | None = None


def _spec(
    identifier: str,
    *,
    fitting_data: str = "OOB residual and raw sigma from currently labelled records only",
    min_oob: int = 10,
    fallback: str = "identity_raw_sigma",
    bounds: tuple[float, float] | None = (0.25, 4.0),
    acquisition: str = "scaled_sigma",
    evaluation: str = "scaled_gaussian_sigma",
    parameters: int = 1,
    objective: str = "calibration",
    coverage: float | None = None,
) -> ProductionStrategySpec:
    return ProductionStrategySpec(
        identifier,
        fitting_data,
        min_oob,
        fallback,
        bounds,
        acquisition,
        evaluation,
        parameters,
        objective,
        conformal_reference_coverage=coverage,
    )


PRODUCTION_STRATEGIES = {
    spec.id: spec
    for spec in (
        _spec("RAW", fitting_data="none", min_oob=0, fallback="none", bounds=None, acquisition="raw_sigma", evaluation="raw_gaussian_sigma", parameters=0, objective="identity"),
        _spec("IDENTITY_CONTROL", bounds=None, acquisition="raw_sigma", evaluation="raw_gaussian_sigma", parameters=0, objective="identity_control"),
        _spec("RAW_FIXED_BETA_MATCHED", fitting_data="development-only Original GG effective-beta summaries", min_oob=0, fallback="block_if_selection_map_missing", bounds=None, acquisition="raw_sigma", evaluation="raw_gaussian_sigma", parameters=0, objective="fixed development-matched beta"),
        _spec("RAW_STAGE_BETA_MATCHED", fitting_data="development-only Original GG effective-beta summaries by frozen budget stage", min_oob=0, fallback="block_if_selection_map_missing", bounds=None, acquisition="raw_sigma", evaluation="raw_gaussian_sigma", parameters=0, objective="stagewise development-matched beta"),
        _spec("ORIGINAL_GG", min_oob=8, bounds=None, objective="V5 Gaussian-consistent median residual-ratio"),
        _spec("SELECTED_GG", min_oob=8, bounds=None, objective="V5 Gaussian-global scaler with development-selected beta"),
        _spec("GG_CALIBRATION_ONLY", min_oob=8, bounds=None, acquisition="raw_sigma", objective="V5 Gaussian-global calibration; exact RAW acquisition"),
        _spec("GG_ACQUISITION_ONLY", min_oob=8, bounds=None, evaluation="raw_gaussian_sigma", objective="V5 Gaussian-global acquisition; raw evaluation"),
        _spec("HISTORICAL_CS", min_oob=3, bounds=(0.25, 4.0), parameters=7, objective="V5 six-feature pairwise candidate-specific ranking"),
        _spec("SELECTED_CS", min_oob=10, bounds=(0.25, 4.0), parameters=2, objective="V5 parsimonious F1 pairwise candidate-specific ranking"),
        _spec("CS_CALIBRATION_ONLY", min_oob=10, bounds=(0.25, 4.0), acquisition="raw_sigma", parameters=2, objective="V5 selected CS calibration; exact RAW acquisition"),
        _spec("CS_ACQUISITION_ONLY", min_oob=10, bounds=(0.25, 4.0), evaluation="raw_gaussian_sigma", parameters=2, objective="V5 selected CS acquisition; raw evaluation"),
        _spec("SCALAR_TEMPERATURE_NLL", min_oob=3, bounds=(0.05, 20.0), acquisition="raw_sigma", parameters=1, objective="Gaussian OOB NLL; calibration-only simple scaler"),
        _spec("SCALAR_TEMPERATURE_RESIDUAL_RATIO", min_oob=3, bounds=(0.05, 20.0), acquisition="raw_sigma", parameters=1, objective="OOB median absolute residual ratio; calibration-only simple scaler"),
        _spec("POWER_SCALING", min_oob=3, bounds=(0.25, 2.0), acquisition="raw_sigma", parameters=2, objective="bounded Gaussian OOB NLL; calibration-only simple scaler"),
        _spec("ISOTONIC_ABS_RESIDUAL", min_oob=3, bounds=None, acquisition="raw_sigma", parameters=0, objective="monotone OOB absolute-residual regression; calibration-only simple scaler"),
        _spec("CONFORMAL_INTERVAL_ONLY", min_oob=3, bounds=None, acquisition="raw_sigma", evaluation="coverage_specific_interval", parameters=0, objective="finite-sample OOB residual-ratio quantile", coverage=0.90),
        _spec("CONFORMAL_GAUSSIAN_EQUIVALENT", min_oob=3, bounds=None, acquisition="raw_sigma", evaluation="coverage_specific_gaussian_equivalent", parameters=0, objective="named finite-sample conformal-to-Gaussian conversion", coverage=0.90),
        _spec("SELECTED_CS_EQUIVALENT_DOF_CONTROL", min_oob=20, bounds=(0.25, 4.0), acquisition="raw_sigma", parameters=2, objective="OOB ridge intercept plus log raw sigma; calibration-only control"),
        _spec("HISTORICAL_CS_EQUIVALENT_DOF_CONTROL", min_oob=20, bounds=(0.25, 4.0), acquisition="raw_sigma", parameters=7, objective="OOB ridge intercept plus six V5 local features; calibration-only control"),
    )
}


@dataclass
class AppliedProductionScale:
    spec: ProductionStrategySpec
    status: str
    query_sigma: np.ndarray
    diagnostic_sigma: np.ndarray | None
    query_scale_factor: np.ndarray
    diagnostic_scale_factor: np.ndarray | None
    query_interval_half_width: np.ndarray | None = None
    diagnostic_interval_half_width: np.ndarray | None = None
    query_interval_half_widths: dict[float, np.ndarray] | None = None
    diagnostic_interval_half_widths: dict[float, np.ndarray] | None = None
    fit_metadata: dict[str, Any] | None = None


def _valid_oob(model: Any, floor: float, min_count: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean, sigma, count = model.oob_or_crossfit_predict_mean_std()
    mean = np.asarray(mean, float)
    sigma = np.asarray(sigma, float)
    count = np.asarray(count, int)
    # Unavailable OOB values are excluded by a documented count gate.  Any
    # finite non-positive/negative value is validated by the calibration API.
    valid = np.isfinite(mean) & np.isfinite(sigma) & (count >= int(min_count))
    if np.any(sigma[np.isfinite(sigma)] < 0):
        raise ValueError("canonical OOB sigma contains a negative value")
    effective = np.full_like(sigma, np.nan)
    effective[valid] = np.maximum(sigma[valid], floor)
    residual = model.y_train_[valid] - mean[valid]
    return mean, sigma, count, valid, residual


def _ensure_positive(values: np.ndarray, name: str) -> np.ndarray:
    values = np.asarray(values, float)
    if not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError(f"{name} must be finite and positive")
    return values


def _candidate_config(adapter: CanonicalV5Adapter, selected: bool) -> dict[str, Any]:
    config = dict(adapter.protocol()["candidate_specific"])
    if selected:
        config.update(
            {
                "min_oob_trees_per_sample": 10,
                "feature_indices": [0],
                "top_q_pair_weight": 1.0,
                "objective": "pairwise_ranking",
            }
        )
    else:
        config.update({"min_oob_trees_per_sample": 3, "feature_indices": list(range(6))})
    return config


def _historical_features(adapter: CanonicalV5Adapter, model: Any, oob_mean: np.ndarray, oob_sigma: np.ndarray, count: np.ndarray, floor: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    v5 = adapter.modules["strategies"]
    effective, _ = v5.apply_uncertainty_floor(oob_sigma, floor, allow_nan=True)
    ratios = np.abs(model.y_train_ - oob_mean) / effective
    valid = np.isfinite(ratios) & np.isfinite(oob_mean) & np.isfinite(oob_sigma) & (count >= 3)
    features = v5._local_features(
        model,
        model.X_train_,
        ratios,
        valid.copy(),
        model.X_train_,
        oob_sigma,
        oob_mean,
        training=True,
    )
    valid &= np.isfinite(features).all(axis=1)
    return model.y_train_[valid] - oob_mean[valid], np.maximum(oob_sigma[valid], floor), features[valid]


def fit_and_apply_production_scale(
    spec: ProductionStrategySpec,
    *,
    adapter: CanonicalV5Adapter,
    model: Any,
    X_query: np.ndarray,
    query_mean: np.ndarray,
    query_raw_sigma: np.ndarray,
    X_diagnostic: np.ndarray | None = None,
    diagnostic_mean: np.ndarray | None = None,
    diagnostic_raw_sigma: np.ndarray | None = None,
    seed: int,
    floor: float = 1e-8,
) -> AppliedProductionScale:
    """Fit only on model OOB records and map to query/diagnostic predictions."""

    _, query_effective, _ = validate_sigma(query_raw_sigma, floor=floor, name="query raw sigma")
    if X_diagnostic is not None:
        if diagnostic_raw_sigma is None or diagnostic_mean is None:
            raise ValueError("diagnostic mean and sigma must be supplied together")
        _, diagnostic_effective, _ = validate_sigma(diagnostic_raw_sigma, floor=floor, name="diagnostic raw sigma")
    else:
        diagnostic_effective = None
    oob_mean, oob_sigma, counts, valid, residual = _valid_oob(model, floor, spec.min_oob)
    valid_sigma = np.maximum(oob_sigma[valid], floor)
    metadata: dict[str, Any] = {"valid_oob_count": int(valid.sum()), "min_oob_trees": int(spec.min_oob)}

    def identity(status: str) -> AppliedProductionScale:
        return AppliedProductionScale(
            spec,
            status,
            query_effective,
            diagnostic_effective,
            np.ones(len(query_effective)),
            None if diagnostic_effective is None else np.ones(len(diagnostic_effective)),
            fit_metadata=metadata,
        )

    if spec.id in {"RAW", "IDENTITY_CONTROL", "RAW_FIXED_BETA_MATCHED", "RAW_STAGE_BETA_MATCHED"}:
        return identity("identity")
    if len(residual) < spec.min_oob:
        return identity("identity_insufficient_oob")

    if spec.id in {"ORIGINAL_GG", "SELECTED_GG", "GG_CALIBRATION_ONLY", "GG_ACQUISITION_ONLY"}:
        scalar_scale, status = adapter.modules["strategies"].gaussian_global_scale(
            oob_mean,
            oob_sigma,
            model.y_train_,
            counts,
            spec.min_oob,
            floor,
        )
        scalar_scale = float(scalar_scale)
        scale = _ensure_positive(np.full(len(query_effective), scalar_scale), "global scale")
        diagnostic_scale = (
            None
            if diagnostic_effective is None
            else _ensure_positive(
                np.full(len(diagnostic_effective), scalar_scale), "global diagnostic scale"
            )
        )
        return AppliedProductionScale(
            spec,
            str(status),
            query_effective * scale,
            None if diagnostic_effective is None else diagnostic_effective * diagnostic_scale,
            scale,
            diagnostic_scale,
            fit_metadata={**metadata, "global_scale": float(scale[0])},
        )

    if spec.id in {"HISTORICAL_CS", "SELECTED_CS", "CS_CALIBRATION_ONLY", "CS_ACQUISITION_ONLY"}:
        selected = spec.id in {"SELECTED_CS", "CS_CALIBRATION_ONLY", "CS_ACQUISITION_ONLY"}
        config = _candidate_config(adapter, selected)
        v5 = adapter.modules["strategies"]
        query_scale, status = v5.candidate_specific_scale(
            model, oob_mean, oob_sigma, counts, model.y_train_, X_query, query_mean, query_raw_sigma,
            int(seed), config, floor,
        )
        query_scale = _ensure_positive(query_scale, "candidate-specific query scale")
        diagnostic_scale = None
        if diagnostic_effective is not None:
            diagnostic_scale, diagnostic_status = v5.candidate_specific_scale(
                model, oob_mean, oob_sigma, counts, model.y_train_, X_diagnostic, diagnostic_mean, diagnostic_raw_sigma,
                int(seed), config, floor,
            )
            diagnostic_scale = _ensure_positive(diagnostic_scale, "candidate-specific diagnostic scale")
            if diagnostic_status != status:
                status = f"{status}|diagnostic:{diagnostic_status}"
        return AppliedProductionScale(
            spec,
            str(status),
            query_effective * query_scale,
            None if diagnostic_effective is None else diagnostic_effective * diagnostic_scale,
            query_scale,
            diagnostic_scale,
            fit_metadata={**metadata, "candidate_specific_config": config},
        )

    if spec.id == "SCALAR_TEMPERATURE_NLL":
        fit = fit_scalar_nll(residual, valid_sigma, floor=floor)
    elif spec.id == "SCALAR_TEMPERATURE_RESIDUAL_RATIO":
        fit = fit_scalar_residual_ratio(residual, valid_sigma, floor=floor)
    elif spec.id == "POWER_SCALING":
        fit = fit_power_nll(residual, valid_sigma, floor=floor)
    elif spec.id == "ISOTONIC_ABS_RESIDUAL":
        fit = fit_isotonic_abs_residual(residual, valid_sigma, floor=floor)
    elif spec.id == "SELECTED_CS_EQUIVALENT_DOF_CONTROL":
        fit = fit_selected_cs_equivalent_dof(residual, valid_sigma, floor=floor, min_samples=spec.min_oob)
    elif spec.id == "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL":
        residual_hist, sigma_hist, features_hist = _historical_features(adapter, model, oob_mean, oob_sigma, counts, floor)
        if len(residual_hist) < spec.min_oob:
            return identity("identity_insufficient_oob")
        fit = fit_historical_cs_equivalent_dof(residual_hist, sigma_hist, features_hist, floor=floor, min_samples=spec.min_oob)
        query_features = _historical_candidate_features(adapter, model, oob_mean, oob_sigma, counts, X_query, query_raw_sigma, query_mean, floor)
        diagnostic_features = None if diagnostic_effective is None else _historical_candidate_features(adapter, model, oob_mean, oob_sigma, counts, X_diagnostic, diagnostic_raw_sigma, diagnostic_mean, floor)
        query_sigma = fit.transform(query_raw_sigma, query_features, floor=floor)
        diagnostic_sigma = None if diagnostic_effective is None else fit.transform(diagnostic_raw_sigma, diagnostic_features, floor=floor)
        return AppliedProductionScale(
            spec,
            "fit_success" if not getattr(fit, "used_fallback", False) else "identity_insufficient_oob",
            query_sigma,
            diagnostic_sigma,
            query_sigma / query_effective,
            None if diagnostic_sigma is None else diagnostic_sigma / diagnostic_effective,
            fit_metadata={**metadata, "effective_degrees_of_freedom": getattr(fit, "effective_degrees_of_freedom", 0.0)},
        )
    elif spec.id == "CONFORMAL_INTERVAL_ONLY":
        fits = {
            coverage: fit_conformal_interval_only(
                residual, valid_sigma, nominal_coverage=coverage, floor=floor
            )
            for coverage in (0.50, 0.80, 0.90, 0.95)
        }
        query_widths = {
            coverage: fit.half_width(query_raw_sigma, floor=floor) for coverage, fit in fits.items()
        }
        diagnostic_widths = (
            None
            if diagnostic_effective is None
            else {
                coverage: fit.half_width(diagnostic_raw_sigma, floor=floor)
                for coverage, fit in fits.items()
            }
        )
        reference = float(spec.conformal_reference_coverage or 0.90)
        return AppliedProductionScale(
            spec,
            "fit_success",
            query_effective,
            diagnostic_effective,
            np.ones(len(query_effective)),
            None if diagnostic_effective is None else np.ones(len(diagnostic_effective)),
            query_widths[reference],
            None if diagnostic_widths is None else diagnostic_widths[reference],
            query_interval_half_widths=query_widths,
            diagnostic_interval_half_widths=diagnostic_widths,
            fit_metadata={
                **metadata,
                "conformal_reference_coverage": reference,
                "conformal_quantiles": {
                    str(coverage): fit.residual_ratio_quantile for coverage, fit in fits.items()
                },
            },
        )
    elif spec.id == "CONFORMAL_GAUSSIAN_EQUIVALENT":
        fit = fit_conformal_gaussian_equivalent(residual, valid_sigma, reference_coverage=float(spec.conformal_reference_coverage), floor=floor)
    else:  # pragma: no cover - defensive exhaustiveness
        raise KeyError(spec.id)

    if spec.id == "HISTORICAL_CS_EQUIVALENT_DOF_CONTROL":  # handled above
        raise AssertionError("unreachable")
    if spec.id == "SELECTED_CS_EQUIVALENT_DOF_CONTROL":
        query_sigma = fit.transform(query_raw_sigma, floor=floor)
        diagnostic_sigma = None if diagnostic_effective is None else fit.transform(diagnostic_raw_sigma, floor=floor)
    else:
        query_sigma = fit.transform(query_raw_sigma, floor=floor)
        diagnostic_sigma = None if diagnostic_effective is None else fit.transform(diagnostic_raw_sigma, floor=floor)
    query_sigma = _ensure_positive(query_sigma, "scaled query sigma")
    if diagnostic_sigma is not None:
        diagnostic_sigma = _ensure_positive(diagnostic_sigma, "scaled diagnostic sigma")
    return AppliedProductionScale(
        spec,
        "fit_success" if getattr(fit, "converged", True) else "identity_optimizer_failure",
        query_sigma,
        diagnostic_sigma,
        query_sigma / query_effective,
        None if diagnostic_sigma is None else diagnostic_sigma / diagnostic_effective,
        fit_metadata={**metadata, "fit_method": getattr(fit, "method", spec.id)},
    )


def _historical_candidate_features(
    adapter: CanonicalV5Adapter,
    model: Any,
    oob_mean: np.ndarray,
    oob_sigma: np.ndarray,
    count: np.ndarray,
    X: np.ndarray,
    sigma: np.ndarray,
    mean: np.ndarray,
    floor: float,
) -> np.ndarray:
    v5 = adapter.modules["strategies"]
    effective, _ = v5.apply_uncertainty_floor(oob_sigma, floor, allow_nan=True)
    ratios = np.abs(model.y_train_ - oob_mean) / effective
    valid = np.isfinite(ratios) & np.isfinite(oob_mean) & np.isfinite(oob_sigma) & (count >= 3)
    features = v5._local_features(model, model.X_train_, ratios, valid, X, sigma, mean, training=False)
    if not np.isfinite(features).all():
        raise ValueError("canonical historical candidate features are non-finite")
    return features


def score_production_round(
    spec: ProductionStrategySpec,
    application: AppliedProductionScale,
    mean: np.ndarray,
    stable_ids: np.ndarray,
    *,
    beta: float,
    adapter: CanonicalV5Adapter,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply canonical V5 stable tie-breaking to a registered acquisition map."""

    mean = np.asarray(mean, float)
    stable_ids = np.asarray(stable_ids)
    if not np.isfinite(mean).all() or len(np.unique(stable_ids)) != len(stable_ids):
        raise ValueError("production score inputs are invalid")
    if not np.isfinite(beta) or beta < 0:
        raise ValueError("production beta must be finite and nonnegative")
    if spec.acquisition_mapping == "raw_sigma":
        sigma = application.query_sigma / application.query_scale_factor
        scores = mean + float(beta) * sigma
    elif spec.acquisition_mapping == "scaled_sigma":
        scores = mean + float(beta) * application.query_sigma
    else:  # pragma: no cover - registry guards this
        raise ValueError(f"strategy {spec.id} has no legal production acquisition mapping")
    if not np.isfinite(scores).all():
        raise ValueError("production acquisition scores are non-finite")
    order = adapter.modules["strategies"].stable_order(scores, stable_ids)
    return scores, np.asarray(order, int)
