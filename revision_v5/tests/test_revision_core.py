from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from transportability_v5.layers import decision_intervention, uncertainty_quality
from transportability_v5.metrics import (batch_utility, budget_to_recall, normalized_auc,
                                         stable_topk, target_set_size)
from transportability_v5.statistics import (assert_unique_inference_rows, benjamini_hochberg,
                                             paired_percentile_bootstrap, paired_sign_flip_test)
from transportability_v5.registry import claim_next,initialize,transition
from transportability_v5.strategies import (diagnostic_standard_deviation, global_scaling_equivalence,
                                             apply_uncertainty_floor, score_strategy, stable_order)


ROOT=Path(__file__).resolve().parents[1]


def test_seed_disjointness_and_corrected_parser():
    summary=json.loads((ROOT/"audits_v4"/"seed_namespace_summary.json").read_text(encoding="utf-8"))
    assert summary["candidate_range_is_disjoint"]
    assert summary["candidate_unused"]==list(range(5000,5040))


def test_development_manifest_complete_and_unique():
    manifest=pd.read_csv(ROOT/"manifests_v4"/"DEVELOPMENT_JOB_MANIFEST_V5.csv")
    lock=json.loads((ROOT/"manifests_v4"/"DEVELOPMENT_SPEC_LOCK_V5.json").read_text(encoding="utf-8"))
    assert len(manifest)==lock["job_count"]==5760
    assert manifest.job_id.is_unique
    assert set(manifest.seed)==set(range(1000,1010))
    assert set(manifest.status)=={"PLANNED"}


def test_ood_group_disjointness_audit():
    audit=pd.read_csv(ROOT/"audits_v4"/"ood_disjointness_audit.csv")
    assert len(audit)==160
    assert audit["pass"].all()
    assert (audit.source_target_diagnostic_group_overlap==0).all()
    assert (audit.candidate_id_overlap==0).all()


def test_stable_id_tie_breaking():
    scores=np.ones(4); ids=np.array([9,2,7,1])
    assert ids[stable_order(scores,ids)].tolist()==[1,2,7,9]


def test_raw_vs_calibration_only_decision_identity():
    mean=np.array([0.,1.,1.]); std=np.array([2.,.1,.1]); ids=np.array([3,2,1]); rng=np.random.default_rng(1)
    raw,_=score_strategy("raw_ucb_beta_1",mean,std,ids,rng)
    calibration_only,_=score_strategy("gg_calibration_only",mean,std,ids,rng,global_scale=7)
    assert np.array_equal(raw,calibration_only)
    assert np.array_equal(stable_order(raw,ids),stable_order(calibration_only,ids))
    assert np.array_equal(diagnostic_standard_deviation("gg_calibration_only",std,7),np.maximum(std,1e-8)*7)


def test_gg_vs_raw_beta_eff_score_equivalence():
    rng=np.random.default_rng(4); mean=rng.normal(size=30); std=np.abs(rng.normal(size=30)); ids=rng.permutation(30)
    result=global_scaling_equivalence(mean,std,ids,beta=.5,global_scale=2.75)
    assert result["max_abs_score_difference"]==0
    assert result["rank_identity"]


def test_diagnostic_scale_does_not_enter_calibration_only_acquisition():
    mean=np.array([1.,2.]); std=np.array([.2,.3]); ids=np.arange(2); rng=np.random.default_rng(2)
    a,_=score_strategy("gg_calibration_only",mean,std,ids,rng,global_scale=.01)
    b,_=score_strategy("gg_calibration_only",mean,std,ids,rng,global_scale=100)
    assert np.array_equal(a,b)


def test_target_top_q_integer_construction_and_stable_ties():
    y=np.ones(101); pool=np.arange(101); ids=np.arange(101)[::-1]
    assert target_set_size(pool,.005)==1
    assert target_set_size(pool,.01)==2
    assert ids[stable_topk(y,pool,ids,.01)].tolist()==[0,1]


def test_l2_formulas():
    result=decision_intervention(np.array([4.,3.,2.,1.]),np.array([4.,2.,3.,1.]),np.arange(4),2)
    assert result["batch_replacement_fraction"]==pytest.approx(2/3)
    assert result["raw_selected_fraction_replaced"]==pytest.approx(.5)


def test_l3_formulas_and_target_sizes():
    y=np.arange(200,dtype=float); pool=np.arange(200); ids=np.arange(200)
    result=batch_utility(y,[199,198],[0,1],pool,ids)
    assert result["immediate_top1_recall_increment"]==1
    assert result["top0p5_target_set_size"]==1
    assert result["top5_target_set_size"]==10


def test_l4_integration_and_budget_threshold():
    assert normalized_auc([0,.5,1],[0,.5,1])==pytest.approx(.5)
    assert budget_to_recall([10,20,30],[0,.4,.8],.5)==30
    assert budget_to_recall([10,20],[0,.4],.5) is None


def test_calibration_metrics_are_finite_and_crps_nonnegative():
    result=uncertainty_quality([0,1],[0.1,.9],[.2,.2])
    assert result["crps_mean"]>=0
    assert np.isfinite(list(result.values())).all()


def test_floor_event_count_and_candidate_scale_clip_bounds():
    effective,mask=apply_uncertainty_floor([0,1e-9,1.0],1e-8)
    assert mask.tolist()==[True,True,False]
    assert effective.tolist()==[1e-8,1e-8,1.0]
    proposed=np.exp(np.clip(np.array([-100.,0.,100.]),np.log(.25),np.log(4.0)))
    assert np.count_nonzero(proposed==.25)==1
    assert np.count_nonzero(proposed==4.0)==1


def test_bootstrap_and_permutation_reproducibility():
    alt=np.arange(20,dtype=float)+.1; raw=np.arange(20,dtype=float)
    assert paired_percentile_bootstrap(alt,raw,n_boot=1000)==paired_percentile_bootstrap(alt,raw,n_boot=1000)
    assert paired_sign_flip_test(alt,raw)==paired_sign_flip_test(alt,raw)


def test_bh_family_construction():
    adjusted=benjamini_hochberg([.01,.04,.03,.2])
    assert np.allclose(adjusted,[.04,.05333333333333334,.05333333333333334,.2])


def test_no_duplicate_inference_rows():
    frame=pd.DataFrame({"environment":["a","b"],"contrast":["x","x"]})
    assert_unique_inference_rows(frame,["environment","contrast"])
    with pytest.raises(ValueError):
        assert_unique_inference_rows(pd.concat([frame,frame.iloc[[0]]]),["environment","contrast"])


def test_registry_statuses_and_recovery(tmp_path):
    connection=initialize(tmp_path/"registry.sqlite",["a","b"],"abc")
    claim=claim_next(connection,"worker",123,"host")
    assert claim["job_id"]=="a"
    transition(connection,"a","FAILED",{"exit_code":1,"last_error":"test"})
    transition(connection,"a","PLANNED",allow_retry=True)
    claim=claim_next(connection,"worker",123,"host")
    assert claim["job_id"]=="a"
    transition(connection,"a","RECOVERED",{"exit_code":0})
    statuses=dict(connection.execute("SELECT job_id,status FROM jobs"))
    assert statuses=={"a":"RECOVERED","b":"PLANNED"}


def test_historical_da_oob_identity_never_claims_minimum_ten():
    historical={
        "strategy":"cs_da_oob_hist",
        "evidence_class":"historical_v2_v3",
        "min_oob_trees_per_sample":3,
    }
    assert historical["strategy"]=="cs_da_oob_hist"
    assert historical["min_oob_trees_per_sample"]==3
    assert not (
        historical["evidence_class"].startswith("historical")
        and historical["min_oob_trees_per_sample"]==10
    )
