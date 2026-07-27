"""Compatibility exports for Stage-2 smoke-only data helpers.

Production V6 code must use :mod:`transportability_v6.canonical_adapter`.
"""

from .smoke_only.data import formula_features, load_materials_csv, synthetic_materials

__all__ = ["formula_features", "load_materials_csv", "synthetic_materials"]
