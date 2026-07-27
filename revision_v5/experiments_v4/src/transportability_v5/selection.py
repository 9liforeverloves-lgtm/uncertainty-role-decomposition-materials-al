from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr,kendalltau


COMPLEXITY=("ucb_beta_0p5","ucb_beta_1p0","ucb_beta_2p0","gaussian_global_ucb","candidate_specific_da_oob")


def select_policy(development: pd.DataFrame, heldout_task: str, tolerance=.005):
    used=development.loc[development.task!=heldout_task].copy()
    if heldout_task in set(used.task): raise AssertionError("held-out task leaked into selection")
    summary=used.groupby("strategy").primary_nauc.agg(["mean","min"]).reset_index()
    best=summary["mean"].max(); eligible=summary[summary["mean"]>=best-tolerance]
    worst=eligible["min"].max(); eligible=eligible[eligible["min"]>=worst-1e-15]
    rank={x:i for i,x in enumerate(COMPLEXITY)}
    selected=min(eligible.strategy,key=lambda x:rank.get(x,999))
    return selected,summary


def rank_stability(development_values,heldout_values):
    shared=sorted(set(development_values)&set(heldout_values)); a=np.array([development_values[x] for x in shared]); b=np.array([heldout_values[x] for x in shared])
    return {"spearman":float(spearmanr(a,b).statistic),"kendall":float(kendalltau(a,b).statistic),
            "top1_agreement":max(shared,key=development_values.get)==max(shared,key=heldout_values.get),
            "top2_overlap":len(set(sorted(shared,key=development_values.get,reverse=True)[:2])&set(sorted(shared,key=heldout_values.get,reverse=True)[:2]))/2}
