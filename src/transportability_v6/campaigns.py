"""Compatibility exports for the explicitly smoke-only campaign runner.

Production campaigns live in :mod:`transportability_v6.production_campaign`.
"""

from .smoke_only import SMOKE_LABEL
from .smoke_only.campaigns import CampaignConfig, run_campaign

__all__ = ["CampaignConfig", "SMOKE_LABEL", "run_campaign"]
