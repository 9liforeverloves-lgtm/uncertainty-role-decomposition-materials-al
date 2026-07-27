from __future__ import annotations

import numpy as np

from transportability_v5.strategies import choose


def test_equal_scores_use_ascending_stable_candidate_id() -> None:
    scores = np.array([1.0, 1.0, 1.0, 0.5])
    stable_ids = np.array([8, 2, 5, 1])
    positions = choose(scores, stable_ids, 3)
    assert stable_ids[positions].tolist() == [2, 5, 8]
