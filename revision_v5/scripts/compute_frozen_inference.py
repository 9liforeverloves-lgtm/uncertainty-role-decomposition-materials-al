#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5-RC1 Frozen Statistical Inference
Performs paired bootstrap and permutation inference on locked endpoints
"""

from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT
TABLES = REVISION / "tables_v5"
AUDITS = REVISION / "audits_v5"

# Bootstrap and permutation parameters from frozen protocol
N_BOOTSTRAP = 10000
N_PERMUTATION = 10000
CI_LEVEL = 0.95

def compute_paired_inference(baseline_df: pd.DataFrame, test_df: pd.DataFrame,
                             endpoint: str, higher_is_better: bool) -> dict:
    """
    Compute paired statistical inference for one contrast

    Returns:
        - n_pairs: number of valid paired seeds
        - mean_diff: mean paired difference (test - baseline)
        - ci_lower: bootstrap percentile 2.5%
        - ci_upper: bootstrap percentile 97.5%
        - p_value: sign-flip permutation p-value
        - effect_direction: 'favors_test', 'favors_baseline', or 'negligible'
    """
    # Merge on seed
    merged = pd.merge(
        baseline_df[['seed', endpoint]],
        test_df[['seed', endpoint]],
        on='seed',
        suffixes=('_baseline', '_test')
    )

    # Drop NaN pairs
    merged = merged.dropna()
    n_pairs = len(merged)

    if n_pairs == 0:
        return {
            'n_pairs': 0,
            'mean_diff': np.nan,
            'ci_lower': np.nan,
            'ci_upper': np.nan,
            'p_value': np.nan,
            'effect_direction': 'no_data'
        }

    # Compute paired differences (test - baseline)
    diffs = merged[f'{endpoint}_test'].values - merged[f'{endpoint}_baseline'].values
    mean_diff = float(np.mean(diffs))

    # Bootstrap 95% CI (percentile method)
    boot_means = []
    rng = np.random.RandomState(42)  # Fixed seed for reproducibility
    for _ in range(N_BOOTSTRAP):
        boot_idx = rng.choice(n_pairs, size=n_pairs, replace=True)
        boot_sample = diffs[boot_idx]
        boot_means.append(np.mean(boot_sample))

    ci_lower = float(np.percentile(boot_means, 2.5))
    ci_upper = float(np.percentile(boot_means, 97.5))

    # Sign-flip permutation test
    perm_stats = []
    rng = np.random.RandomState(42)  # Fixed seed for reproducibility
    for _ in range(N_PERMUTATION):
        signs = rng.choice([-1, 1], size=n_pairs)
        perm_stat = np.mean(diffs * signs)
        perm_stats.append(perm_stat)

    # Two-tailed p-value
    p_value = float(np.mean(np.abs(perm_stats) >= np.abs(mean_diff)))

    # Effect direction
    if higher_is_better:
        if mean_diff > 0 and p_value < 0.05:
            effect_direction = 'favors_test'
        elif mean_diff < 0 and p_value < 0.05:
            effect_direction = 'favors_baseline'
        else:
            effect_direction = 'inconclusive'
    else:  # lower is better
        if mean_diff < 0 and p_value < 0.05:
            effect_direction = 'favors_test'
        elif mean_diff > 0 and p_value < 0.05:
            effect_direction = 'favors_baseline'
        else:
            effect_direction = 'inconclusive'

    return {
        'n_pairs': n_pairs,
        'mean_diff': mean_diff,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'p_value': p_value,
        'effect_direction': effect_direction
    }

def run_inference_analysis():
    """Run complete inference analysis on all primary contrasts"""

    print("=" * 80)
    print("V5-RC1 STATISTICAL INFERENCE")
    print("=" * 80)
    print()
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Load endpoints
    endpoints = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints.csv")

    print(f"Loaded endpoints: {len(endpoints)} trajectories")
    print()

    # Define primary contrasts from frozen protocol
    primary_contrasts = [
        ('raw_ucb_beta_1', 'gg_ucb_beta_1', 'Original GG vs Raw'),
        ('raw_ucb_beta_1', 'gg_ucb_beta_0p5', 'Selected GG vs Raw'),
        ('raw_ucb_beta_1', 'cs_da_oob_hist', 'Historical CS vs Raw'),
        ('raw_ucb_beta_1', 'cs_da_oob_parsimonious_f1', 'Selected CS vs Raw')
    ]

    # Define endpoints with direction
    endpoint_specs = [
        ('l1_campaign_mace', 'L1 Campaign MACE', False),  # lower is better
        ('l4_top1pct_recall_nauc', 'L4 Top-1% Recall nAUC', True)  # higher is better
    ]

    results = []

    # Process each environment
    for environment in sorted(endpoints['environment'].unique()):
        env_data = endpoints[endpoints['environment'] == environment]

        print(f"Processing environment: {environment}")

        # Process each contrast
        for baseline_strat, test_strat, contrast_name in primary_contrasts:
            # Check if both strategies exist in this environment
            baseline_data = env_data[env_data['strategy'] == baseline_strat]
            test_data = env_data[env_data['strategy'] == test_strat]

            if len(baseline_data) == 0 or len(test_data) == 0:
                continue

            # Process each endpoint
            for endpoint, endpoint_name, higher_is_better in endpoint_specs:
                inference = compute_paired_inference(
                    baseline_data, test_data, endpoint, higher_is_better
                )

                result = {
                    'environment': environment,
                    'contrast_name': contrast_name,
                    'baseline_strategy': baseline_strat,
                    'test_strategy': test_strat,
                    'endpoint': endpoint,
                    'endpoint_name': endpoint_name,
                    'higher_is_better': higher_is_better,
                    'n_pairs': inference['n_pairs'],
                    'mean_diff': inference['mean_diff'],
                    'ci_lower': inference['ci_lower'],
                    'ci_upper': inference['ci_upper'],
                    'p_value': inference['p_value'],
                    'effect_direction': inference['effect_direction'],
                    'significant_0p05': inference['p_value'] < 0.05 if not np.isnan(inference['p_value']) else False
                }

                results.append(result)

        print(f"  Completed {len([r for r in results if r['environment'] == environment])} contrasts")

    print()
    print(f"Completed: {datetime.now().isoformat()}")
    print()

    # Convert to DataFrame
    inference_df = pd.DataFrame(results)

    # Save primary contrasts
    output_path = TABLES / "v5_rc1_primary_contrasts.csv"
    inference_df.to_csv(output_path, index=False)
    print(f"Written: {output_path.name}")
    print()

    # Generate summary statistics
    print("=" * 80)
    print("INFERENCE SUMMARY")
    print("=" * 80)
    print()

    print(f"Total contrasts tested: {len(inference_df)}")
    print(f"Unique environments: {inference_df['environment'].nunique()}")
    print(f"Unique contrast types: {inference_df['contrast_name'].nunique()}")
    print()

    # Significance by endpoint
    for endpoint, endpoint_name, _ in endpoint_specs:
        endpoint_results = inference_df[inference_df['endpoint'] == endpoint]
        n_sig = endpoint_results['significant_0p05'].sum()
        n_total = len(endpoint_results)

        print(f"{endpoint_name}:")
        print(f"  Significant at p<0.05: {n_sig}/{n_total}")

        # Effect direction breakdown
        for direction in ['favors_test', 'favors_baseline', 'inconclusive']:
            n_dir = (endpoint_results['effect_direction'] == direction).sum()
            print(f"  {direction}: {n_dir}")
        print()

    # Contrast-specific summary
    print("By contrast type:")
    for contrast_name in inference_df['contrast_name'].unique():
        contrast_results = inference_df[inference_df['contrast_name'] == contrast_name]
        n_sig = contrast_results['significant_0p05'].sum()
        n_total = len(contrast_results)
        print(f"  {contrast_name}: {n_sig}/{n_total} significant")
    print()

    # Representative effect sizes
    print("Representative effect sizes (mean across environments):")
    for contrast_name in inference_df['contrast_name'].unique():
        print(f"\n  {contrast_name}:")
        for endpoint, endpoint_name, _ in endpoint_specs:
            subset = inference_df[
                (inference_df['contrast_name'] == contrast_name) &
                (inference_df['endpoint'] == endpoint)
            ]
            if len(subset) > 0:
                mean_effect = subset['mean_diff'].mean()
                print(f"    {endpoint_name}: {mean_effect:.6f}")
    print()

    # Generate statistical analysis report
    report = generate_inference_report(inference_df, endpoint_specs)
    report_path = REVISION / "23_final_statistical_analysis_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"Written: {report_path.name}")
    print()

    return inference_df

def generate_inference_report(inference_df: pd.DataFrame, endpoint_specs: list) -> str:
    """Generate markdown report of statistical inference results"""

    report = f"""# V5-RC1 Final Statistical Analysis Report

Generated: {datetime.now().isoformat()}

## Overview

This report presents the results of paired statistical inference on frozen V5-RC1 confirmation endpoints.

- **Total contrasts tested**: {len(inference_df)}
- **Unique environments**: {inference_df['environment'].nunique()}
- **Inference method**: Paired bootstrap CI + sign-flip permutation test
- **Bootstrap iterations**: {N_BOOTSTRAP}
- **Permutation iterations**: {N_PERMUTATION}
- **Significance level**: α = 0.05 (unadjusted)

## Primary Endpoints

- **L1 Campaign MACE**: Mean absolute calibration error (lower is better)
- **L4 Top-1% Recall nAUC**: Sequential value (higher is better)

## Inference Method

### Paired Design

- **Inference unit**: Seed (5000-5039)
- **Pairing**: Within environment (task × split × model)
- **Effect**: test - baseline (paired difference)

### Bootstrap Confidence Intervals

- **Method**: Percentile bootstrap
- **Resampling**: With replacement from paired differences
- **Iterations**: {N_BOOTSTRAP}
- **CI level**: 95% (2.5th and 97.5th percentiles)

### Permutation Test

- **Null hypothesis**: No difference between strategies
- **Method**: Sign-flip permutation
- **Iterations**: {N_PERMUTATION}
- **p-value**: Two-tailed proportion of permuted statistics ≥ observed |effect|

## Results Summary

"""

    # Add significance summary
    for endpoint, endpoint_name, _ in endpoint_specs:
        endpoint_results = inference_df[inference_df['endpoint'] == endpoint]
        n_sig = endpoint_results['significant_0p05'].sum()
        n_total = len(endpoint_results)

        report += f"### {endpoint_name}\n\n"
        report += f"- **Contrasts tested**: {n_total}\n"
        report += f"- **Significant at p<0.05**: {n_sig} ({100*n_sig/n_total:.1f}%)\n\n"

        report += "**Effect direction distribution**:\n\n"
        for direction in ['favors_test', 'favors_baseline', 'inconclusive']:
            n_dir = (endpoint_results['effect_direction'] == direction).sum()
            report += f"- {direction.replace('_', ' ').title()}: {n_dir}\n"
        report += "\n"

    # Add contrast-specific results
    report += "## Results by Contrast Type\n\n"

    for contrast_name in sorted(inference_df['contrast_name'].unique()):
        report += f"### {contrast_name}\n\n"

        contrast_results = inference_df[inference_df['contrast_name'] == contrast_name]
        n_sig = contrast_results['significant_0p05'].sum()
        n_total = len(contrast_results)

        report += f"- **Significant**: {n_sig}/{n_total} contrasts\n\n"

        for endpoint, endpoint_name, higher_is_better in endpoint_specs:
            subset = contrast_results[contrast_results['endpoint'] == endpoint]
            if len(subset) > 0:
                mean_effect = subset['mean_diff'].mean()
                n_env_sig = subset['significant_0p05'].sum()

                direction = "higher" if higher_is_better else "lower"
                favors = "test favored" if (mean_effect > 0 and higher_is_better) or (mean_effect < 0 and not higher_is_better) else "baseline favored"

                report += f"**{endpoint_name}** ({direction} is better):\n"
                report += f"- Mean effect across environments: {mean_effect:.6f}\n"
                report += f"- Significant environments: {n_env_sig}/{len(subset)}\n"
                report += f"- Overall direction: {favors}\n\n"

        report += "\n"

    # Important notes
    report += """## Important Notes

### Multiplicity

- **No adjustment applied yet**: p-values are unadjusted
- **Prospectively specified families**: Require family-wise error rate correction
- **Recommendation**: Apply Bonferroni or Holm-Bonferroni within families before interpretation

### Interpretation Guidelines

- **Significant (p<0.05)**: Evidence of difference, subject to multiplicity adjustment
- **Inconclusive**: Insufficient evidence to reject null hypothesis
- **Not tested for equivalence**: Absence of significance ≠ equivalence

### Effect Direction

- **L1 (lower better)**: Negative effect favors test strategy
- **L4 (higher better)**: Positive effect favors test strategy
- **Check CI**: Does it exclude zero?

### No Task Pooling

- Results are environment-specific (16 independent environments)
- Cannot generalize beyond tested tasks and conditions
- Cross-environment patterns are descriptive only

## Next Steps

1. **Apply multiplicity correction** to prospectively defined families
2. **Generate figures** showing effect sizes and CIs by environment
3. **Update manuscript** with confirmed results
4. **Complete traceability matrix** linking manuscript numbers to this table
5. **Perform final validation** before submission

## Data Location

- **Endpoints**: `tables_v5/v5_rc1_seed_level_endpoints.csv`
- **Inference results**: `tables_v5/v5_rc1_primary_contrasts.csv`
- **Completeness audit**: `audits_v5/v5_rc1_endpoint_completeness.csv`

All analysis uses frozen protocol definitions and locked trajectory content.
"""

    return report

if __name__ == '__main__':
    inference_df = run_inference_analysis()
