from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .checkpoint import assert_complete_checkpoint_set, checkpoint_labels_present, save_reached_checkpoints
from .layers import uncertainty_quality
from .metrics import (best_so_far, enrichment_factor, normalized_auc, normalized_simple_regret,
                      recall, simple_regret, batch_utility, target_set_size)
from .provenance import atomic_json, stable_payload_hash, source_code_hashes, write_job_provenance
from .strategies import (apply_uncertainty_floor, choose, score_strategy, gaussian_global_scale,
                         candidate_specific_scale, diagnostic_standard_deviation)
from .surrogates import make_surrogate


class ControlledInterruption(RuntimeError):
    """Intentional canary-only stop after a durable checkpoint."""


def peak_memory_mb():
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD),("PeakWorkingSetSize",ctypes.c_size_t),
                    ("WorkingSetSize",ctypes.c_size_t),("QuotaPeakPagedPoolUsage",ctypes.c_size_t),("QuotaPagedPoolUsage",ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage",ctypes.c_size_t),("QuotaNonPagedPoolUsage",ctypes.c_size_t),("PagefileUsage",ctypes.c_size_t),("PeakPagefileUsage",ctypes.c_size_t)]
            value=Counters(); value.cb=ctypes.sizeof(value)
            function=ctypes.windll.psapi.GetProcessMemoryInfo
            function.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]; function.restype=wintypes.BOOL
            handle=ctypes.windll.kernel32.GetCurrentProcess()
            if not function(handle,ctypes.byref(value),value.cb): return float("nan")
            return float(value.PeakWorkingSetSize/1024**2)
        import resource
        value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return float(value/1024 if value>10**7 else value/1024)
    except Exception:
        return float("nan")


def atomic_parquet(df, path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_suffix(path.suffix+".tmp")
    df.to_parquet(temporary,index=False,compression="zstd"); os.replace(temporary,path)


def _identity_fields(identity):
    return {key: identity[key] for key in ("protocol_schema_version", "protocol_path", "protocol_sha256",
                                             "analysis_plan_path", "analysis_plan_sha256", "manifest_path",
                                             "manifest_sha256", "run_config_sha256", "job_id")}


def _verify_resume_identity(state, identity):
    for key, value in _identity_fields(identity).items():
        if key in {"manifest_path","manifest_sha256"}: continue
        if state.get(key) != value:
            raise RuntimeError(f"resume identity mismatch for {key}")


def _floor_statistics(raw_std, effective_std, floor_mask, selected_positions, oob_std, floor):
    selected_positions=np.asarray(selected_positions,int); finite_oob=np.isfinite(oob_std)
    _,oob_mask=apply_uncertainty_floor(oob_std,floor,allow_nan=True)
    count=len(raw_std); selected_count=len(selected_positions); oob_count=int(finite_oob.sum())
    return {
        "uncertainty_floor": float(floor),
        "pool_floor_event_count": int(floor_mask.sum()),
        "pool_floor_event_rate": float(floor_mask.mean()) if count else 0.0,
        "selected_floor_event_count": int(floor_mask[selected_positions].sum()) if selected_count else 0,
        "selected_floor_event_rate": float(floor_mask[selected_positions].mean()) if selected_count else 0.0,
        "min_raw_std": float(np.min(raw_std)) if count else float("nan"),
        "min_effective_std": float(np.min(effective_std)) if count else float("nan"),
        "oob_floor_event_count": int(oob_mask.sum()),
        "oob_floor_event_rate": float(oob_mask.sum()/oob_count) if oob_count else 0.0,
        "oob_available_count": oob_count,
    }


def _state_payload(key, identity, queried, next_round, complete, floor_totals, primary_nauc=None, checkpoints=None, manifest_history=None):
    payload={"key":key, "config_hash":identity["run_config_sha256"], **_identity_fields(identity),
             "queried_indices":list(map(int,queried)), "next_round":int(next_round), "complete":bool(complete),
             "total_pool_floor_events":int(floor_totals["pool"]),
             "total_selected_floor_events":int(floor_totals["selected"]),
             "total_oob_floor_events":int(floor_totals["oob"]),
             "floor_was_ever_active":bool(floor_totals["ever"]),
             "checkpoint_labels":sorted(checkpoints or []),
             "manifest_sha256_history":list(manifest_history or [identity["manifest_sha256"]])}
    if primary_nauc is not None: payload["primary_nauc"]=float(primary_nauc)
    return payload


def run_trajectory(X,y,formulas,ids,split,strategy,model_name,master_seed,config,output_dir,identity,protocol_raw,resume=True,
                   interrupt_after_checkpoint_label=None):
    """Run one schema-v2 trajectory with auditable provenance and checkpoints."""
    X=np.asarray(X,float); y=np.asarray(y,float); ids=np.asarray(ids); stable=np.arange(len(y),dtype=np.int64)
    target=np.asarray(split.target,int); source=np.asarray(split.source,int)
    initial_count=max(1,min(len(source),int(config["campaign"]["initial_count"])))
    batch_size=max(1,int(config["campaign"]["batch_size"])); max_queries=min(len(target),int(config["campaign"]["max_queries"]))
    if identity["run_config_sha256"] != stable_payload_hash(config): raise ValueError("run config hash does not match identity")
    key=f"{config['task']}__{split.protocol}__{model_name}__{strategy}__seed{master_seed}"
    if identity["job_id"] != key: raise ValueError("job identity does not match trajectory key")
    out=Path(output_dir)/key; out.mkdir(parents=True,exist_ok=True)
    state_path=out/"state.json"; rounds_path=out/"rounds.parquet"; selected_path=out/"selected.parquet"
    diagnostic_path=out/"diagnostic_metrics.parquet"; floor_audit_path=out/"floor_ranking_audit.parquet"
    write_job_provenance(out,identity,protocol_raw,source_code_hashes(Path(__file__).resolve().parents[2]))
    init_rng=np.random.default_rng(master_seed); initial=np.sort(init_rng.choice(source,size=initial_count,replace=False))
    queried=list(map(int,initial)); selected_rows=[]; diagnostic_rows=[]; floor_audit_rows=[]; start_round=0; floor_totals={"pool":0,"selected":0,"oob":0,"ever":False}; manifest_history=[identity["manifest_sha256"]]
    round_rows=[{"environment_id":f"{config['task']}|{split.protocol}|{model_name}","task":config["task"],
        "split_protocol":split.protocol,"model":model_name,"strategy":strategy,"seed":master_seed,"round":-1,
        "config_hash":identity["run_config_sha256"], **_identity_fields(identity),
        "queried_ids_before":json.dumps(ids[queried].tolist()),"selected_batch_ids":"[]",
        "top0p5_recall":recall(y,queried,target,stable,.005),"top1_recall":recall(y,queried,target,stable,.01),
        "top2_recall":recall(y,queried,target,stable,.02),"top5_recall":recall(y,queried,target,stable,.05),
        "top0p5_target_set_size":target_set_size(target,.005),"top1_target_set_size":target_set_size(target,.01),
        "top2_target_set_size":target_set_size(target,.02),"top5_target_set_size":target_set_size(target,.05),
        "budget_fraction":0.0,"simple_regret":simple_regret(y,queried,np.concatenate([source,target])),"candidate_count":len(target),
        "global_scale":1.0,"scale_status":"initial_state","candidate_scale_status":"initial_state","runtime_seconds":0.0,"peak_memory_mb":peak_memory_mb(),
        "uncertainty_floor":float(config["oob"]["uncertainty_floor"]),"pool_floor_event_count":0,"pool_floor_event_rate":0.0,
        "selected_floor_event_count":0,"selected_floor_event_rate":0.0,"min_raw_std":float("nan"),"min_effective_std":float("nan"),
        "oob_floor_event_count":0,"oob_floor_event_rate":0.0,"oob_available_count":0,
        "batch_replacement_fraction":0.0,"immediate_top1_recall_increment":0.0,"top1_precision_gain":0.0,"top5_precision_gain":0.0}]
    if resume and state_path.exists():
        state=json.loads(state_path.read_text(encoding="utf-8")); _verify_resume_identity(state,identity)
        queried=list(map(int,state["queried_indices"])); start_round=int(state["next_round"])
        floor_totals={"pool":int(state.get("total_pool_floor_events",0)),"selected":int(state.get("total_selected_floor_events",0)),
                      "oob":int(state.get("total_oob_floor_events",0)),"ever":bool(state.get("floor_was_ever_active",False))}
        manifest_history=list(state.get("manifest_sha256_history",[state.get("manifest_sha256")]))
        if identity["manifest_sha256"] not in manifest_history: manifest_history.append(identity["manifest_sha256"])
        if rounds_path.exists(): round_rows=pd.read_parquet(rounds_path).to_dict("records")
        if selected_path.exists(): selected_rows=pd.read_parquet(selected_path).to_dict("records")
        if diagnostic_path.exists(): diagnostic_rows=pd.read_parquet(diagnostic_path).to_dict("records")
        if floor_audit_path.exists(): floor_audit_rows=pd.read_parquet(floor_audit_path).to_dict("records")
        if state.get("complete"):
            assert_complete_checkpoint_set(out)
            return {"key":key,"rounds":pd.DataFrame(round_rows),"selected":pd.DataFrame(selected_rows),
                    "primary_nauc":float(state["primary_nauc"]),"state_path":str(state_path)}
    pool_reference=target.copy(); started=time.perf_counter(); floor=float(config["oob"]["uncertainty_floor"])
    initial_checkpoint_written=False
    while len(set(queried)&set(target)) < max_queries:
        candidates=np.array(sorted(set(map(int,target))-set(queried)),int)
        if len(candidates)==0: break
        seed=int(np.random.SeedSequence([master_seed,start_round,11 if model_name=="random_forest" else 17]).generate_state(1)[0])
        model=make_surrogate(model_name,n_estimators=config["model"]["n_estimators"],min_samples_leaf=config["model"]["min_samples_leaf"],n_jobs=1)
        model.fit(X[queried],y[queried],seed,stable[queried])
        if not initial_checkpoint_written:
            save_reached_checkpoints(model,out,0.0,-1,len(queried),identity); initial_checkpoint_written=True
        mean,raw_std=model.predict_mean_std(X[candidates]); effective_std,pool_floor_mask=apply_uncertainty_floor(raw_std,floor)
        om,osd,counts=model.oob_or_crossfit_predict_mean_std()
        global_scale,scale_status=gaussian_global_scale(om,osd,y[queried],counts,config["oob"]["min_oob_trees_per_sample"],floor)
        cscale=None; da_status="not_applicable"
        if strategy.startswith("candidate_specific") or strategy.startswith("cs_da_oob"):
            cscale,da_status=candidate_specific_scale(model,om,osd,counts,y[queried],X[candidates],mean,raw_std,seed,config["candidate_specific"],floor)
        rng=np.random.default_rng(np.random.SeedSequence([master_seed,start_round,31]).generate_state(1)[0])
        selected_beta=config.get("acquisition",{}).get("selected_beta")
        scores,used_scale,scored_effective_std,scored_floor_mask=score_strategy(
            strategy,mean,raw_std,stable[candidates],rng,global_scale,cscale,floor,True,selected_beta)
        if not np.array_equal(effective_std,scored_effective_std) or not np.array_equal(pool_floor_mask,scored_floor_mask):
            raise RuntimeError("acquisition floor diagnostics disagree")
        positions=choose(scores,stable[candidates],min(batch_size,max_queries-len(set(queried)&set(target))))
        chosen=candidates[positions]
        base_order=np.asarray(choose(scores,stable[candidates],len(candidates)),int)
        for alternative_floor in config.get("floor_sensitivity",{}).get("absolute_floors",[floor]):
            alternative_floor=float(alternative_floor)
            pool_affected=bool(np.any(np.asarray(raw_std)<alternative_floor))
            oob_affected=bool(np.any(np.isfinite(osd)&(np.asarray(osd)<alternative_floor)))
            candidate_strategy=strategy.startswith("candidate_specific") or strategy.startswith("cs_da_oob")
            deferred=bool(candidate_strategy and oob_affected and alternative_floor!=floor)
            if deferred:
                alternative_scores=None; alternative_order=None; alternative_positions=None
                rank_identity=None; selected_identity=None; score_difference=None
            else:
                alternative_global,_=gaussian_global_scale(
                    om,osd,y[queried],counts,config["oob"]["min_oob_trees_per_sample"],alternative_floor
                )
                alternative_scores,_=score_strategy(
                    strategy,mean,raw_std,stable[candidates],rng,alternative_global,
                    cscale,alternative_floor
                )
                alternative_order=np.asarray(choose(alternative_scores,stable[candidates],len(candidates)),int)
                alternative_positions=alternative_order[:len(positions)]
                rank_identity=bool(np.array_equal(base_order,alternative_order))
                selected_identity=bool(np.array_equal(
                    stable[candidates][positions],stable[candidates][alternative_positions]
                ))
                score_difference=float(np.max(np.abs(scores-alternative_scores)))
            floor_audit_rows.append({
                "environment_id":f"{config['task']}|{split.protocol}|{model_name}",
                "strategy":strategy,"seed":master_seed,"round":start_round,
                "floor":alternative_floor,
                "complete_rank_identity":rank_identity,
                "selected_id_identity":selected_identity,
                "base_rank_sha256":hashlib.sha256(
                    np.asarray(stable[candidates][base_order],dtype=np.int64).tobytes()
                ).hexdigest(),
                "alternative_rank_sha256":(
                    hashlib.sha256(np.asarray(stable[candidates][alternative_order],dtype=np.int64).tobytes()).hexdigest()
                    if alternative_order is not None else ""
                ),
                "score_vector_max_abs_difference":score_difference,
                "floor_event_count":int(np.count_nonzero(np.asarray(raw_std)<alternative_floor)),
                "pool_floor_affected":pool_affected,
                "oob_floor_affected":oob_affected,
                "requires_offline_candidate_refit":deferred,
                "candidate_count":len(candidates),
            })
        raw_scores,_=score_strategy("ucb_beta_1p0",mean,raw_std,stable[candidates],rng,floor=floor)
        raw_positions=choose(raw_scores,stable[candidates],len(chosen)); raw_batch=candidates[raw_positions]
        utility=batch_utility(y,chosen,raw_batch,pool_reference,stable)
        before=list(queried); queried.extend(map(int,chosen)); budget=len(set(queried)&set(target))/max_queries
        statistics=_floor_statistics(raw_std,effective_std,pool_floor_mask,positions,osd,floor)
        floor_totals["pool"]+=statistics["pool_floor_event_count"]; floor_totals["selected"]+=statistics["selected_floor_event_count"]
        floor_totals["oob"]+=statistics["oob_floor_event_count"]; floor_totals["ever"]|=bool(statistics["pool_floor_event_count"] or statistics["oob_floor_event_count"])
        row={"environment_id":f"{config['task']}|{split.protocol}|{model_name}","task":config["task"],"split_protocol":split.protocol,
             "model":model_name,"strategy":strategy,"seed":master_seed,"round":start_round,"config_hash":identity["run_config_sha256"], **_identity_fields(identity),
             "queried_ids_before":json.dumps(ids[before].tolist()),"selected_batch_ids":json.dumps(ids[chosen].tolist()),
             "top0p5_recall":recall(y,queried,pool_reference,stable,.005),"top1_recall":recall(y,queried,pool_reference,stable,.01),
             "top2_recall":recall(y,queried,pool_reference,stable,.02),"top5_recall":recall(y,queried,pool_reference,stable,.05),
             "top0p5_target_set_size":target_set_size(pool_reference,.005),"top1_target_set_size":target_set_size(pool_reference,.01),
             "top2_target_set_size":target_set_size(pool_reference,.02),"top5_target_set_size":target_set_size(pool_reference,.05),
             "enrichment_factor_top1":enrichment_factor(y,queried,pool_reference,stable,.01),
             "best_so_far":best_so_far(y,queried),"normalized_simple_regret":normalized_simple_regret(y,queried,pool_reference),
             "budget_fraction":budget,"simple_regret":simple_regret(y,queried,pool_reference),"candidate_count":len(candidates),
             "global_scale":global_scale,"scale_status":scale_status,"candidate_scale_status":da_status,"runtime_seconds":time.perf_counter()-started,"peak_memory_mb":peak_memory_mb(),
             **statistics, **utility}
        round_rows.append(row)
        diagnostic=np.asarray(split.diagnostic,int)
        diagnostic_mean,diagnostic_raw_std=model.predict_mean_std(X[diagnostic])
        diagnostic_std=diagnostic_standard_deviation(strategy,diagnostic_raw_std,global_scale,floor)
        quality=uncertainty_quality(y[diagnostic],diagnostic_mean,diagnostic_std,floor)
        diagnostic_rows.append({
            "environment_id":row["environment_id"],"strategy":strategy,"seed":master_seed,"round":start_round,
            "diagnostic_count":len(diagnostic),"diagnostic_scale_uses_targets":False,
            "diagnostic_targets_used_in_acquisition":False,"global_scale":float(global_scale),**quality,
        })
        topn=min(5*len(chosen),len(candidates)); top=choose(scores,stable[candidates],topn)
        for rank,pos in enumerate(top):
            idx=int(candidates[pos]); selected_rows.append({"environment_id":row["environment_id"],"strategy":strategy,"seed":master_seed,"round":start_round,
                **_identity_fields(identity),"stable_candidate_id":int(stable[idx]),"candidate_id":str(ids[idx]),"rank":rank+1,"selected":bool(pos in set(positions)),
                "predicted_mean":float(mean[pos]),"raw_predicted_std":float(raw_std[pos]),"effective_predicted_std":float(effective_std[pos]),
                "floor_was_applied":bool(pool_floor_mask[pos]),"scale":float(used_scale[pos]),"score":float(scores[pos])})
        atomic_parquet(pd.DataFrame(round_rows),rounds_path); atomic_parquet(pd.DataFrame(selected_rows),selected_path)
        atomic_parquet(pd.DataFrame(diagnostic_rows),diagnostic_path)
        atomic_parquet(pd.DataFrame(floor_audit_rows),floor_audit_path)
        atomic_json(state_path,_state_payload(key,identity,queried,start_round+1,False,floor_totals,checkpoints=checkpoint_labels_present(out),manifest_history=manifest_history))
        checkpoint_seed=int(np.random.SeedSequence([master_seed,start_round+1,11 if model_name=="random_forest" else 17]).generate_state(1)[0])
        checkpoint_model=make_surrogate(model_name,n_estimators=config["model"]["n_estimators"],min_samples_leaf=config["model"]["min_samples_leaf"],n_jobs=1)
        checkpoint_model.fit(X[queried],y[queried],checkpoint_seed,stable[queried])
        reached=save_reached_checkpoints(checkpoint_model,out,budget,start_round,len(queried),identity)
        atomic_json(state_path,_state_payload(key,identity,queried,start_round+1,False,floor_totals,checkpoints=checkpoint_labels_present(out),manifest_history=manifest_history))
        if interrupt_after_checkpoint_label in reached:
            raise ControlledInterruption(f"controlled interruption after checkpoint {interrupt_after_checkpoint_label}")
        start_round+=1
    assert_complete_checkpoint_set(out)
    frame=pd.DataFrame(round_rows); value=normalized_auc(frame["budget_fraction"],frame["top1_recall"]) if len(frame) else float("nan")
    atomic_json(state_path,_state_payload(key,identity,queried,start_round,True,floor_totals,value,checkpoint_labels_present(out),manifest_history=manifest_history))
    return {"key":key,"rounds":frame,"selected":pd.DataFrame(selected_rows),"primary_nauc":value,"state_path":str(state_path)}
