"""V6 evidence pipeline. V5-RC1 is imported read-only and never rewritten."""

from .strategies import STRATEGIES, StrategySpec, score_round

__all__ = ["STRATEGIES", "StrategySpec", "score_round"]
