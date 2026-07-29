"""Pure validation helpers for V6 P0 confirmation freeze readiness."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math
from typing import Any


PRIMARY_ENDPOINTS = frozenset({"L1", "L4"})


def endpoint_support(endpoint_declaration: str) -> frozenset[str]:
    """Expand a strategy endpoint declaration into supported primary endpoints."""

    normalized = str(endpoint_declaration).strip()
    if normalized in {"L1_and_L4", "L1_L4_joint"}:
        return PRIMARY_ENDPOINTS
    if normalized in PRIMARY_ENDPOINTS:
        return frozenset({normalized})
    return frozenset()


def canonical_strategy_id(
    strategy_id: str,
    aliases: Mapping[str, str] | None = None,
) -> str:
    """Resolve one registered alias and reject alias cycles."""

    aliases = aliases or {}
    current = str(strategy_id)
    visited: set[str] = set()
    while current in aliases:
        if current in visited:
            raise ValueError(f"strategy alias cycle contains {current}")
        visited.add(current)
        current = str(aliases[current])
    return current


def _comparison_strategy_id(contrast: Mapping[str, Any]) -> str:
    explicit = contrast.get("strategy_id")
    if explicit:
        return str(explicit)
    comparison = str(contrast.get("comparison", "")).strip()
    if " vs " not in comparison:
        raise ValueError(f"contrast {contrast.get('id', '<unknown>')} lacks a strategy_id")
    return comparison.split(" vs ", 1)[0].removesuffix(" joint").strip()


def validate_contrast_endpoint_consistency(
    contrasts: Iterable[Mapping[str, Any]],
    strategy_registry: Iterable[Mapping[str, Any]],
    aliases: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    """Validate that both sides of every inferential contrast support its endpoint.

    Descriptive joint summaries (for example ``L1_L4_joint``) are deliberately
    outside this primary-endpoint validator.
    """

    registry = {str(item["id"]): dict(item) for item in strategy_registry}
    alias_map = dict(aliases or {})
    validated: list[dict[str, str]] = []
    for contrast in contrasts:
        endpoint = str(contrast.get("endpoint", ""))
        if endpoint not in PRIMARY_ENDPOINTS:
            continue
        contrast_id = str(contrast.get("id", "<unknown>"))
        test_id = canonical_strategy_id(_comparison_strategy_id(contrast), alias_map)
        baseline_id = canonical_strategy_id(str(contrast.get("baseline", "")), alias_map)
        if baseline_id not in registry:
            raise ValueError(
                f"{contrast_id}: baseline {baseline_id!r} is absent from the strategy registry"
            )
        if test_id not in registry:
            raise ValueError(
                f"{contrast_id}: strategy {test_id!r} is absent from the strategy registry"
            )
        for side, strategy_id in (("strategy", test_id), ("baseline", baseline_id)):
            supported = endpoint_support(str(registry[strategy_id].get("endpoint", "")))
            if endpoint not in supported:
                raise ValueError(
                    f"{contrast_id}: {side} {strategy_id!r} does not support {endpoint}"
                )
        validated.append(
            {
                "contrast_id": contrast_id,
                "endpoint": endpoint,
                "strategy_id": test_id,
                "baseline_id": baseline_id,
            }
        )
    return validated


def validate_alias_registry(
    aliases: Mapping[str, str],
    canonical_strategy_ids: Iterable[str],
) -> None:
    """Require disjoint aliases, valid canonical targets, and no chains/cycles."""

    canonical = {str(value) for value in canonical_strategy_ids}
    alias_ids = {str(value) for value in aliases}
    overlap = canonical & alias_ids
    if overlap:
        raise ValueError(f"aliases also appear as canonical strategies: {sorted(overlap)}")
    for alias, target in aliases.items():
        if str(target) not in canonical:
            raise ValueError(f"alias {alias!r} has non-canonical target {target!r}")
        if str(target) in alias_ids:
            raise ValueError(f"alias {alias!r} points to another alias")


def effective_beta(nominal_beta: float, fitted_scale: float) -> float:
    """Return the registered acquisition coefficient after scale fitting."""

    nominal = float(nominal_beta)
    scale = float(fitted_scale)
    if not math.isfinite(nominal) or nominal < 0:
        raise ValueError("nominal beta must be finite and nonnegative")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("fitted scale must be finite and positive")
    return nominal * scale


def validate_gg_policy_identity(
    strategy_registry: Iterable[Mapping[str, Any]],
) -> None:
    """Require the two frozen V5 GG policies to remain distinct and correctly named."""

    registry = {str(item["id"]): dict(item) for item in strategy_registry}
    required = {"ORIGINAL_GG": 1.0, "SELECTED_GG": 0.5}
    for strategy_id, expected_beta in required.items():
        if strategy_id not in registry:
            raise ValueError(f"missing canonical GG policy {strategy_id}")
        observed = float(registry[strategy_id].get("nominal_beta", float("nan")))
        if observed != expected_beta:
            raise ValueError(
                f"{strategy_id} nominal beta is {observed!r}, expected {expected_beta}"
            )
    if registry["ORIGINAL_GG"] == registry["SELECTED_GG"]:
        raise ValueError("ORIGINAL_GG and SELECTED_GG must be distinct policy records")
    selected_provenance = registry["SELECTED_GG"].get("policy_provenance")
    if not isinstance(selected_provenance, Mapping):
        raise ValueError("SELECTED_GG lacks exact policy provenance")
    if str(selected_provenance.get("v5_strategy_id")) != "gg_ucb_beta_0p5":
        raise ValueError("SELECTED_GG provenance does not identify gg_ucb_beta_0p5")


def validate_manifest_policy_identity(
    rows: Iterable[Mapping[str, Any]],
    strategy_registry: Iterable[Mapping[str, Any]],
) -> None:
    """Reject manifest rows whose policy ID, beta, or provenance was substituted."""

    registry = {str(item["id"]): dict(item) for item in strategy_registry}
    for row in rows:
        strategy_id = str(row.get("strategy_id", row.get("strategy", "")))
        if strategy_id not in registry:
            raise ValueError(f"manifest strategy {strategy_id!r} is not canonical")
        policy = registry[strategy_id]
        expected_beta = float(policy["nominal_beta"])
        observed_beta = float(row.get("nominal_beta", float("nan")))
        if observed_beta != expected_beta:
            raise ValueError(
                f"manifest {strategy_id} nominal beta {observed_beta!r} "
                f"does not match policy {expected_beta}"
            )
        expected_key = str(policy.get("policy_key", strategy_id))
        observed_key = str(row.get("policy_key", ""))
        if observed_key != expected_key:
            raise ValueError(
                f"manifest {strategy_id} policy key {observed_key!r} "
                f"does not match {expected_key!r}"
            )


def validate_analysis_only_contrasts(
    contrasts: Iterable[Mapping[str, Any]],
) -> None:
    """Ensure descriptive analyses cannot be projected into confirmation jobs."""

    for contrast in contrasts:
        if not bool(contrast.get("analysis_only", False)):
            continue
        contrast_id = str(contrast.get("id", "<unknown>"))
        if bool(contrast.get("generate_confirmation_job", True)):
            raise ValueError(f"{contrast_id}: analysis-only contrast generates a job")
        if contrast.get("strategy_id") not in (None, ""):
            raise ValueError(f"{contrast_id}: analysis-only contrast has a singular strategy")
        if contrast.get("baseline") not in (None, ""):
            raise ValueError(f"{contrast_id}: analysis-only contrast has a singular baseline")
        if str(contrast.get("family")) != "NONE_DESCRIPTIVE":
            raise ValueError(f"{contrast_id}: analysis-only contrast has an inferential family")
        if contrast.get("binary_claim") is not False:
            raise ValueError(f"{contrast_id}: analysis-only contrast has a binary claim")
        method_contrasts = contrast.get("method_contrasts")
        if not isinstance(method_contrasts, list) or not method_contrasts:
            raise ValueError(f"{contrast_id}: analysis-only contrast lacks method contrasts")
