#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5-RC1 Generate Final v3 Tables
Applies within-environment BH multiplicity adjustment
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT
TABLES = REVISION / "tables_v5"

print("=" * 80)
print("V5-RC1 FINAL v3 TABLE GENERATION")
print("=" * 80)
print()

# Load corrected v2 tables
endpoints_v2 = pd.read_csv(TABLES / "v5_rc1_seed_level_endpoints_v2.csv")
contrasts_v2 = pd.read_csv(TABLES / "v5_rc1_primary_contrasts_v2.csv")

print(f"Loaded v2 endpoints: {len(endpoints_v2)} rows")
print(f"Loaded v2 contrasts: {len(contrasts_v2)} rows")
print()

# Update endpoints with L4 validation status
endpoints_v3 = endpoints_v2.copy()
endpoints_v3['l4_independently_validated'] = 'conditional_pass_see_23B'
endpoints_v3['l4_validation_note'] = 'Median difference 2.86e-04, task-specific pattern, approved tolerance 1e-2'

# Save v3 endpoints
endpoints_v3.to_csv(TABLES / "v5_rc1_seed_level_endpoints_v3.csv", index=False)
print(f"Written: v5_rc1_seed_level_endpoints_v3.csv")
print()

# Apply within-environment BH adjustment
print("Applying within-environment Benjamini-Hochberg adjustment...")
print()

contrasts_v3 = contrasts_v2.copy()
contrasts_v3['p_value_bh_adjusted'] = np.nan
contrasts_v3['significant_after_bh'] = False
contrasts_v3['evidence_label'] = ''

for environment in contrasts_v3['environment'].unique():
    env_data = contrasts_v3[contrasts_v3['environment'] == environment].copy()

    # Get unadjusted p-values
    p_values = env_data['p_value_unadjusted'].values
    n_tests = len(p_values)

    # BH procedure
    sorted_indices = np.argsort(p_values)
    sorted_p = p_values[sorted_indices]

    # Adjusted p-values
    adjusted_p = np.minimum(1.0, sorted_p * n_tests / (np.arange(n_tests) + 1))

    # Ensure monotonicity
    for i in range(n_tests - 2, -1, -1):
        adjusted_p[i] = min(adjusted_p[i], adjusted_p[i + 1])

    # Reorder to original
    reordered_adjusted = np.empty(n_tests)
    reordered_adjusted[sorted_indices] = adjusted_p

    # Update
    mask = contrasts_v3['environment'] == environment
    contrasts_v3.loc[mask, 'p_value_bh_adjusted'] = reordered_adjusted
    contrasts_v3.loc[mask, 'significant_after_bh'] = reordered_adjusted < 0.05

# Evidence labels
for idx, row in contrasts_v3.iterrows():
    p_adj = row['p_value_bh_adjusted']
    p_unadj = row['p_value_unadjusted']

    if p_adj < 0.05:
        contrasts_v3.at[idx, 'evidence_label'] = 'significant_after_BH'
    elif p_unadj < 0.05:
        contrasts_v3.at[idx, 'evidence_label'] = 'nominally_significant'
    else:
        contrasts_v3.at[idx, 'evidence_label'] = 'not_significant'

# Add metadata
contrasts_v3['adjustment_method'] = 'within_environment_BH'
contrasts_v3['adjustment_family_size'] = 8
contrasts_v3['alpha_level'] = 0.05
contrasts_v3['prospectively_specified'] = True

# Save v3 contrasts
contrasts_v3.to_csv(TABLES / "v5_rc1_primary_contrasts_v3.csv", index=False)
print(f"Written: v5_rc1_primary_contrasts_v3.csv")
print()

# Summary
print("=" * 80)
print("FINAL v3 SUMMARY")
print("=" * 80)
print()

print("Evidence counts after BH adjustment:")
for label in ['significant_after_BH', 'nominally_significant', 'not_significant']:
    count = (contrasts_v3['evidence_label'] == label).sum()
    pct = 100 * count / len(contrasts_v3)
    print(f"  {label:25s}: {count:3d} / 128 ({pct:5.1f}%)")
print()

print("By contrast type:")
for contrast in sorted(contrasts_v3['contrast_name'].unique()):
    contrast_data = contrasts_v3[contrasts_v3['contrast_name'] == contrast]
    sig_bh = (contrast_data['evidence_label'] == 'significant_after_BH').sum()
    total = len(contrast_data)
    print(f"  {contrast:30s}: {sig_bh:2d} / {total} significant after BH")
print()

print("Files generated:")
print("  - v5_rc1_seed_level_endpoints_v3.csv")
print("  - v5_rc1_primary_contrasts_v3.csv")
print()
print("Ready for final check and manuscript work.")
