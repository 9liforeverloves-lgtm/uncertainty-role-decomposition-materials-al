"""Compatibility export for a smoke-only RF implementation.

Production V6 code uses the frozen V5 surrogate factories through the
canonical adapter.
"""

from .smoke_only.surrogates import RandomForestEnsemble

__all__ = ["RandomForestEnsemble"]
