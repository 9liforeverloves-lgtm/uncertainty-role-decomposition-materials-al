from __future__ import annotations

import itertools

import numpy as np


def paired_effect(alternative,baseline):
    alternative=np.asarray(alternative,float); baseline=np.asarray(baseline,float)
    valid=np.isfinite(alternative)&np.isfinite(baseline)
    difference=alternative[valid]-baseline[valid]
    if not len(difference): raise ValueError("no valid paired observations")
    return difference


def paired_percentile_bootstrap(alternative,baseline,n_boot=20000,seed=51001):
    difference=paired_effect(alternative,baseline)
    rng=np.random.default_rng(seed)
    indices=rng.integers(0,len(difference),size=(int(n_boot),len(difference)))
    draws=difference[indices].mean(axis=1)
    return {
        "effect":float(difference.mean()),
        "ci_low":float(np.quantile(draws,.025)),
        "ci_high":float(np.quantile(draws,.975)),
        "valid_pairs":int(len(difference)),
        "bootstrap_seed":int(seed),
        "bootstrap_draws":int(n_boot),
    }


def paired_sign_flip_test(alternative,baseline,seed=51002,monte_carlo_draws=200000):
    difference=paired_effect(alternative,baseline)
    observed=abs(float(difference.mean()))
    n=len(difference)
    if n<=20:
        signs=np.asarray(list(itertools.product((-1.0,1.0),repeat=n)),float)
        null=np.abs((signs*difference).mean(axis=1))
        p=float(np.mean(null>=observed-1e-15))
        mode="exact"
        draws=len(null)
    else:
        rng=np.random.default_rng(seed)
        signs=rng.choice((-1.0,1.0),size=(int(monte_carlo_draws),n))
        null=np.abs((signs*difference).mean(axis=1))
        p=float((1+np.sum(null>=observed-1e-15))/(len(null)+1))
        mode="monte_carlo"
        draws=len(null)
    return {"p_value":p,"mode":mode,"draws":int(draws),"permutation_seed":int(seed),"valid_pairs":n}


def benjamini_hochberg(p_values):
    p=np.asarray(p_values,float)
    if p.ndim!=1 or not np.isfinite(p).all() or np.any((p<0)|(p>1)):
        raise ValueError("p-values must be a finite one-dimensional vector in [0,1]")
    order=np.argsort(p,kind="stable"); ranked=p[order]; n=len(p)
    adjusted=np.minimum.accumulate((ranked*n/np.arange(1,n+1))[::-1])[::-1]
    output=np.empty(n,float); output[order]=np.minimum(1,adjusted)
    return output


def assert_unique_inference_rows(frame,key_columns):
    duplicate=frame.duplicated(list(key_columns),keep=False)
    if duplicate.any():
        raise ValueError(f"duplicate inference rows: {int(duplicate.sum())}")

