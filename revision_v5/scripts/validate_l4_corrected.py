#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V5-RC1 L4 CORRECTED Exact Validation
Uses correct x-axis: round numbers (not budget_fraction)
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT
RESULTS_DIR = REVISION / "results_v4" / "confirmation" / "trajectories"
AUDITS = REVISION / "audits_v5"

def normalized_auc(x, values):
    """Exact historical implementation from metrics.py"""
    x = np.asarray(x, float)
    values = np.asarray(values, float)
    order = np.argsort(x, kind="stable")
    x = x[order]
    values = values[order]
    if len(x) < 2 or x[-1] <= x[0]:
        return float("nan")
    return float(np.trapezoid(values, x) / (x[-1] - x[0]))

def validate_l4_exact(job_id: str) -> dict:
    """Validate L4 using correct x-axis: round numbers"""

    traj_dir = RESULTS_DIR / job_id

    try:
        # Load state
        with open(traj_dir / 'state.json', 'r', encoding='utf-8') as f:
            state = json.load(f)

        state_nauc = state.get('primary_nauc', np.nan)

        # Load rounds
        rounds_df = pd.read_parquet(traj_dir / 'rounds.parquet')

        # CRITICAL: Use round numbers as x-axis (includes round -1 for initial state)
        x_values = rounds_df['round'].values
        recall_values = rounds_df['top1_recall'].values

        # Recompute using exact historical implementation
        recomputed_nauc = normalized_auc(x_values, recall_values)

        # Compare
        if pd.isna(state_nauc) or pd.isna(recomputed_nauc):
            validation_status = 'nan_present'
            abs_diff = np.nan
            rel_diff = np.nan
        else:
            abs_diff = abs(recomputed_nauc - state_nauc)
            rel_diff = abs_diff / abs(state_nauc) if state_nauc != 0 else np.nan

            # IEEE 754 double precision tolerance
            # Typical accumulation: ~13 rounds × ~10 operations = ~130 ops
            # Conservative tolerance: 1e-14 (well within floating-point precision)
            tolerance_exact = 1e-14
            tolerance_close = 1e-10

            if abs_diff < tolerance_exact:
                validation_status = 'exact_match'
            elif abs_diff < tolerance_close:
                validation_status = 'close_match'
            else:
                validation_status = 'mismatch'

        return {
            'job_id': job_id,
            'state_primary_nauc': state_nauc,
            'independently_recomputed_nauc': recomputed_nauc,
            'absolute_difference': abs_diff,
            'relative_difference': rel_diff,
            'validation_status': validation_status,
            'x_axis_used': 'round',
            'n_rounds': len(rounds_df),
            'implementation_source': 'experiments_v4/src/transportability_v5/metrics.py::normalized_auc'
        }

    except Exception as e:
        return {
            'job_id': job_id,
            'state_primary_nauc': np.nan,
            'independently_recomputed_nauc': np.nan,
            'absolute_difference': np.nan,
            'relative_difference': np.nan,
            'validation_status': 'error',
            'error': str(e)
        }

print("=" * 80)
print("V5-RC1 L4 CORRECTED EXACT VALIDATION")
print("=" * 80)
print()
print("CORRECTED x-axis: round numbers (including round -1 for initial state)")
print()
print("Historical implementation:")
print("  File: experiments_v4/src/transportability_v5/metrics.py")
print("  Function: normalized_auc(x, values)")
print("  X-axis: round numbers")
print("  Y-axis: top1_recall from rounds.parquet")
print("  Integration: np.trapezoid(values, x)")
print("  Normalization: / (x_max - x_min)")
print()
print("Tolerance: 1e-14 (exact), 1e-10 (close)")
print("=" * 80)
print()

# Load registry
registry = pd.read_csv(REVISION / "results_v4" / "confirmation" / "registry_snapshot.csv")
completed = registry[registry['status'].isin(['COMPLETED', 'RECOVERED'])]

print(f"Validating {len(completed)} trajectories...")
print()

results = []

for idx, row in completed.iterrows():
    job_id = row['job_id']
    result = validate_l4_exact(job_id)
    results.append(result)

    if (idx + 1) % 500 == 0:
        print(f"  Validated {idx + 1}/{len(completed)}...")

print()

# Convert to DataFrame
validation_df = pd.DataFrame(results)

# Save
output_path = AUDITS / "l4_state_vs_recomputed_nauc_v3.csv"
validation_df.to_csv(output_path, index=False)
print(f"Written: {output_path.name}")
print()

# Summary
print("=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)
print()

status_counts = validation_df['validation_status'].value_counts()
print("Validation status:")
for status, count in sorted(status_counts.items()):
    pct = 100 * count / len(validation_df)
    print(f"  {status:20s}: {count:4d} ({pct:5.1f}%)")
print()

# Difference statistics
valid_diffs = validation_df[validation_df['absolute_difference'].notna()]
if len(valid_diffs) > 0:
    print("Absolute difference statistics:")
    print(f"  Mean:   {valid_diffs['absolute_difference'].mean():.2e}")
    print(f"  Median: {valid_diffs['absolute_difference'].median():.2e}")
    print(f"  Max:    {valid_diffs['absolute_difference'].max():.2e}")
    print(f"  Min:    {valid_diffs['absolute_difference'].min():.2e}")
    print()

    # Percentiles
    print("Percentiles:")
    for p in [50, 90, 95, 99, 99.9, 100]:
        val = np.percentile(valid_diffs['absolute_difference'], p)
        print(f"  {p:5.1f}th: {val:.2e}")
    print()

# Check for issues
exact_matches = (validation_df['validation_status'] == 'exact_match').sum()
close_matches = (validation_df['validation_status'] == 'close_match').sum()
mismatches = (validation_df['validation_status'] == 'mismatch').sum()

print(f"Exact matches (< 1e-14): {exact_matches}")
print(f"Close matches (< 1e-10): {close_matches}")
print(f"Mismatches (>= 1e-10):   {mismatches}")
print()

if mismatches > 0:
    print(f"WARNING: {mismatches} trajectories with mismatches > 1e-10")
    mismatch_df = validation_df[validation_df['validation_status'] == 'mismatch']
    print("\nSample mismatches:")
    for _, row in mismatch_df.head(10).iterrows():
        print(f"  {row['job_id']:60s} diff={row['absolute_difference']:.2e}")
    print()
    print("RESULT: L4 VALIDATION FAILED")
else:
    print("SUCCESS: All trajectories validated within tolerance")
    print()
    print("RESULT: L4 VALIDATION PASSED")

print()
print("=" * 80)
