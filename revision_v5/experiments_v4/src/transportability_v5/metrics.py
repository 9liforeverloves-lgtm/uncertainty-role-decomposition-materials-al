from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def stable_topk(y, pool, stable_ids, fraction):
    pool=np.asarray(pool,int); y=np.asarray(y,float); ids=np.asarray(stable_ids)
    k=max(1, int(np.ceil(len(pool)*fraction)))
    order=np.lexsort((ids[pool], -y[pool]))
    return pool[order[:k]]


def recall(y, queried, pool, stable_ids, fraction=.01):
    reference=set(map(int, stable_topk(y,pool,stable_ids,fraction)))
    return len(reference & set(map(int,queried))) / len(reference)


def target_set_size(pool, fraction):
    return max(1,int(np.ceil(len(np.asarray(pool))*float(fraction))))


def normalized_auc(x, values):
    x=np.asarray(x,float); values=np.asarray(values,float)
    order=np.argsort(x,kind="stable"); x=x[order]; values=values[order]
    if len(x)<2 or x[-1] <= x[0]: return float("nan")
    return float(np.trapezoid(values,x)/(x[-1]-x[0]))


def simple_regret(y, queried, pool):
    return float(np.max(np.asarray(y)[pool])-np.max(np.asarray(y)[list(queried)]))


def normalized_simple_regret(y,queried,pool):
    values=np.asarray(y,float); pool=np.asarray(pool,int)
    scale=float(np.max(values[pool])-np.min(values[pool]))
    if scale<=0: return 0.0
    return simple_regret(values,queried,pool)/scale


def enrichment_factor(y,queried,pool,stable_ids,fraction=.01):
    pool=np.asarray(pool,int); queried=set(map(int,queried))
    if not queried: return float("nan")
    target=set(map(int,stable_topk(y,pool,stable_ids,fraction)))
    selected_rate=len(queried&target)/len(queried)
    pool_rate=len(target)/len(pool)
    return float(selected_rate/pool_rate)


def best_so_far(y,queried):
    return float(np.max(np.asarray(y,float)[list(queried)]))


def budget_to_recall(queried_counts,recalls,threshold):
    for count,value in zip(queried_counts,recalls):
        if value>=threshold: return int(count)
    return None


def batch_utility(y, alternative, baseline, pool, stable_ids):
    tops={q:set(map(int,stable_topk(y,pool,stable_ids,q))) for q in (.005,.01,.02,.05)}
    a=set(map(int,alternative)); b=set(map(int,baseline)); n=max(1,len(a|b))
    result={"batch_replacement_fraction":1-len(a&b)/n,
            "raw_selected_fraction_replaced":1-len(a&b)/max(1,len(b))}
    for label,q in (("top0p5",.005),("top1",.01),("top2",.02),("top5",.05)):
        target=tops[q]
        result[f"immediate_{label}_recall_increment"]=(len(a&target)-len(b&target))/max(1,len(target))
        result[f"{label}_precision_gain"]=len(a&target)/max(1,len(a))-len(b&target)/max(1,len(b))
        result[f"{label}_target_set_size"]=len(target)
    return result


def transfer_regret(oracle_value, selected_value): return float(oracle_value-selected_value)
def selection_optimism(development_value, heldout_value): return float(development_value-heldout_value)


def failure_label(l1, l2, l3, l4, material_threshold=.10):
    if l1 and l2 < material_threshold: return "statistical-to-decision break"
    if l2 >= material_threshold and not l3: return "decision-to-immediate-utility break"
    if l3 and not l4: return "immediate-to-sequential-value break"
    return "break not uniquely localized"
