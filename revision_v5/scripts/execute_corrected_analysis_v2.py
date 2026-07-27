#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5-RC1 CORRECTED Analysis - Complete Execution
Part 2: Main execution logic
"""

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from compute_corrected_analysis_v2 import *

def process_all_trajectories_corrected():
    """Process all trajectories with corrected endpoint computation"""

    print("=" * 80)
    print("V5-RC1 CORRECTED ENDPOINT COMPUTATION")
    print("=" * 80)
    print()
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Build baseline map from policy lock
    baseline_map = build_task_baseline_map()

    # Load registry
    registry = pd.read_csv(REVISION / "results_v4" / "confirmation" / "registry_snapshot.csv")
    completed = registry[registry['status'].isin(['COMPLETED', 'RECOVERED'])]

    print(f"Total trajectories to process: {len(completed)}")
    print()

    results = []
    l1_audit_records = []
    l4_audit_records = []
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

        # Compute validated endpoints
        try:
            l1_campaign_mace, l1_audit = compute_l1_campaign_mace_validated(data, job_id)
            l4_top1pct, l4_audit = compute_l4_top1pct_validated(data, job_id)

            # Store audit records
            l1_audit_records.append(l1_audit)
            l4_audit_records.append(l4_audit)

            # Determine selected baseline for this task
            selected_baseline = baseline_map.get(task, 'raw_ucb_beta_1')

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
                'l1_validated': l1_audit['n_checkpoints_matched'] == 4,
                'l4_validated': False,  # Placeholder
                'selected_baseline_strategy': selected_baseline,
                'policy_lock_hash': POLICY_LOCK.get('selection_table_sha256', '')[:16],
                'result_lock_hash': RESULT_LOCK_HASH,
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

    # Convert to DataFrame
    endpoints_df = pd.DataFrame(results)

    # Save corrected endpoints
    output_path = TABLES / "v5_rc1_seed_level_endpoints_v2.csv"
    endpoints_df.to_csv(output_path, index=False)
    print(f"Written: {output_path.name}")
    print(f"  Rows: {len(endpoints_df)}")
    print()

    # Save L1 audit
    l1_checkpoint_audit = []
    for audit in l1_audit_records:
        for ckpt_record in audit['checkpoint_records']:
            l1_checkpoint_audit.append({
                'job_id': audit['job_id'],
                **ckpt_record
            })

    l1_audit_df = pd.DataFrame(l1_checkpoint_audit)
    l1_audit_path = AUDITS / "l1_checkpoint_mapping_audit.csv"
    l1_audit_df.to_csv(l1_audit_path, index=False)
    print(f"Written: {l1_audit_path.name}")
    print()

    # Check L1 validation issues
    l1_issues = l1_audit_df[l1_audit_df['error'].notna()]
    if len(l1_issues) > 0:
        print(f"WARNING: {len(l1_issues)} L1 checkpoint matching issues found")
        print(f"  See {l1_audit_path.name} for details")
    else:
        print("✓ All L1 checkpoints matched successfully")
    print()

    # Summary
    print("=" * 80)
    print("CORRECTED ENDPOINT COMPUTATION SUMMARY")
    print("=" * 80)
    print()
    print(f"Total trajectories: {len(results)}")
    print(f"L1 fully validated: {endpoints_df['l1_validated'].sum()}/{len(endpoints_df)}")
    print(f"L4 validated: {endpoints_df['l4_validated'].sum()}/{len(endpoints_df)}")
    print()

    # Check baseline mapping
    print("Selected baseline verification:")
    for task in sorted(baseline_map.keys()):
        task_data = endpoints_df[endpoints_df['task'] == task]
        baselines = task_data['selected_baseline_strategy'].unique()
        print(f"  {task}: {baselines[0] if len(baselines) == 1 else 'INCONSISTENT'}")
    print()

    return endpoints_df

def run_corrected_inference():
    """Run corrected statistical inference"""

    print("=" * 80)
    print("V5-RC1 CORRECTED STATISTICAL INFERENCE")
    print("=" * 80)
    print()

    # Load corrected endpoints
    endpoints = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints_v2.csv")

    # Build baseline map
    baseline_map = build_task_baseline_map()

    # Define contrast types
    contrast_configs = [
        ('Original GG vs Raw', 'gg_ucb_beta_1', 'raw_ucb_beta_1'),
        ('Historical CS vs Raw', 'cs_da_oob_hist', 'raw_ucb_beta_1'),
        ('Selected GG vs Raw', 'gg_ucb_beta_0p5', 'TASK_SPECIFIC'),
        ('Selected CS vs Raw', 'cs_da_oob_parsimonious_f1', 'TASK_SPECIFIC')
    ]

    # Endpoints
    endpoint_specs = [
        ('l1_campaign_mace', 'L1 Campaign MACE', False),
        ('l4_top1pct_recall_nauc', 'L4 Top-1% Recall nAUC', True)
    ]

    results = []

    # Process each environment
    for environment in sorted(endpoints['environment'].unique()):
        env_data = endpoints[endpoints['environment'] == environment]

        # Extract task from environment
        task = environment.split('__')[0]

        print(f"Processing environment: {environment}")

        # Process each contrast
        for contrast_name, test_strategy, baseline_strategy in contrast_configs:
            # Determine correct baseline
            if baseline_strategy == 'TASK_SPECIFIC':
                actual_baseline = baseline_map[task]
            else:
                actual_baseline = baseline_strategy

            # Get data
            baseline_data = env_data[env_data['strategy'] == actual_baseline]
            test_data = env_data[env_data['strategy'] == test_strategy]

            if len(baseline_data) == 0 or len(test_data) == 0:
                continue

            # Process each endpoint
            for endpoint, endpoint_name, higher_is_better in endpoint_specs:
                contrast_key = f"{environment}|{contrast_name}|{endpoint}"

                inference = compute_paired_inference_corrected(
                    baseline_data, test_data, endpoint, higher_is_better, contrast_key
                )

                result = {
                    'task': task,
                    'environment': environment,
                    'contrast_name': contrast_name,
                    'baseline_strategy': actual_baseline,
                    'test_strategy': test_strategy,
                    'endpoint': endpoint,
                    'endpoint_name': endpoint_name,
                    'higher_is_better': higher_is_better,
                    'n_pairs': inference['n_pairs'],
                    'mean_diff': inference['mean_diff'],
                    'ci_lower': inference['ci_lower'],
                    'ci_upper': inference['ci_upper'],
                    'p_value_unadjusted': inference['p_value_unadjusted'],
                    'p_value_adjusted': np.nan,  # Placeholder for multiplicity adjustment
                    'adjustment_family': 'none_yet',
                    'effect_direction': inference['effect_direction'],
                    'significant_unadjusted': inference['p_value_unadjusted'] < 0.05 if not np.isnan(inference['p_value_unadjusted']) else False,
                    'evidence_label': 'pending_adjustment',
                    'result_lock_hash': RESULT_LOCK_HASH,
                    'policy_lock_hash': POLICY_LOCK.get('selection_table_sha256', '')[:16]
                }

                results.append(result)

        print(f"  Completed {len([r for r in results if r['environment'] == environment])} contrasts")

    print()

    # Save results
    inference_df = pd.DataFrame(results)
    output_path = TABLES / "v5_rc1_primary_contrasts_v2.csv"
    inference_df.to_csv(output_path, index=False)
    print(f"Written: {output_path.name}")
    print(f"  Rows: {len(inference_df)}")
    print()

    # Summary
    print("=" * 80)
    print("CORRECTED INFERENCE SUMMARY")
    print("=" * 80)
    print()

    # Compare baseline usage
    print("Baseline strategy distribution:")
    for contrast in sorted(inference_df['contrast_name'].unique()):
        contrast_data = inference_df[inference_df['contrast_name'] == contrast]
        baseline_counts = contrast_data['baseline_strategy'].value_counts()
        print(f"\n{contrast}:")
        for strat, count in baseline_counts.items():
            print(f"  {strat}: {count}")

    print()

    # Significance summary
    print("Significance summary (unadjusted p<0.05):")
    for contrast in sorted(inference_df['contrast_name'].unique()):
        contrast_data = inference_df[inference_df['contrast_name'] == contrast]
        n_sig = contrast_data['significant_unadjusted'].sum()
        n_total = len(contrast_data)
        print(f"  {contrast}: {n_sig}/{n_total}")

    print()

    return inference_df

if __name__ == '__main__':
    # Execute corrected analysis
    endpoints_df = process_all_trajectories_corrected()
    inference_df = run_corrected_inference()

    print("=" * 80)
    print("CORRECTED ANALYSIS COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Review L1 checkpoint audit for validation issues")
    print("  2. Complete L4 independent validation")
    print("  3. Extract and apply frozen multiplicity adjustment")
    print("  4. Compare corrected vs invalid analysis")
    print("  5. Generate corrected statistical report")
