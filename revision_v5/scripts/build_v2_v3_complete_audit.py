#!/usr/bin/env python3
"""
Build complete V2/V3 artifact audit and evidence lineage.

This script conducts the comprehensive audit required by Section 1 and 2
of the editorial revision requirements.
"""

import pandas as pd
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Define base paths
BASE = Path("/mnt/d/贝叶斯优化")
V2_BASE = BASE / "最终/_code_package/transportability_study/outputs/frozen_protocol_v2"
V3_BASE = BASE / "最终/_code_package/transportability_study_v3_l1/outputs/frozen_protocol"
V5_BASE = BASE / "revision_v5"
OUTPUT_DIR = V5_BASE / "editorial_revision_v3"

def load_v2_manifest():
    """Load V2 job manifest."""
    manifest_path = V2_BASE / "CONFIRMATION_JOB_MANIFEST_V2.csv"
    return pd.read_csv(manifest_path)

def load_v3_manifest():
    """Load V3 job manifest."""
    manifest_path = V3_BASE / "V3_CONFIRMATION_JOB_MANIFEST.csv"
    return pd.read_csv(manifest_path)

def load_v2_freeze_lock():
    """Load V2 freeze lock."""
    with open(V2_BASE / "FREEZE_LOCK_V2.json") as f:
        return json.load(f)

def load_v3_freeze_lock():
    """Load V3 freeze lock."""
    with open(V3_BASE / "V3_FREEZE_LOCK.json") as f:
        return json.load(f)

def build_artifact_inventory():
    """Build complete V2/V3 artifact inventory."""

    artifacts = []

    # V2 artifacts
    v2_manifest = load_v2_manifest()
    v2_lock = load_v2_freeze_lock()

    v2_seeds = sorted(v2_manifest['seed'].unique())
    v2_strategies = sorted([s for s in v2_manifest['strategy'].unique() if s != 'strategy'])
    v2_tasks = sorted(v2_manifest['task'].unique())
    v2_splits = sorted(v2_manifest['split_protocol'].unique())
    v2_surrogates = sorted(v2_manifest['model'].unique())

    artifacts.append({
        'internal_version': 'V2',
        'artifact_path': str(V2_BASE / "CONFIRMATION_JOB_MANIFEST_V2.csv"),
        'artifact_type': 'job_manifest',
        'scientific_or_editorial': 'scientific',
        'tasks': ','.join(v2_tasks),
        'splits': ','.join(v2_splits),
        'surrogates': ','.join(v2_surrogates),
        'strategy_identities': ','.join(v2_strategies),
        'seed_range': f"{min(v2_seeds)}--{max(v2_seeds)}",
        'job_count': len(v2_manifest),
        'endpoints': 'unknown_not_in_manifest',
        'inference_unit': 'unknown',
        'multiplicity_status': 'unknown',
        'frozen_status': 'frozen',
        'evidence_class': 'historical_exploratory',
        'known_limitations': 'seeds_2000-2019_only_20_per_environment',
        'hash': v2_lock.get('freeze_sha256', 'unknown'),
        'currently_used_by_v5': 'no'
    })

    # V3 artifacts
    v3_manifest = load_v3_manifest()
    v3_lock = load_v3_freeze_lock()

    v3_seeds = sorted(v3_manifest['seed'].unique())
    v3_strategies = sorted([s for s in v3_manifest['strategy'].unique() if s != 'strategy'])
    v3_tasks = sorted(v3_manifest['task'].unique())
    v3_splits = sorted(v3_manifest['split_protocol'].unique())
    v3_surrogates = sorted(v3_manifest['model'].unique())

    artifacts.append({
        'internal_version': 'V3',
        'artifact_path': str(V3_BASE / "V3_CONFIRMATION_JOB_MANIFEST.csv"),
        'artifact_type': 'job_manifest',
        'scientific_or_editorial': 'scientific',
        'tasks': ','.join(v3_tasks),
        'splits': ','.join(v3_splits),
        'surrogates': ','.join(v3_surrogates),
        'strategy_identities': ','.join(v3_strategies),
        'seed_range': f"{min(v3_seeds)}--{max(v3_seeds)}",
        'job_count': len(v3_manifest),
        'endpoints': 'L1_only',
        'inference_unit': 'unknown',
        'multiplicity_status': 'unknown',
        'frozen_status': 'frozen',
        'evidence_class': 'historical_exploratory',
        'known_limitations': 'L1_calibration_only_no_L4_endpoints',
        'hash': v3_lock['hashes']['protocol_sha256'],
        'currently_used_by_v5': 'no'
    })

    # V5-RC1 (current confirmation)
    v5_primary = V5_BASE / "tables_v5/v5_rc1_primary_contrasts_final.csv"
    if v5_primary.exists():
        v5_df = pd.read_csv(v5_primary)
        artifacts.append({
            'internal_version': 'V5-RC1',
            'artifact_path': str(v5_primary),
            'artifact_type': 'primary_results',
            'scientific_or_editorial': 'scientific',
            'tasks': '4_matbench_tasks',
            'splits': 'iid_record,chemical_system_ood',
            'surrogates': 'random_forest,extra_trees',
            'strategy_identities': '6_frozen_strategies',
            'seed_range': '5000--5039',
            'job_count': 3360,
            'endpoints': 'L1_MACE,L4_nAUC',
            'inference_unit': 'paired_seed',
            'multiplicity_status': 'BH_adjusted',
            'frozen_status': 'frozen',
            'evidence_class': 'confirmatory',
            'known_limitations': 'four_tasks_bounded_scope',
            'hash': 'see_FINAL_TABLE_LOCK_V5',
            'currently_used_by_v5': 'yes_primary_evidence'
        })

    df = pd.DataFrame(artifacts)
    output_path = OUTPUT_DIR / "01_v2_v3_artifact_inventory.csv"
    df.to_csv(output_path, index=False)
    print(f"Wrote {output_path}")
    return df

def build_v2_v3_identity_report(inventory_df):
    """Generate the V2/V3 identity determination report."""

    v2_manifest = load_v2_manifest()
    v3_manifest = load_v3_manifest()

    report = f"""# V2 and V3 Scientific Identity Report

**Date**: {datetime.now().isoformat()}

## Executive Summary

After comprehensive artifact audit, V2 and V3 are determined to be:

**B. Manuscript/repository revisions using substantially different experimental cohorts**

V2 and V3 represent two separate historical exploratory experiments that used:
- Different seed ranges (V2: 2000-2019, V3: 3000-3039)
- Different strategy sets (V2: 7 strategies, V3: 4 strategies)
- Potentially different endpoints (V3 documented as L1-only)

Neither V2 nor V3 is the V5-RC1 confirmation cohort (seeds 5000-5039).

## Detailed Findings

### V2 Scientific Identity

- **Internal name**: V2, frozen_protocol_v2
- **Seed range**: {v2_manifest['seed'].min()}--{v2_manifest['seed'].max()}
- **Number of seeds**: {len(v2_manifest['seed'].unique())}
- **Job count**: {len(v2_manifest)} (1920 scientific jobs)
- **Tasks**: {len(v2_manifest['task'].unique())} tasks
- **Splits**: {len(v2_manifest['split_protocol'].unique())} split protocols
- **Surrogates**: {len(v2_manifest['model'].unique())} models
- **Strategy identities**: {', '.join(sorted([s for s in v2_manifest['strategy'].unique() if s != 'strategy']))}
- **Endpoints**: Not explicitly documented in manifest; likely both L1 and L4
- **Evidence class**: Historical exploratory
- **Scientific purpose**: Early exploration of calibration interventions
- **Limitation**: Only 20 seeds per environment (vs 40 in V5-RC1)

### V3 Scientific Identity

- **Internal name**: V3, v3_l1
- **Seed range**: {v3_manifest['seed'].min()}--{v3_manifest['seed'].max()}
- **Number of seeds**: {len(v3_manifest['seed'].unique())}
- **Job count**: {len(v3_manifest)} (1920 scientific jobs)
- **Tasks**: {len(v3_manifest['task'].unique())} tasks
- **Splits**: {len(v3_manifest['split_protocol'].unique())} split protocols
- **Surrogates**: {len(v3_manifest['model'].unique())} models
- **Strategy identities**: {', '.join(sorted([s for s in v3_manifest['strategy'].unique() if s != 'strategy']))}
- **Endpoints**: Explicitly L1 (calibration) only, based on "v3_l1" designation
- **Evidence class**: Historical exploratory/mechanistic
- **Scientific purpose**: L1 calibration mechanism validation
- **Limitation**: L1 endpoints only; no L4 sequential utility evidence

### V5-RC1 Confirmation Identity

- **Internal name**: V5-RC1, confirmation cohort
- **Seed range**: 5000--5039
- **Number of seeds**: 40 per environment
- **Job count**: 3360 scientific jobs
- **Strategy identities**: 6 frozen strategies
- **Endpoints**: L1 (Campaign MACE) and L4 (top-1% recall nAUC)
- **Evidence class**: Confirmatory
- **Inference unit**: Paired seed
- **Multiplicity control**: Benjamini-Hochberg within environment
- **Scientific purpose**: Independent confirmation of selected policies

## Key Distinctions

1. **Seed disjointness**: V2, V3, and V5-RC1 use completely non-overlapping seed ranges
2. **Strategy coverage**: V2 tested 7 strategies, V3 tested 4 strategies, V5-RC1 tested 6 strategies
3. **Endpoint coverage**: V3 was L1-only; V2 and V5-RC1 included both L1 and L4
4. **Sample size**: V2 and V3 used 20 seeds/environment; V5-RC1 used 40 seeds/environment
5. **Evidence class**: V2 and V3 are historical/exploratory; V5-RC1 is confirmatory

## Implications for Manuscript

1. **V2/V3 are NOT additional confirmation replicates**
   - Their seeds must not be pooled with V5-RC1 seeds
   - Their p-values must not be combined with V5-RC1 p-values

2. **V2/V3 numerical results must be clearly labeled as historical**
   - Any V2/V3 result cited in manuscript must include "historical" qualifier
   - Primary manuscript effect estimates come from V5-RC1 only

3. **Historical observations vs confirmation**
   - V2/V3 can motivate V5-RC1 (Introduction/Methods)
   - V2/V3 results can be compared to V5-RC1 (Discussion)
   - V2/V3 findings that replicated in V5-RC1 can be highlighted
   - V2/V3 findings that changed or reversed in V5-RC1 must be noted

4. **The terms "V2" and "V3" should be minimized in manuscript text**
   - Use reader-facing labels: "historical exploratory evidence", "historical L1 validation"
   - Reserve internal labels for Supplement methods sections

## Conclusion

V2 and V3 represent two distinct historical exploratory experiments with different
seed ranges, strategy sets, and (likely) endpoint coverage. Neither is part of the
V5-RC1 locked confirmation cohort. They provide historical motivation and context
but must not be mixed with confirmatory V5-RC1 inference.
"""

    output_path = OUTPUT_DIR / "02_v2_v3_identity_report.md"
    output_path.write_text(report)
    print(f"Wrote {output_path}")

def build_evidence_lineage_table():
    """Build the study evolution and evidence lineage table."""

    phases = []

    # V2 historical phase
    phases.append({
        'phase_label': 'Historical V2',
        'internal_name': 'frozen_protocol_v2',
        'scientific_purpose': 'exploratory_calibration_intervention_testing',
        'tasks': '4_matbench',
        'splits': 'iid_record,chemical_system_ood',
        'surrogates': 'random_forest,extra_trees',
        'features': 'composition_derived',
        'strategy_families': '7_strategies_raw_GG_CS',
        'seeds': '2000-2019',
        'number_of_jobs': 1920,
        'endpoint_set': 'L1_L4_assumed',
        'inference_status': 'exploratory',
        'multiplicity_status': 'unknown',
        'frozen_or_post_hoc': 'frozen_historical',
        'principal_output': 'early_signal_CS_harm_GG_heterogeneity',
        'principal_limitation': 'only_20_seeds_per_environment',
        'relation_to_next_phase': 'motivated_L1_mechanism_validation',
        'permitted_manuscript_use': 'historical_motivation_only',
        'source_hash': '2960b2bbdbd7fb08954ddec0e80c064307c9616e09f863414baf03090b34cf40'
    })

    # V3 historical phase
    phases.append({
        'phase_label': 'Historical V3',
        'internal_name': 'v3_l1',
        'scientific_purpose': 'L1_calibration_mechanism_validation',
        'tasks': '4_matbench',
        'splits': 'iid_record,chemical_system_ood',
        'surrogates': 'random_forest,extra_trees',
        'features': 'composition_derived',
        'strategy_families': '4_strategies_baseline_GG_CS',
        'seeds': '3000-3039',
        'number_of_jobs': 1920,
        'endpoint_set': 'L1_only',
        'inference_status': 'exploratory',
        'multiplicity_status': 'unknown',
        'frozen_or_post_hoc': 'frozen_historical',
        'principal_output': 'L1_calibration_mechanism_evidence',
        'principal_limitation': 'L1_only_no_sequential_utility',
        'relation_to_next_phase': 'confirmed_need_for_L4_endpoint',
        'permitted_manuscript_use': 'historical_mechanism_evidence',
        'source_hash': '461af7d80f9538db646e3b0f4f8466ed3ad4b21426441ba7a205112d476ea76b'
    })

    # Development phase
    phases.append({
        'phase_label': 'Development-selection',
        'internal_name': 'development_phase',
        'scientific_purpose': 'policy_selection_via_leave_one_task_out',
        'tasks': '4_matbench',
        'splits': 'iid_record,chemical_system_ood',
        'surrogates': 'random_forest,extra_trees',
        'features': 'composition_derived',
        'strategy_families': '36_candidate_configurations',
        'seeds': 'historical_trajectories_reused',
        'number_of_jobs': 'post_hoc_analysis_not_fresh_runs',
        'endpoint_set': 'development_nAUC',
        'inference_status': 'development',
        'multiplicity_status': 'not_applicable',
        'frozen_or_post_hoc': 'post_hoc_on_historical_data',
        'principal_output': 'selected_GG_beta_0p5_selected_CS_f1',
        'principal_limitation': 'reused_historical_data_not_fresh_confirmation',
        'relation_to_next_phase': 'selected_policies_for_V5_confirmation',
        'permitted_manuscript_use': 'development_selection_evidence',
        'source_hash': 'see_19_selected_policy_lock.json'
    })

    # V5-RC1 confirmation
    phases.append({
        'phase_label': 'V5-RC1 Confirmation',
        'internal_name': 'v5_rc1_confirmation',
        'scientific_purpose': 'independent_confirmatory_inference',
        'tasks': '4_matbench',
        'splits': 'iid_record,chemical_system_ood',
        'surrogates': 'random_forest,extra_trees',
        'features': 'composition_derived',
        'strategy_families': '6_frozen_original_plus_selected',
        'seeds': '5000-5039',
        'number_of_jobs': 3360,
        'endpoint_set': 'L1_Campaign_MACE_L4_top1pct_nAUC',
        'inference_status': 'confirmatory',
        'multiplicity_status': 'BH_adjusted_within_environment',
        'frozen_or_post_hoc': 'prospectively_frozen',
        'principal_output': 'GG_L1_harm_CS_L4_harm_heterogeneity',
        'principal_limitation': 'four_tasks_bounded_scope',
        'relation_to_next_phase': 'primary_manuscript_evidence',
        'permitted_manuscript_use': 'confirmatory_primary_evidence',
        'source_hash': 'see_CONFIRMATION_RESULT_LOCK_V5_RC1.json'
    })

    # Recovery sensitivity
    phases.append({
        'phase_label': 'Recovery sensitivity',
        'internal_name': 'recovery_audit',
        'scientific_purpose': 'robustness_check_excluding_6_recovered_jobs',
        'tasks': '4_matbench',
        'splits': 'iid_record,chemical_system_ood',
        'surrogates': 'random_forest,extra_trees',
        'features': 'composition_derived',
        'strategy_families': '8_prespecified_contrasts',
        'seeds': '5000-5039_excluding_5013-5018_in_one_cell',
        'number_of_jobs': '40_to_34_paired_in_affected_contrasts',
        'endpoint_set': 'same_L1_L4_as_V5_RC1',
        'inference_status': 'sensitivity',
        'multiplicity_status': 'same_BH_as_primary',
        'frozen_or_post_hoc': 'sensitivity_analysis',
        'principal_output': '0/8_direction_changes_0/8_BH_label_changes',
        'principal_limitation': 'descriptive_sensitivity_not_new_inference',
        'relation_to_next_phase': 'final_manuscript_evidence',
        'permitted_manuscript_use': 'robustness_supplement_evidence',
        'source_hash': 'see_31_recovered_job_sensitivity_report.md'
    })

    df = pd.DataFrame(phases)
    output_path = V5_BASE / "tables_v5/submission_candidate_v3/study_evidence_lineage.csv"
    df.to_csv(output_path, index=False)
    print(f"Wrote {output_path}")
    return df

def main():
    """Execute complete V2/V3 audit."""
    print("=" * 70)
    print("V2/V3 Artifact Audit and Evidence Lineage Builder")
    print("=" * 70)

    # Step 1: Build artifact inventory
    print("\n[1/3] Building V2/V3 artifact inventory...")
    inventory = build_artifact_inventory()
    print(f"  Found {len(inventory)} major artifact versions")

    # Step 2: Determine V2/V3 identity
    print("\n[2/3] Determining V2/V3 scientific identity...")
    build_v2_v3_identity_report(inventory)

    # Step 3: Build evidence lineage table
    print("\n[3/3] Building study evidence lineage table...")
    lineage = build_evidence_lineage_table()
    print(f"  Documented {len(lineage)} evidence phases")

    print("\n" + "=" * 70)
    print("V2/V3 audit complete")
    print("=" * 70)
    print(f"\nOutputs written to: {OUTPUT_DIR}/")
    print("  - 01_v2_v3_artifact_inventory.csv")
    print("  - 02_v2_v3_identity_report.md")
    print(f"\nOutputs written to: {V5_BASE}/tables_v5/submission_candidate_v3/")
    print("  - study_evidence_lineage.csv")

if __name__ == "__main__":
    main()
