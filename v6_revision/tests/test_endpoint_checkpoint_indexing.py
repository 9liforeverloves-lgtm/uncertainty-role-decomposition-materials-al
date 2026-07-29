import pandas as pd
import pytest

from transportability_v6.production_endpoints import campaign_mace


def test_campaign_mace_uses_exact_nonnegative_checkpoint_rows():
    frame = pd.DataFrame({"mean_absolute_coverage_error": [0.1, 0.2, 0.3, 0.4]})
    rows = {"initial": 0, "25pct": 1, "50pct": 2, "75pct": 3}
    assert campaign_mace(frame, rows) == pytest.approx(0.25)


def test_campaign_mace_rejects_legacy_negative_initial_alias():
    frame = pd.DataFrame({"mean_absolute_coverage_error": [0.1, 0.2, 0.3, 0.4]})
    rows = {"initial": -1, "25pct": 1, "50pct": 2, "75pct": 3}
    with pytest.raises(ValueError, match="checkpoint round is invalid for initial"):
        campaign_mace(frame, rows)
