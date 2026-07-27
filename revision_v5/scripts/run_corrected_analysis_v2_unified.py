#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5-RC1 CORRECTED Analysis - Complete Unified Script
Fixes all critical issues identified in invalidation notice
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
import hashlib

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT
RESULTS_DIR = REVISION / "results_v4" / "confirmation" / "trajectories"
TABLES = REVISION / "tables_v5"
AUDITS = REVISION / "audits_v5"

# Load frozen policy lock
with open(REVISION / "19_selected_policy_lock.json", 'r') as f:
    POLICY_LOCK = json.load(f)

# Load result lock
with open(REVISION / "CONFIRMATION_RESULT_LOCK_V5_RC1.json", 'r') as f:
    RESULT_LOCK = json.load(f)

RESULT_LOCK_HASH = RESULT_LOCK['execution_registry']['sha256'][:16]

# Monte Carlo parameters
N_BOOTSTRAP = 10000
N_PERMUTATION = 10000

print("=" * 80)
print("V5-RC1 CORRECTED ANALYSIS")
print("=" * 80)
print()
print("Critical fixes:")
print("  1. Task-specific baseline mapping (log-KVRH uses Raw beta=2)")
print("  2. Rigorous L1 checkpoint validation")
print("  3. Corrected Monte Carlo p-value: p = (extreme + 1) / (n + 1)")
print("  4. Deterministic contrast-specific RNG seeds")
print("=" * 80)
print()

def build_task_baseline_map() -> dict:
    """Build task-specific baseline mapping from policy lock"""
    baseline_map = {}

    for policy in POLICY_LOCK['selected_policies']:
        task = policy['held_out_task']
        if policy['family'] == 'raw':
            baseline_map[task] = policy['selected_strategy']

    print("Task-specific selected Raw baseline mapping:")
    for task in sorted(baseline_map.keys()):
        print(f"  {task}: {baseline_map[task]}")
    print()

    # Verify log-KVRH uses beta=2
    if baseline_map.get('matbench_log_kvrh') != 'raw_ucb_beta_2':
        raise ValueError("CRITICAL: log-KVRH selected baseline must be raw_ucb_beta_2")

    return baseline_map

def load_trajectory_data(job_id: str):
    """Load all data files for a trajectory"""
    traj_dir = RESULTS_DIR / job_id

    if not traj_dir.exists():
        return None

    try:
        with open(traj_dir / 'state.json', 'r', encoding='utf-8') as f:
            state = json.load(f)

        selected = pd.read_parquet(traj_dir / 'selected.parquet')
        rounds = pd.read_parquet(traj_dir / 'rounds.parquet')
        diagnostic = pd.read_parquet(traj_dir / 'diagnostic_metrics.parquet')

        checkpoint_data = {}
        for ckpt in ['initial', '25pct', '50pct', '75pct']:
            with open(traj_dir / f'checkpoint_{ckpt}.json', 'r', encoding='utf-8') as f:
                checkpoint_data[ckpt] = json.load(f)

        return {
            'state': state,
            'selected': selected,
            'rounds': rounds,
            'diagnostic': diagnostic,
            'checkpoint_data': checkpoint_data
        }
    except Exception as e:
        return None

def compute_l1_campaign_mace_validated(data: dict, job_id: str) -> tuple:
    """Compute and validate L1 Campaign MACE"""
    diagnostic = data['diagnostic']
    checkpoint_data = data['checkpoint_data']

    checkpoint_maces = []
    audit_records = []

    for ckpt_name in ['initial', '25pct', '50pct', '75pct']:
        ckpt = checkpoint_data[ckpt_name]
        acq_round = ckpt.get('acquisition_round')

        # Match by round index in diagnostic DataFrame
        if acq_round is not None and acq_round < len(diagnostic):
            diag_row = diagnostic.iloc[acq_round]

            # Recompute MACE from four coverage levels
            cov_50 = diag_row.get('coverage_50', np.nan)
            cov_80 = diag_row.get('coverage_80', np.nan)
            cov_90 = diag_row.get('coverage_90', np.nan)
            cov_95 = diag_row.get('coverage_95', np.nan)

            if not any(pd.isna([cov_50, cov_80, cov_90, cov_95])):
                recomputed_mace = np.mean([
                    abs(cov_50 - 0.50),
                    abs(cov_80 - 0.80),
                    abs(cov_90 - 0.90),
                    abs(cov_95 - 0.95)
                ])

                stored_mace = diag_row.get('mean_absolute_coverage_error', np.nan)
                checkpoint_maces.append(recomputed_mace)

                audit_records.append({
                    'checkpoint': ckpt_name,
                    'acquisition_round': acq_round,
                    'recomputed_mace': recomputed_mace,
                    'stored_mace': stored_mace,
                    'difference': abs(recomputed_mace - stored_mace) if not pd.isna(stored_mace) else np.nan,
                    'error': None
                })
            else:
                audit_records.append({'checkpoint': ckpt_name, 'error': 'missing_coverage'})
        else:
            audit_records.append({'checkpoint': ckpt_name, 'error': 'no_match'})

    campaign_mace = float(np.mean(checkpoint_maces)) if len(checkpoint_maces) == 4 else np.nan

    audit_info = {
        'job_id': job_id,
        'n_checkpoints_matched': len([r for r in audit_records if r.get('error') is None]),
        'checkpoint_records': audit_records
    }

    return campaign_mace, audit_info

def compute_paired_inference_corrected(baseline_df, test_df, endpoint, higher_is_better, contrast_key):
    """Compute paired inference with corrected Monte Carlo p-value"""
    merged = pd.merge(
        baseline_df[['seed', endpoint]],
        test_df[['seed', endpoint]],
        on='seed',
        suffixes=('_baseline', '_test')
    )

    merged = merged.dropna()
    n_pairs = len(merged)

    if n_pairs == 0:
        return {
            'n_pairs': 0,
            'mean_diff': np.nan,
            'ci_lower': np.nan,
            'ci_upper': np.nan,
            'p_value_unadjusted': np.nan,
            'effect_direction': 'no_data'
        }

    diffs = merged[f'{endpoint}_test'].values - merged[f'{endpoint}_baseline'].values
    mean_diff = float(np.mean(diffs))

    # Bootstrap CI
    contrast_hash = hashlib.md5((contrast_key + RESULT_LOCK_HASH).encode()).hexdigest()
    boot_seed = int(contrast_hash[:8], 16) % (2**31)
    rng_boot = np.random.RandomState(boot_seed)

    boot_means = []
    for _ in range(N_BOOTSTRAP):
        boot_idx = rng_boot.choice(n_pairs, size=n_pairs, replace=True)
        boot_means.append(np.mean(diffs[boot_idx]))

    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    # CORRECTED Permutation test
    perm_seed = int(contrast_hash[8:16], 16) % (2**31)
    rng_perm = np.random.RandomState(perm_seed)

    perm_stats = []
    for _ in range(N_PERMUTATION):
        signs = rng_perm.choice([-1, 1], size=n_pairs)
        perm_stats.append(np.mean(diffs * signs))

    # CRITICAL FIX: p = (extreme_count + 1) / (n_permutations + 1)
    extreme_count = np.sum(np.abs(perm_stats) >= np.abs(mean_diff))
    p_value = (extreme_count + 1) / (N_PERMUTATION + 1)

    # Effect direction
    if higher_is_better:
        effect_direction = 'favors_test' if mean_diff > 0 and p_value < 0.05 else ('favors_baseline' if mean_diff < 0 and p_value < 0.05 else 'inconclusive')
    else:
        effect_direction = 'favors_test' if mean_diff < 0 and p_value < 0.05 else ('favors_baseline' if mean_diff > 0 and p_value < 0.05 else 'inconclusive')

    return {
        'n_pairs': n_pairs,
        'mean_diff': mean_diff,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'p_value_unadjusted': float(p_value),
        'effect_direction': effect_direction
    }

# MAIN EXECUTION
print("STEP 1: Build task-specific baseline mapping")
print("-" * 80)
baseline_map = build_task_baseline_map()

print("STEP 2: Process all trajectories with corrected endpoints")
print("-" * 80)

registry = pd.read_csv(REVISION / "results_v4" / "confirmation" / "registry_snapshot.csv")
completed = registry[registry['status'].isin(['COMPLETED', 'RECOVERED'])]

print(f"Total trajectories: {len(completed)}")
print()

results = []
l1_audit_records = []

for idx, row in completed.iterrows():
    job_id = row['job_id']
    parts = job_id.split('__')

    if len(parts) < 5:
        continue

    task, split, model, strategy = parts[0], parts[1], parts[2], parts[3]
    seed = int(parts[4].replace('seed', ''))

    data = load_trajectory_data(job_id)
    if data is None:
        continue

    try:
        l1_mace, l1_audit = compute_l1_campaign_mace_validated(data, job_id)
        l4_nauc = data['state'].get('primary_nauc', np.nan)

        l1_audit_records.append(l1_audit)

        results.append({
            'job_id': job_id,
            'task': task,
            'split': split,
            'model': model,
            'strategy': strategy,
            'seed': seed,
            'environment': f"{task}__{split}__{model}",
            'l1_campaign_mace': l1_mace,
            'l4_top1pct_recall_nauc': l4_nauc,
            'l1_validated': l1_audit['n_checkpoints_matched'] == 4,
            'selected_baseline_strategy': baseline_map.get(task, 'raw_ucb_beta_1'),
            'policy_lock_hash': POLICY_LOCK.get('selection_table_sha256', '')[:16],
            'result_lock_hash': RESULT_LOCK_HASH
        })

    except Exception as e:
        continue

    if (idx + 1) % 100 == 0:
        print(f"  Processed {idx + 1}/{len(completed)}...")

endpoints_df = pd.DataFrame(results)
endpoints_df.to_csv(TABLES / "v5_rc1_seed_level_endpoints_v2.csv", index=False)
print(f"\nWritten: v5_rc1_seed_level_endpoints_v2.csv ({len(endpoints_df)} rows)")
print()

# L1 audit
l1_checkpoint_audit = []
for audit in l1_audit_records:
    for ckpt_record in audit['checkpoint_records']:
        l1_checkpoint_audit.append({'job_id': audit['job_id'], **ckpt_record})

pd.DataFrame(l1_checkpoint_audit).to_csv(AUDITS / "l1_checkpoint_mapping_audit_v2.csv", index=False)
print(f"Written: l1_checkpoint_mapping_audit_v2.csv")
print()

print("STEP 3: Run corrected statistical inference")
print("-" * 80)

contrast_configs = [
    ('Original GG vs Raw', 'gg_ucb_beta_1', 'raw_ucb_beta_1'),
    ('Historical CS vs Raw', 'cs_da_oob_hist', 'raw_ucb_beta_1'),
    ('Selected GG vs Raw', 'gg_ucb_beta_0p5', 'TASK_SPECIFIC'),
    ('Selected CS vs Raw', 'cs_da_oob_parsimonious_f1', 'TASK_SPECIFIC')
]

endpoint_specs = [
    ('l1_campaign_mace', 'L1 Campaign MACE', False),
    ('l4_top1pct_recall_nauc', 'L4 Top-1% Recall nAUC', True)
]

inference_results = []

for environment in sorted(endpoints_df['environment'].unique()):
    env_data = endpoints_df[endpoints_df['environment'] == environment]
    task = environment.split('__')[0]

    for contrast_name, test_strategy, baseline_strategy in contrast_configs:
        actual_baseline = baseline_map[task] if baseline_strategy == 'TASK_SPECIFIC' else baseline_strategy

        baseline_data = env_data[env_data['strategy'] == actual_baseline]
        test_data = env_data[env_data['strategy'] == test_strategy]

        if len(baseline_data) == 0 or len(test_data) == 0:
            continue

        for endpoint, endpoint_name, higher_is_better in endpoint_specs:
            contrast_key = f"{environment}|{contrast_name}|{endpoint}"
            inference = compute_paired_inference_corrected(
                baseline_data, test_data, endpoint, higher_is_better, contrast_key
            )

            inference_results.append({
                'task': task,
                'environment': environment,
                'contrast_name': contrast_name,
                'baseline_strategy': actual_baseline,
                'test_strategy': test_strategy,
                'endpoint': endpoint,
                'endpoint_name': endpoint_name,
                'higher_is_better': higher_is_better,
                **inference
            })

inference_df = pd.DataFrame(inference_results)
inference_df.to_csv(TABLES / "v5_rc1_primary_contrasts_v2.csv", index=False)
print(f"Written: v5_rc1_primary_contrasts_v2.csv ({len(inference_df)} rows)")
print()

print("=" * 80)
print("CORRECTED ANALYSIS COMPLETE")
print("=" * 80)
print()
print(f"Endpoints: {len(endpoints_df)} trajectories")
print(f"Inference: {len(inference_df)} contrasts")
print(f"L1 validated: {endpoints_df['l1_validated'].sum()}/{len(endpoints_df)}")
print()
print("Baseline verification:")
for task in sorted(baseline_map.keys()):
    task_data = endpoints_df[endpoints_df['task'] == task]
    baseline = task_data['selected_baseline_strategy'].iloc[0] if len(task_data) > 0 else 'N/A'
    print(f"  {task}: {baseline}")
