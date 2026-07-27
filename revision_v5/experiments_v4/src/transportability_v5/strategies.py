from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata
from sklearn.linear_model import Ridge
from sklearn.neighbors import NearestNeighbors


BETA_GRID=(0.0,.25,.5,1.0,2.0,4.0)
LOCAL_FEATURE_NAMES=(
    "log_raw_uncertainty",
    "log_leaf_density",
    "log_descriptor_distance",
    "predictive_mean_percentile",
    "log_local_standardized_residual",
    "log_local_residual_dispersion",
)
STRATEGIES=(
    "random",
    "uncertainty_only",
    "raw_ucb_beta_0",
    "raw_ucb_beta_0p125",
    "raw_ucb_beta_0p25",
    "raw_ucb_beta_0p5",
    "raw_ucb_beta_1",
    "raw_ucb_beta_2",
    "raw_ucb_beta_4",
    "raw_ucb_beta_8",
    "gg_ucb_beta_1",
    "gg_calibration_only",
    "gg_acquisition_only",
    "gg_ucb_retuned",
    "candidate_specific_da_oob",
    "cs_da_oob_hist",
    "cs_da_oob_v5",
    "cs_da_oob_parsimonious_f1",
)


def apply_uncertainty_floor(raw_std, floor, allow_nan=False):
    """Return max(raw_std, floor) and a mask of strict floor activations.

    NaN is permitted only for unavailable OOB predictions, where it remains
    unavailable rather than being silently converted into a usable uncertainty.
    """
    values=np.asarray(raw_std,float)
    floor=float(floor)
    if not np.isfinite(floor) or floor<=0: raise ValueError("uncertainty floor must be finite and positive")
    nan=np.isnan(values)
    if np.any(~np.isfinite(values)&~nan): raise ValueError("uncertainty standard deviation must be finite")
    if np.any(nan) and not allow_nan: raise ValueError("uncertainty standard deviation contains NaN")
    if np.any(values[np.isfinite(values)]<0): raise ValueError("uncertainty standard deviation must be non-negative")
    mask=np.isfinite(values)&(values<floor); effective=values.copy(); effective[mask]=floor
    return effective,mask


def stable_order(scores, stable_ids):
    return np.lexsort((np.asarray(stable_ids), -np.asarray(scores,float)))


def beta_from_strategy(name, selected_beta=None):
    if name in {"random","uncertainty_only"}: return None
    if name in {"gg_calibration_only","gg_ucb_beta_1","gg_acquisition_only"}: return 1.0
    if name=="gg_ucb_retuned":
        if selected_beta is None: raise ValueError("selected GG beta missing")
        return float(selected_beta)
    aliases={"ucb_beta_0p5":.5,"ucb_beta_1p0":1.0,"ucb_beta_2p0":2.0}
    if name in aliases: return aliases[name]
    match=__import__("re").fullmatch(r"(?:raw|gg)_ucb_beta_(\d+)(?:p(\d+))?",name)
    if match:
        whole,decimal=match.groups()
        return float(f"{whole}.{decimal or '0'}")
    return 1.0


def gaussian_global_scale(oob_mean,oob_std,y,counts,min_count=3,floor=1e-8):
    effective,_=apply_uncertainty_floor(oob_std,floor,allow_nan=True)
    valid=np.isfinite(oob_mean)&np.isfinite(effective)&(counts>=min_count)
    if valid.sum()<8: return 1.0,"identity_insufficient_oob"
    legacy=float(np.median(np.abs(np.asarray(y)[valid]-oob_mean[valid])/effective[valid]))
    return max(floor,legacy/0.67448975),"gaussian_consistent"


def _descriptor_distance(Xref,Xq,training=False):
    Xref=np.asarray(Xref,float); Xq=np.asarray(Xq,float); center=Xref.mean(0); spread=Xref.std(0); spread[spread<1e-12]=1
    a=np.nan_to_num((Xref-center)/spread); b=np.nan_to_num((Xq-center)/spread)
    k=min(2 if training else 1,len(a)); d,_=NearestNeighbors(n_neighbors=k).fit(a).kneighbors(b)
    return d[:,1 if training and k>1 else 0]


def _local_features(model,Xref,ratios,valid,Xq,raw_std,mean,training=False):
    ref_leaf=model.leaf_or_local_representation(Xref); q_leaf=model.leaf_or_local_representation(Xq)
    local=np.ones(len(Xq)); dispersion=np.zeros(len(Xq)); density=np.zeros(len(Xq))
    for row in range(len(Xq)):
        prox=np.mean(ref_leaf==q_leaf[row],axis=1); mask=valid&(prox>0)
        if training and row<len(mask): mask[row]=False
        if mask.any():
            w=prox[mask]**2; vals=ratios[mask]; order=np.argsort(vals,kind="stable"); vals=vals[order]; w=w[order]
            local[row]=vals[np.searchsorted(np.cumsum(w),.5*w.sum())]
            dispersion[row]=np.average(np.abs(vals-local[row]),weights=w); density[row]=w.sum()
    knn=_descriptor_distance(Xref,Xq,training=training)
    percentile=rankdata(mean,method="average")/max(1,len(mean))
    return np.column_stack([np.log(np.maximum(raw_std,1e-12)),np.log1p(density),np.log1p(knn),percentile,
                            np.log(np.maximum(local,1e-12)),np.log1p(dispersion)])


def candidate_specific_scale(model,oob_mean,oob_std,oob_counts,y,X_candidates,cand_mean,cand_std,seed,config,floor=1e-8):
    oob_effective,_=apply_uncertainty_floor(oob_std,floor,allow_nan=True)
    y=np.asarray(y,float); ratios=np.abs(y-oob_mean)/oob_effective
    valid=np.isfinite(ratios)&(oob_counts>=config.get("min_oob_trees_per_sample",3))
    if valid.sum()<config.get("min_queried_for_DA",30): return np.ones(len(X_candidates)),"raw_ucb_fallback"
    train_features=_local_features(model,model.X_train_,ratios,valid,model.X_train_,oob_std,oob_mean,training=True)
    candidate_features=_local_features(model,model.X_train_,ratios,valid,X_candidates,cand_std,cand_mean)
    valid &= np.isfinite(train_features).all(1)&np.isfinite(oob_mean)&np.isfinite(oob_std)
    if valid.sum()<config.get("min_queried_for_DA",30): return np.ones(len(X_candidates)),"raw_ucb_fallback"
    indices=tuple(config.get("feature_indices",range(len(LOCAL_FEATURE_NAMES))))
    if not indices or any(index<0 or index>=len(LOCAL_FEATURE_NAMES) for index in indices):
        raise ValueError("feature_indices must select at least one valid local feature")
    train_features=train_features[:,indices]; candidate_features=candidate_features[:,indices]
    xf=train_features[valid]; target=y[valid]; mean=oob_mean[valid]; sigma=oob_std[valid]
    center=xf.mean(0); spread=xf.std(0); spread[spread<1e-12]=1; z=(xf-center)/spread
    design=np.column_stack([np.ones(len(z)),z]); rng=np.random.default_rng(seed)
    lo=np.log(config.get("scale_min",.25)); hi=np.log(config.get("scale_max",4.0))
    objective_mode=config.get("objective","pairwise_ranking")
    if objective_mode in {"direct_log_abs_standardized_residual","calibration_ridge"}:
        target_log=np.log(np.maximum(ratios[valid],floor))
        fit=Ridge(alpha=float(config.get("l2_regularization",.01)),fit_intercept=True)
        fit.fit(z,target_log)
        candidate_z=(candidate_features-center)/spread
        logs=fit.predict(candidate_z)
        scales=np.exp(np.clip(logs,lo,hi))
        return scales,"direct_fit_success"
    if objective_mode!="pairwise_ranking":
        raise ValueError(f"unknown candidate-specific objective: {objective_mode}")
    maximum=int(config.get("maximum_pairs",20000)); i=rng.integers(0,len(target),size=maximum*2); j=rng.integers(0,len(target),size=maximum*2)
    keep=(i!=j)&(target[i]!=target[j]); i=i[keep][:maximum]; j=j[keep][:maximum]
    if len(i)==0: return np.ones(len(X_candidates)),"raw_ucb_fallback"
    cutoff=np.quantile(target,1-config.get("top_q_fraction",.10)); weights=np.where((target[i]>=cutoff)|(target[j]>=cutoff),config.get("top_q_pair_weight",2.0),1.0)
    sign=np.sign(target[i]-target[j]); temp=config.get("pair_score_temperature",1.0)
    def objective(theta):
        logs=design@theta; scale=np.exp(np.clip(logs,lo,hi)); score=mean+scale*sigma; margin=sign*(score[i]-score[j])/temp
        loss=np.average(np.logaddexp(0,-margin),weights=weights)+config.get("l2_regularization",.01)*np.sum(theta[1:]**2)+config.get("mean_log_scale_squared_regularization",.01)*np.mean(logs**2)
        active=((logs>lo)&(logs<hi)).astype(float); ds=(scale*sigma*active)[:,None]*design
        grad=np.average((-sign*expit(-margin)/temp)[:,None]*(ds[i]-ds[j]),axis=0,weights=weights)
        grad[1:]+=2*config.get("l2_regularization",.01)*theta[1:]; grad+=2*config.get("mean_log_scale_squared_regularization",.01)*np.mean(logs[:,None]*design,axis=0)
        return float(loss),grad
    fit=minimize(objective,np.zeros(design.shape[1]),jac=True,method="L-BFGS-B",options={"maxiter":int(config.get("optimizer_maxiter",100))})
    cq=(candidate_features-center)/spread; scales=np.exp(np.clip(np.column_stack([np.ones(len(cq)),cq])@fit.x,lo,hi))
    return scales,("fit_success" if fit.success else "fit_nonconverged_used")


def score_strategy(name,mean,std,stable_ids,rng,global_scale=1.0,candidate_scale=None,floor=1e-8,
                   return_diagnostics=False,selected_beta=None):
    if name=="random":
        score,scale=rng.random(len(mean)),np.ones(len(mean)); effective,mask=apply_uncertainty_floor(std,floor)
        return (score,scale,effective,mask) if return_diagnostics else (score,scale)
    effective,mask=apply_uncertainty_floor(std,floor)
    if name=="uncertainty_only":
        score,scale=effective.copy(),np.ones(len(mean))
        return (score,scale,effective,mask) if return_diagnostics else (score,scale)
    beta=beta_from_strategy(name,selected_beta)
    scale=np.ones(len(mean))
    if name in {"gaussian_global_ucb","gg_ucb_beta_1","gg_acquisition_only","gg_ucb_retuned"} or name.startswith("gg_ucb_beta_"):
        scale=np.full(len(mean),global_scale)
    elif name=="gg_calibration_only":
        scale=np.ones(len(mean))
    elif name=="legacy_median_ucb": scale=np.full(len(mean),global_scale*0.67448975)
    elif name.startswith("candidate_specific") or name.startswith("cs_da_oob"):
        if candidate_scale is None: raise ValueError("candidate-specific scale missing")
        scale=np.asarray(candidate_scale,float)
    if scale.shape!=effective.shape or not np.isfinite(scale).all() or np.any(scale<=0): raise ValueError("acquisition scale must be finite and positive")
    score=np.asarray(mean)+beta*scale*effective
    return (score,scale,effective,mask) if return_diagnostics else (score,scale)


def diagnostic_standard_deviation(name,raw_std,global_scale=1.0,floor=1e-8):
    effective,_=apply_uncertainty_floor(raw_std,floor)
    if name in {"gaussian_global_ucb","gg_ucb_beta_1","gg_calibration_only","gg_ucb_retuned"}:
        return effective*float(global_scale)
    return effective


def global_scaling_equivalence(mean,raw_std,stable_ids,beta,global_scale,floor=1e-8):
    effective,_=apply_uncertainty_floor(raw_std,floor)
    gg=np.asarray(mean,float)+float(beta)*float(global_scale)*effective
    raw=np.asarray(mean,float)+(float(beta)*float(global_scale))*effective
    gg_order=stable_order(gg,stable_ids)
    raw_order=stable_order(raw,stable_ids)
    return {
        "max_abs_score_difference":float(np.max(np.abs(gg-raw))) if len(gg) else 0.0,
        "rank_identity":bool(np.array_equal(gg_order,raw_order)),
        "gg_scores":gg,
        "raw_beta_eff_scores":raw,
        "gg_order":gg_order,
        "raw_beta_eff_order":raw_order,
    }


def choose(scores,stable_ids,batch_size): return stable_order(scores,stable_ids)[:min(batch_size,len(scores))]
