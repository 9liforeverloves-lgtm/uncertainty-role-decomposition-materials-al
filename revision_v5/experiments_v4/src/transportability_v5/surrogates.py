from __future__ import annotations

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor, BaggingRegressor
from sklearn.tree import ExtraTreeRegressor


class EnsembleSurrogate:
    name = "base"

    def fit(self, X, y, seed: int, stable_ids=None):
        X = np.asarray(X, float); y = np.asarray(y, float)
        order = np.arange(len(y)) if stable_ids is None else np.argsort(np.asarray(stable_ids), kind="stable")
        self.X_train_ = X[order]; self.y_train_ = y[order]
        self.stable_ids_ = np.arange(len(y))[order] if stable_ids is None else np.asarray(stable_ids)[order]
        self.seed_ = int(seed); self.model = self._make(seed); self.model.fit(self.X_train_, self.y_train_)
        return self

    def predict_ensemble(self, X):
        X = np.asarray(X, float)
        return np.column_stack([tree.predict(X) for tree in self.model.estimators_])

    def predict_mean_std(self, X):
        p = self.predict_ensemble(X)
        return p.mean(1), p.std(1, ddof=0)

    def leaf_or_local_representation(self, X):
        X = np.asarray(X, float)
        return np.column_stack([tree.apply(X) for tree in self.model.estimators_])

    def oob_or_crossfit_predict_mean_std(self):
        n = len(self.y_train_); predictions = [[] for _ in range(n)]
        samples = self._estimator_samples()
        for tree, sampled in zip(self.model.estimators_, samples):
            unsampled = np.setdiff1d(np.arange(n), np.unique(sampled), assume_unique=False)
            if len(unsampled):
                values = tree.predict(self.X_train_[unsampled])
                for idx, value in zip(unsampled, values): predictions[int(idx)].append(float(value))
        mean = np.full(n, np.nan); std = np.full(n, np.nan); count = np.zeros(n, int)
        for i, values in enumerate(predictions):
            if values:
                mean[i] = np.mean(values); std[i] = np.std(values); count[i] = len(values)
        return mean, std, count

    def save_state(self, path): joblib.dump(self, path)
    @classmethod
    def load_state(cls, path): return joblib.load(path)


class RandomForestSurrogate(EnsembleSurrogate):
    name = "random_forest"
    def __init__(self, n_estimators=80, min_samples_leaf=2, n_jobs=1):
        self.n_estimators=n_estimators; self.min_samples_leaf=min_samples_leaf; self.n_jobs=n_jobs
    def _make(self, seed):
        return RandomForestRegressor(n_estimators=self.n_estimators, min_samples_leaf=self.min_samples_leaf,
            bootstrap=True, random_state=seed, n_jobs=self.n_jobs, max_features=1.0)
    def _estimator_samples(self):
        from sklearn.ensemble._forest import _generate_sample_indices, _get_n_samples_bootstrap
        n=len(self.y_train_); m=_get_n_samples_bootstrap(n, self.model.max_samples)
        return [_generate_sample_indices(t.random_state, n, m) for t in self.model.estimators_]


class ExtraRandomizedBaggingSurrogate(EnsembleSurrogate):
    name = "extra_randomized_bagging"
    def __init__(self, n_estimators=80, min_samples_leaf=2, n_jobs=1):
        self.n_estimators=n_estimators; self.min_samples_leaf=min_samples_leaf; self.n_jobs=n_jobs
    def _make(self, seed):
        tree=ExtraTreeRegressor(splitter="random", max_features=1.0, min_samples_leaf=self.min_samples_leaf)
        kwargs=dict(n_estimators=self.n_estimators, bootstrap=True, random_state=seed, n_jobs=self.n_jobs)
        try: return BaggingRegressor(estimator=tree, **kwargs)
        except TypeError: return BaggingRegressor(base_estimator=tree, **kwargs)
    def _estimator_samples(self): return list(self.model.estimators_samples_)


def make_surrogate(name, **kwargs):
    if name == "random_forest": return RandomForestSurrogate(**kwargs)
    if name == "extra_randomized_bagging": return ExtraRandomizedBaggingSurrogate(**kwargs)
    raise KeyError(name)
