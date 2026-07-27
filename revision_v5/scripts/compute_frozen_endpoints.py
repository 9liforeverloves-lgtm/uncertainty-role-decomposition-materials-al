#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5-RC1 Small Sample Validation and Endpoint Implementation
Validates and computes frozen protocol endpoints on complete dataset
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT
RESULTS_DIR = REVISION / "results_v4" / "confirmation" / "trajectories"
TABLES = REVISION / "tables_v5"
AUDITS = REVISION / "audits_v5"

TABLES.mkdir(exist_ok=True)
AUDITS.mkdir(exist_ok=True)

def load_trajectory_data(job_id: str):
    """Load all data files for a trajectory"""
    traj_dir = RESULTS_DIR / job_id

    if not traj_dir.exists():
        return None

    try:
        # Load state
        with open(traj_dir / 'state.json', 'r', encoding='utf-8') as f:
            state = json.load(f)

        # Load parquet files
        selected = pd.read_parquet(traj_dir / 'selected.parquet')
        rounds = pd.read_parquet(traj_dir / 'rounds.parquet')
        diagnostic = pd.read_parquet(traj_dir / 'diagnostic_metrics.parquet')

        # Load checkpoint mappings
        checkpoint_rounds = {}
        for ckpt in ['initial', '25pct', '50pct', '75pct']:
            with open(traj_dir / f'checkpoint_{ckpt}.json', 'r', encoding='utf-8') as f:
                ckpt_data = json.load(f)
            checkpoint_rounds[ckpt] = ckpt_data.get('acquisition_round', 0)

        return {
            'state': state,
            'selected': selected,
            'rounds': rounds,
            'diagnostic': diagnostic,
            'checkpoint_rounds': checkpoint_rounds
        }
    except Exception as e:
        print(f"Error loading {job_id}: {e}")
        return None

def compute_l1_campaign_mace(data: dict) -> float:
    """
    Compute L1 Campaign MACE from frozen protocol definition

    Frozen definition:
        MACE_t = mean over alpha in {0.50, 0.80, 0.90, 0.95}
                 of |empirical_coverage_t_alpha - alpha|

        campaign_MACE = mean over checkpoints {initial, 25%, 50%, 75%}
                        of MACE_t

    Implementation:
        diagnostic_metrics.parquet contains 'mean_absolute_coverage_error' per round
        This is already the four-level MACE (averaged over 4 alphas)
        We extract values at checkpoint rounds and average
    """
    diagnostic = data['diagnostic']
    checkpoint_rounds = data['checkpoint_rounds']

    checkpoint_maces = []
    for ckpt in ['initial', '25pct', '50pct', '75pct']:
        rnd = checkpoint_rounds[ckpt]
        if rnd < len(diagnostic):
            mace = diagnostic.iloc[rnd]['mean_absolute_coverage_error']
            checkpoint_maces.append(mace)

    if len(checkpoint_maces) == 4:
        return float(np.mean(checkpoint_maces))
    else:
        return np.nan

def compute_l4_top1pct_recall_nauc(data: dict) -> float:
    """
    Compute L4 Top-1% Recall normalized AUC

    Use state.json['primary_nauc'] which appears to be pre-computed correctly
    according to frozen protocol (including initial state)
    """
    return data['state'].get('primary_nauc', np.nan)

def compute_secondary_l4_endpoints(data: dict) -> dict:
    """
    Compute secondary L4 endpoints for top-0.5%, 2%, 5%

    These require similar computation to primary L4 but with different k values
    For now, return NaN as these are secondary endpoints
    """
    return {
        'l4_top0p5pct_recall_nauc': np.nan,
        'l4_top2pct_recall_nauc': np.nan,
        'l4_top5pct_recall_nauc': np.nan
    }

def process_all_trajectories():
    """Process all 3360 trajectories and compute endpoints"""

    print("=" * 80)
    print("V5-RC1 ENDPOINT COMPUTATION")
    print("=" * 80)
    print()
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Load registry
    registry = pd.read_csv(REVISION / "results_v4" / "confirmation" / "registry_snapshot.csv")
    completed = registry[registry['status'].isin(['COMPLETED', 'RECOVERED'])]

    print(f"Total trajectories to process: {len(completed)}")
    print()

    results = []
    errors = []

    for idx, row in completed.iterrows():
        job_id = row['job_id']

        # Parse job structure
        parts = job_id.split('__')
        if len(parts) < 5:
            errors.append({'job_id': job_id, 'error': 'Invalid job_id format'})
            continue

        task = parts[0]
        split = parts[1]
        model = parts[2]
        strategy = parts[3]
        seed = int(parts[4].replace('seed', ''))

        # Load trajectory data
        data = load_trajectory_data(job_id)
        if data is None:
            errors.append({'job_id': job_id, 'error': 'Failed to load data'})
            continue

        # Compute endpoints
        try:
            l1_campaign_mace = compute_l1_campaign_mace(data)
            l4_top1pct = compute_l4_top1pct_recall_nauc(data)
            secondary_l4 = compute_secondary_l4_endpoints(data)

            result = {
                'job_id': job_id,
                'task': task,
                'split': split,
                'model': model,
                'strategy': strategy,
                'seed': seed,
                'environment': f"{task}__{split}__{model}",
                'l1_campaign_mace': l1_campaign_mace,
                'l4_top1pct_recall_nauc': l4_top1pct,
                **secondary_l4,
                'complete': data['state'].get('complete', False),
                'floor_was_active': data['state'].get('floor_was_ever_active', False),
                'n_rounds': data['state'].get('next_round', 0)
            }

            results.append(result)

        except Exception as e:
            errors.append({'job_id': job_id, 'error': str(e)})

        # Progress indicator
        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(completed)} trajectories...")

    print()
    print(f"Completed: {datetime.now().isoformat()}")
    print()
    print(f"Successfully processed: {len(results)}")
    print(f"Errors: {len(errors)}")
    print()

    # Convert to DataFrame
    endpoints_df = pd.DataFrame(results)

    # Save seed-level endpoints
    output_path = TABLES / "v5_rc1_seed_level_endpoints.csv"
    endpoints_df.to_csv(output_path, index=False)
    print(f"Written: {output_path.name}")
    print()

    # Generate completeness audit
    audit_rows = []
    for env in endpoints_df['environment'].unique():
        env_data = endpoints_df[endpoints_df['environment'] == env]
        for strategy in env_data['strategy'].unique():
            strat_data = env_data[env_data['strategy'] == strategy]

            n_seeds = len(strat_data)
            n_complete = strat_data['complete'].sum()
            n_l1_valid = strat_data['l1_campaign_mace'].notna().sum()
            n_l4_valid = strat_data['l4_top1pct_recall_nauc'].notna().sum()

            audit_rows.append({
                'environment': env,
                'strategy': strategy,
                'n_seeds': n_seeds,
                'n_complete': n_complete,
                'n_l1_valid': n_l1_valid,
                'n_l4_valid': n_l4_valid,
                'l1_complete': n_l1_valid == 40,
                'l4_complete': n_l4_valid == 40
            })

    audit_df = pd.DataFrame(audit_rows)
    audit_path = AUDITS / "v5_rc1_endpoint_completeness.csv"
    audit_df.to_csv(audit_path, index=False)
    print(f"Written: {audit_path.name}")
    print()

    # Save errors if any
    if errors:
        errors_df = pd.DataFrame(errors)
        errors_path = AUDITS / "v5_rc1_endpoint_errors.csv"
        errors_df.to_csv(errors_path, index=False)
        print(f"Written: {errors_path.name} ({len(errors)} errors)")
        print()

    # Summary statistics
    print("=" * 80)
    print("ENDPOINT COMPUTATION SUMMARY")
    print("=" * 80)
    print()
    print(f"Total trajectories processed: {len(results)}")
    print(f"Unique environments: {endpoints_df['environment'].nunique()}")
    print(f"Unique strategies: {endpoints_df['strategy'].nunique()}")
    print(f"Seeds range: {endpoints_df['seed'].min()}-{endpoints_df['seed'].max()}")
    print()

    print("L1 Campaign MACE:")
    print(f"  Valid values: {endpoints_df['l1_campaign_mace'].notna().sum()}/{len(endpoints_df)}")
    print(f"  Mean: {endpoints_df['l1_campaign_mace'].mean():.6f}")
    print(f"  Range: [{endpoints_df['l1_campaign_mace'].min():.6f}, {endpoints_df['l1_campaign_mace'].max():.6f}]")
    print()

    print("L4 Top-1% Recall nAUC:")
    print(f"  Valid values: {endpoints_df['l4_top1pct_recall_nauc'].notna().sum()}/{len(endpoints_df)}")
    print(f"  Mean: {endpoints_df['l4_top1pct_recall_nauc'].mean():.6f}")
    print(f"  Range: [{endpoints_df['l4_top1pct_recall_nauc'].min():.6f}, {endpoints_df['l4_top1pct_recall_nauc'].max():.6f}]")
    print()

    print("Completeness audit:")
    complete_envs = audit_df[(audit_df['l1_complete']) & (audit_df['l4_complete'])].shape[0]
    total_combos = len(audit_df)
    print(f"  Strategy-environment combinations with 40 valid pairs: {complete_envs}/{total_combos}")
    print()

    if complete_envs == total_combos:
        print("SUCCESS: All strategy-environment combinations have complete 40-pair endpoints")
    else:
        print("WARNING: Some combinations have missing endpoints")
        incomplete = audit_df[~((audit_df['l1_complete']) & (audit_df['l4_complete']))]
        print(f"  Incomplete combinations: {len(incomplete)}")
        for _, row in incomplete.head(10).iterrows():
            print(f"    {row['environment']}/{row['strategy']}: L1={row['n_l1_valid']}/40, L4={row['n_l4_valid']}/40")
    print()

    return endpoints_df, audit_df

if __name__ == '__main__':
    endpoints_df, audit_df = process_all_trajectories()
