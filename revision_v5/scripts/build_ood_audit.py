from __future__ import annotations

import csv
import functools
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd


ROOT=Path(r"C:\Users\ROG\Desktop\贝叶斯优化\revision_v5")
WORKSPACE=ROOT.parent
CODE=WORKSPACE/"最终"/"_code_package"
sys.path.insert(0,str(ROOT/"experiments_v4"/"src"))
from transportability_v5.data import load_materials_csv
from transportability_v5.splits import chemical_system

TASKS=("matbench_expt_gap","matbench_mp_gap","matbench_log_gvrh","matbench_log_kvrh")
SEEDS=range(5000,5040)


@functools.lru_cache(maxsize=None)
def system(formula):
    return chemical_system(formula)


def stable_key(seed,value):
    return hashlib.sha256(f"{seed}|{value}".encode()).hexdigest()


def assign(groups,seed,n):
    by_group={}
    for index,group in enumerate(groups): by_group.setdefault(group,[]).append(index)
    targets={"source":n*.20,"diagnostic":n*.20,"target":n*.60}
    assigned={key:[] for key in targets}; counts={key:0 for key in targets}
    for group in sorted(by_group,key=lambda value:(-len(by_group[value]),stable_key(seed,value))):
        role=max(targets,key=lambda key:(targets[key]-counts[key],-counts[key],key))
        assigned[role].extend(by_group[group]); counts[role]+=len(by_group[group])
    return {key:np.asarray(sorted(value),int) for key,value in assigned.items()}


def elements(formula):
    return sorted(set(re.findall(r"[A-Z][a-z]?",str(formula))))


def main():
    audit=[]; summary=[]; element_rows=[]
    for task in TASKS:
        data=load_materials_csv(CODE/"results"/"benchmark"/task/"materials.csv")
        formulas=data.formula.astype(str).to_numpy(); ids=data.material_id.astype(str).to_numpy()
        groups=tuple(system(value) for value in formulas)
        for seed in SEEDS:
            roles=assign(groups,seed,len(data))
            group_sets={key:{groups[index] for index in values} for key,values in roles.items()}
            id_sets={key:set(ids[values]) for key,values in roles.items()}
            overlap=sum(len(group_sets[a]&group_sets[b]) for a,b in (("source","target"),("source","diagnostic"),("target","diagnostic")))
            id_overlap=sum(len(id_sets[a]&id_sets[b]) for a,b in (("source","target"),("source","diagnostic"),("target","diagnostic")))
            duplicate_ids=len(ids)-len(set(ids))
            audit.append({
                "task":task,"seed":seed,"source_target_diagnostic_group_overlap":overlap,
                "candidate_id_overlap":id_overlap,"duplicate_material_id_count":duplicate_ids,
                "source_records":len(roles["source"]),"target_records":len(roles["target"]),
                "diagnostic_records":len(roles["diagnostic"]),"pass":overlap==0 and id_overlap==0 and duplicate_ids==0,
            })
            for role,indices in roles.items():
                values=data.target.to_numpy(float)[indices]
                summary.append({
                    "evidence_class":"prospective_v5_rc1_split_geometry","task":task,"split_protocol":"chemical_system_ood",
                    "seed":seed,"role":role,"record_count":len(indices),"group_count":len(group_sets[role]),
                    "target_mean":float(np.mean(values)),"target_std":float(np.std(values)),
                    "target_q01":float(np.quantile(values,.01)),"target_q99":float(np.quantile(values,.99)),
                    "target_used_for_partition":False,
                })
                counts=Counter(element for index in indices for element in elements(formulas[index]))
                for element,count in counts.items():
                    element_rows.append({"task":task,"seed":seed,"role":role,"element":element,"record_presence_count":count})
    pd.DataFrame(audit).to_csv(ROOT/"audits_v4"/"ood_disjointness_audit.csv",index=False)
    pd.DataFrame(summary).to_csv(ROOT/"tables_v5"/"ood_split_summary.csv",index=False)
    pd.DataFrame(element_rows).to_csv(ROOT/"tables_v5"/"ood_element_frequency.csv",index=False)
    result={
        "rows":len(audit),"passed":sum(row["pass"] for row in audit),"failed":sum(not row["pass"] for row in audit),
        "definition":"Canonical chemical system is the sorted unique element-symbol set joined by hyphens. Entire groups are greedily assigned to source, target, or diagnostic roles using size deficit and a seed-hashed stable tie break.",
        "duplicate_compositions_and_polymorphs":"Records sharing an element set remain in one role. Exact duplicate material IDs are forbidden; distinct polymorph records remain records but cannot cross chemical-system roles.",
        "targets_used_for_assignment":False,
    }
    (ROOT/"audits_v4"/"ood_disjointness_summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")


if __name__=="__main__":
    main()
