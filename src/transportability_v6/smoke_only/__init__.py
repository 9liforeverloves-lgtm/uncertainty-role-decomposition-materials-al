"""Simplified components reserved for non-inferential engineering smoke checks."""

from __future__ import annotations


SMOKE_LABEL = "NON-INFERENTIAL ENGINEERING VALIDATION"
PRODUCTION_EVIDENCE_CLASSES = frozenset({"V6-MECH", "V6-EXT", "V6-SENS", "V6-REP"})


class SmokeOnlyComponentError(RuntimeError):
    """A reduced smoke component was requested by a scientific production run."""


def require_smoke_context(evidence_class: str | None) -> None:
    if evidence_class in PRODUCTION_EVIDENCE_CLASSES:
        raise SmokeOnlyComponentError(
            f"smoke-only implementation is prohibited for production evidence class {evidence_class}"
        )

