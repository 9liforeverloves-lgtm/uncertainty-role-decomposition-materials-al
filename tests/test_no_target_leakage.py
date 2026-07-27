from __future__ import annotations

import numpy as np
import pytest

from transportability_v5.splits import SplitResult


def test_split_validation_rejects_role_overlap() -> None:
    split = SplitResult(
        source=np.array([0, 1]),
        target=np.array([1, 2]),
        diagnostic=np.array([3]),
        group_by_index=("a", "b", "c", "d"),
        protocol="iid_record",
        seed=1,
    )
    with pytest.raises(ValueError, match="overlap"):
        split.validate(4, 1, 1, 1)


def test_chemical_system_split_rejects_group_leakage() -> None:
    split = SplitResult(
        source=np.array([0]),
        target=np.array([1]),
        diagnostic=np.array([2]),
        group_by_index=("shared", "shared", "other"),
        protocol="chemical_system_ood",
        seed=1,
    )
    with pytest.raises(ValueError, match="group leakage"):
        split.validate(3, 1, 1, 1)
