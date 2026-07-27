"""Small RF ensemble reserved for smoke tests; production uses V5 adapters."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble._forest import _generate_sample_indices, _get_n_samples_bootstrap

from . import require_smoke_context


class RandomForestEnsemble:
    def __init__(
        self,
        n_estimators: int = 24,
        min_samples_leaf: int = 2,
        *,
        evidence_class: str | None = None,
    ):
        require_smoke_context(evidence_class)
        self.n_estimators = int(n_estimators)
        self.min_samples_leaf = int(min_samples_leaf)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        seed: int,
        stable_ids: np.ndarray,
    ) -> "RandomForestEnsemble":
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        stable_ids = np.asarray(stable_ids)
        order = np.argsort(stable_ids, kind="stable")
        self.X_train_ = X[order]
        self.y_train_ = y[order]
        self.stable_ids_ = stable_ids[order]
        self.model_ = RandomForestRegressor(
            n_estimators=self.n_estimators,
            min_samples_leaf=self.min_samples_leaf,
            bootstrap=True,
            random_state=int(seed),
            max_features=1.0,
            n_jobs=1,
        )
        self.model_.fit(self.X_train_, self.y_train_)
        return self

    def predict_mean_std(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, float)
        predictions = np.column_stack([tree.predict(X) for tree in self.model_.estimators_])
        return predictions.mean(axis=1), predictions.std(axis=1, ddof=0)

    def oob_mean_std(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n = len(self.y_train_)
        sample_count = _get_n_samples_bootstrap(n, self.model_.max_samples)
        values: list[list[float]] = [[] for _ in range(n)]
        for tree in self.model_.estimators_:
            sampled = _generate_sample_indices(tree.random_state, n, sample_count)
            oob = np.setdiff1d(np.arange(n), np.unique(sampled), assume_unique=False)
            predictions = tree.predict(self.X_train_[oob])
            for index, prediction in zip(oob, predictions):
                values[int(index)].append(float(prediction))
        mean = np.full(n, np.nan)
        sigma = np.full(n, np.nan)
        count = np.zeros(n, dtype=int)
        for index, row in enumerate(values):
            if row:
                mean[index] = float(np.mean(row))
                sigma[index] = float(np.std(row, ddof=0))
                count[index] = len(row)
        return mean, sigma, count

