from __future__ import annotations

import numpy as np
from scipy.special import ndtr
from scipy.stats import kendalltau


def uncertainty_quality(y,mean,std,floor=1e-8):
    y=np.asarray(y,float); mean=np.asarray(mean,float); std=np.maximum(np.asarray(std,float),floor); z=(y-mean)/std
    levels=(.50,.80,.90,.95); gaussian=(.67448975,1.28155157,1.64485363,1.95996398)
    coverage=[float(np.mean(np.abs(z)<=q)) for q in gaussian]
    signed=[a-b for a,b in zip(coverage,levels)]; errors=[abs(value) for value in signed]
    nll=.5*np.log(2*np.pi*std**2)+.5*z**2
    phi=np.exp(-.5*z**2)/np.sqrt(2*np.pi)
    crps=std*(z*(2*ndtr(z)-1)+2*phi-1/np.sqrt(np.pi))
    return {"mean_absolute_coverage_error":float(np.mean(errors)),"coverage_50":coverage[0],"coverage_80":coverage[1],
        "coverage_90":coverage[2],"coverage_95":coverage[3],"gaussian_nll_mean":float(np.mean(nll)),
        "signed_coverage_error_50":signed[0],"signed_coverage_error_80":signed[1],
        "signed_coverage_error_90":signed[2],"signed_coverage_error_95":signed[3],
        "crps_mean":float(np.mean(crps)),
        "standardized_residual_q025":float(np.quantile(z,.025)),"standardized_residual_q975":float(np.quantile(z,.975)),
        "mean_interval_width_95":float(np.mean(2*1.95996398*std)),"floor_rate":float(np.mean(np.asarray(std)<=floor))}


def decision_intervention(alternative_scores,raw_scores,stable_ids,batch_size):
    from .strategies import stable_order
    a=stable_order(alternative_scores,stable_ids); b=stable_order(raw_scores,stable_ids); B=min(batch_size,len(a)); sa=set(a[:B]); sb=set(b[:B])
    union=len(sa|sb); top5=min(5*B,len(a)); tau=kendalltau(np.argsort(a),np.argsort(b)).statistic
    return {"batch_replacement_fraction":1-len(sa&sb)/max(1,union),
        "raw_selected_fraction_replaced":1-len(sa&sb)/max(1,len(sb)),"topB_overlap":len(sa&sb)/max(1,B),
        "top5B_overlap":len(set(a[:top5])&set(b[:top5]))/max(1,top5),"kendall_tau":float(tau),
        "material_change_10pct":bool(1-len(sa&sb)/max(1,union)>=.10),"sensitivity_05":bool(1-len(sa&sb)/max(1,union)>=.05),
        "sensitivity_20":bool(1-len(sa&sb)/max(1,union)>=.20)}
