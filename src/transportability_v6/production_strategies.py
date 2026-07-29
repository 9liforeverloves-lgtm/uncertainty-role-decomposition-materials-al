"""Production V6 strategy adapters built on canonical V5 algorithms."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
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
        _spec("SELECTED_GG", min_oob=8, bounds=None, evaluation="raw_gaussian_sigma", objective="V5 Gaussian-global selected-beta acquisition with raw diagnostic sigma"),
        _spec("GG_CALIBRATION_ONLY", min_oob=8, bounds=None, acquisition="raw_sigma", objective="V5 Gaussian-global calibration; exact RAW acquisition"),
        _spec("GG_ACQUISITION_ONLY", min_oob=8, bounds=None, evaluation="raw_gaussian_sigma", objective="V5 Gaussian-global acquisition; raw evaluation"),
        _spec("HISTORICAL_CS", min_oob=3, bounds=(0.25, 4.0), evaluation="raw_gaussian_sigma", parameters=7, objective="V5 six-feature pairwise candidate-specific ranking; raw diagnostic sigma"),
        _spec("SELECTED_CS", min_oob=10, bounds=(0.25, 4.0), parameters=2, objective="V5 parsimonious F1 pairwise candidate-specific ranking; candidate-scaled joint evaluation"),
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


# Frozen V5 GG/CS trajectories passed ``y[queried]`` to their OOB fitting
# functions after the surrogate had sorted training records by stable ID.  The
# ordering is therefore part of the historical strategy identity, even though
# it is not a statistically desirable residual pairing.  Preserve it only for
# named V5-derived strategies; new scalar and conformal methods use aligned
# OOB targets.
V5_LEGACY_OOB_ORDER_STRATEGIES = frozenset(
    {
        "ORIGINAL_GG",
        "SELECTED_GG",
        "GG_CALIBRATION_ONLY",
        "GG_ACQUISITION_ONLY",
        "HISTORICAL_CS",
        "SELECTED_CS",
        "CS_CALIBRATION_ONLY",
        "CS_ACQUISITION_ONLY",
    }
)


# The frozen V5 implementation performs an independent stable sort of the
# same valid OOB ratios for every candidate.  Candidate-specific calibration
# can therefore become dominated by repeated sorting rather than its frozen
# V5 objective.  The helper below preserves V5's arithmetic and calls its
# optimizer unchanged; it only reuses the one globally stable ordering that
# V5 would obtain after masking each candidate's nonzero leaf-proximity rows.
#
# The V5 strategy module is process-global, so installing the temporary helper
# is protected by a re-entrant lock and restored in ``finally``.  Every use is
# validated against the unmodified V5 path before a production campaign is
# permitted to rely on it (see the dedicated validation script).
_V5_LOCAL_FEATURE_PATCH_LOCK = RLock()
_V5_LOCAL_FEATURE_BLOCK_SIZE = 128


def _make_exact_v5_local_feature_accelerator(v5: Any):
    """Return a byte-for-byte arithmetic equivalent of V5 ``_local_features``.

    It retains V5's descriptor-distance and rank transforms.  For a fixed
    ``ratios``/``valid`` pair, a stable global ratio order is equivalent to
    V5's per-candidate stable sort because each candidate mask only removes
    rows.  The sums, cumulative sums, and weighted average are still evaluated
    in precisely that V5 sorted order.
    """

    reference_cache: dict[tuple[int, int, int, int], tuple[np.ndarray, np.ndarray]] = {}

    def accelerated_local_features(
        model: Any,
        Xref: np.ndarray,
        ratios: np.ndarray,
        valid: np.ndarray,
        Xq: np.ndarray,
        raw_std: np.ndarray,
        mean: np.ndarray,
        training: bool = False,
    ) -> np.ndarray:
        key = (id(model), id(Xref), id(ratios), id(valid))
        cached = reference_cache.get(key)
        if cached is None:
            reference_leaf = np.asarray(model.leaf_or_local_representation(Xref))
            ratios_array = np.asarray(ratios, float)
            valid_array = np.asarray(valid, bool)
            stable_valid_rows = np.flatnonzero(valid_array)
            # ``kind='stable'`` retains V5's original-row tie resolution.
            stable_valid_rows = stable_valid_rows[
                np.argsort(ratios_array[stable_valid_rows], kind="stable")
            ]
            cached = (reference_leaf, stable_valid_rows)
            reference_cache[key] = cached
        reference_leaf, stable_valid_rows = cached
        ratios_array = np.asarray(ratios, float)
        query_leaf = np.asarray(model.leaf_or_local_representation(Xq))

        local = np.ones(len(Xq))
        dispersion = np.zeros(len(Xq))
        density = np.zeros(len(Xq))
        for start in range(0, len(Xq), _V5_LOCAL_FEATURE_BLOCK_SIZE):
            stop = min(start + _V5_LOCAL_FEATURE_BLOCK_SIZE, len(Xq))
            # This evaluates exactly V5's ``mean(ref_leaf == q_leaf[row])``
            # for each row, while moving the independent rows into one NumPy
            # operation.  The per-row scalar reductions below retain V5's
            # original arithmetic sequence.
            proximity_block = np.mean(
                reference_leaf[None, :, :] == query_leaf[start:stop, None, :], axis=2
            )
            for offset, proximity in enumerate(proximity_block):
                row = start + offset
                rows = stable_valid_rows[proximity[stable_valid_rows] > 0]
                # V5 removes the matching row only for training features.
                if training and row < len(proximity):
                    rows = rows[rows != row]
                if len(rows):
                    weights = proximity[rows] ** 2
                    values = ratios_array[rows]
                    local[row] = values[np.searchsorted(np.cumsum(weights), 0.5 * weights.sum())]
                    dispersion[row] = np.average(np.abs(values - local[row]), weights=weights)
                    density[row] = weights.sum()
        knn = v5._descriptor_distance(Xref, Xq, training=training)
        percentile = v5.rankdata(mean, method="average") / max(1, len(mean))
        return np.column_stack(
            [
                np.log(np.maximum(raw_std, 1e-12)),
                np.log1p(density),
                np.log1p(knn),
                percentile,
                np.log(np.maximum(local, 1e-12)),
                np.log1p(dispersion),
            ]
        )

    return accelerated_local_features


@contextmanager
def _exact_v5_local_feature_acceleration(v5: Any):
    """Temporarily accelerate only V5's deterministic local-feature helper."""

    with _V5_LOCAL_FEATURE_PATCH_LOCK:
        original = v5._local_features
        v5._local_features = _make_exact_v5_local_feature_accelerator(v5)
        try:
            yield
        finally:
            v5._local_features = original


@contextmanager
def _exact_v5_selected_f1_feature_path(v5: Any):
    """Skip unused V5 local features when the frozen registry selects F1 only.

    V5 selects columns only after constructing all six features.  For the
    prospectively registered ``feature_indices=[0]`` strategy, column zero is
    exactly ``log(max(raw_std, 1e-12))``.  Finite placeholders in unselected
    columns preserve V5's finite-row guard and leave its optimizer unchanged.
    """

    def selected_f1_features(
        model: Any,
        Xref: np.ndarray,
        ratios: np.ndarray,
        valid: np.ndarray,
        Xq: np.ndarray,
        raw_std: np.ndarray,
        mean: np.ndarray,
        training: bool = False,
    ) -> np.ndarray:
        first = np.log(np.maximum(np.asarray(raw_std, float), 1e-12))
        return np.column_stack([first, np.zeros((len(first), 5), dtype=float)])

    with _V5_LOCAL_FEATURE_PATCH_LOCK:
        original = v5._local_features
        v5._local_features = selected_f1_features
        try:
            yield
        finally:
            v5._local_features = original


def _candidate_specific_scale_with_exact_v5_local_features(
    v5: Any,
    model: Any,
    oob_mean: np.ndarray,
    oob_sigma: np.ndarray,
    counts: np.ndarray,
    oob_targets: np.ndarray,
    X_query: np.ndarray,
    query_mean: np.ndarray,
    query_raw_sigma: np.ndarray,
    seed: int,
    config: dict[str, Any],
    floor: float,
) -> tuple[np.ndarray, str]:
    """Run the frozen V5 CS optimizer with its exact accelerated helper."""

    context = (
        _exact_v5_selected_f1_feature_path(v5)
        if tuple(config.get("feature_indices", ())) == (0,)
        else _exact_v5_local_feature_acceleration(v5)
    )
    with context:
        scale, status = v5.candidate_specific_scale(
            model,
            oob_mean,
            oob_sigma,
            counts,
            oob_targets,
            X_query,
            query_mean,
            query_raw_sigma,
            int(seed),
            config,
            floor,
        )
    return np.asarray(scale, float), str(status)


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


def _valid_oob(
    model: Any,
    floor: float,
    min_count: int,
    *,
    target_values: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
    target = model.y_train_ if target_values is None else np.asarray(target_values, float)
    if target.shape != model.y_train_.shape or not np.isfinite(target).all():
        raise ValueError("OOB target values must be finite and match the trained-record count")
    residual = target[valid] - mean[valid]
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
    oob_target_values: np.ndarray | None = None,
) -> AppliedProductionScale:
    """Fit only on model OOB records and map to query/diagnostic predictions."""

    _, query_effective, _ = validate_sigma(query_raw_sigma, floor=floor, name="query raw sigma")
    if X_diagnostic is not None:
        if diagnostic_raw_sigma is None or diagnostic_mean is None:
            raise ValueError("diagnostic mean and sigma must be supplied together")
        _, diagnostic_effective, _ = validate_sigma(diagnostic_raw_sigma, floor=floor, name="diagnostic raw sigma")
    else:
        diagnostic_effective = None
    legacy_order = spec.id in V5_LEGACY_OOB_ORDER_STRATEGIES
    if legacy_order and oob_target_values is None:
        raise ValueError("V5-derived strategy requires the ordered queried targets used for OOB fitting")
    oob_targets = np.asarray(oob_target_values, float) if legacy_order else model.y_train_
    oob_mean, oob_sigma, counts, valid, residual = _valid_oob(
        model,
        floor,
        spec.min_oob,
        target_values=oob_targets,
    )
    valid_sigma = np.maximum(oob_sigma[valid], floor)
    metadata: dict[str, Any] = {
        "valid_oob_count": int(valid.sum()),
        "min_oob_trees": int(spec.min_oob),
        "oob_residual_target_order": "v5_queried_order" if legacy_order else "aligned_model_training_order",
    }

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
            oob_targets,
            counts,
            spec.min_oob,
            floor,
        )
        scalar_scale = float(scalar_scale)
        scale = _ensure_positive(np.full(len(query_effective), scalar_scale), "global scale")
        if diagnostic_effective is None:
            diagnostic_scale = None
        elif spec.evaluation_mapping == "raw_gaussian_sigma":
            # The frozen selected-beta GG label is absent from V5's
            # diagnostic-scaling allowlist: it scales acquisition, while its
            # retained diagnostic metric is evaluated on raw effective sigma.
            diagnostic_scale = np.ones(len(diagnostic_effective))
        else:
            diagnostic_scale = _ensure_positive(
                np.full(len(diagnostic_effective), scalar_scale), "global diagnostic scale"
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
        query_scale, status = _candidate_specific_scale_with_exact_v5_local_features(
            v5,
            model,
            oob_mean,
            oob_sigma,
            counts,
            oob_targets,
            X_query,
            query_mean,
            query_raw_sigma,
            int(seed),
            config,
            floor,
        )
        query_scale = _ensure_positive(query_scale, "candidate-specific query scale")
        diagnostic_scale = None
        if diagnostic_effective is not None and spec.evaluation_mapping == "raw_gaussian_sigma":
            # Acquisition-only and historical controls retain raw checkpoint
            # evaluation.  Prospectively registered SELECTED_CS is joint and
            # therefore follows the scaled diagnostic branch below.
            diagnostic_scale = np.ones(len(diagnostic_effective))
        elif diagnostic_effective is not None:
            diagnostic_scale, diagnostic_status = _candidate_specific_scale_with_exact_v5_local_features(
                v5,
                model,
                oob_mean,
                oob_sigma,
                counts,
                oob_targets,
                X_diagnostic,
                diagnostic_mean,
                diagnostic_raw_sigma,
                int(seed),
                config,
                floor,
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
            fit_metadata={
                **metadata,
                "candidate_specific_config": config,
                "local_feature_implementation": "v5_exact_stable_order_leaf_proximity_v1",
            },
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
