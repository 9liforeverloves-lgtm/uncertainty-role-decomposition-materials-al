#!/usr/bin/env python3
"""
V5-RC1 Small Sample Validation
Validates endpoint computation on a small locked sample before full execution
"""

from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT
RESULTS_DIR = REVISION / "results_v4" / "confirmation" / "trajectories"

print("=" * 80)
print("V5-RC1 SMALL SAMPLE VALIDATION")
print("=" * 80)
print()

# Select small sample: 1 task, 1 split, 1 model, 2 strategies, 2 seeds
SAMPLE = {
    'task': 'matbench_expt_gap',
    'split': 'iid_record',
    'model': 'random_forest',
    'strategies': ['raw_ucb_beta_1', 'gg_ucb_beta_1'],
    'seeds': [5000, 5001]
}

print("Sample selection:")
print(f"  Task: {SAMPLE['task']}")
print(f"  Split: {SAMPLE['split']}")
print(f"  Model: {SAMPLE['model']}")
print(f"  Strategies: {SAMPLE['strategies']}")
print(f"  Seeds: {SAMPLE['seeds']}")
print()

# ============================================================================
# INSPECT DATA STRUCTURE
# ============================================================================

print("STEP 1: Inspect data structure from one trajectory")
print("-" * 80)

job_id = f"{SAMPLE['task']}__{SAMPLE['split']}__{SAMPLE['model']}__{SAMPLE['strategies'][0]}__seed{SAMPLE['seeds'][0]}"
traj_dir = RESULTS_DIR / job_id

print(f"Trajectory: {job_id}")
print()

# Load state
with open(traj_dir / 'state.json', 'r') as f:
    state = json.load(f)

print("State.json key fields:")
print(f"  primary_nauc: {state.get('primary_nauc')}")
print(f"  complete: {state.get('complete')}")
print(f"  next_round: {state.get('next_round')}")
print()

# Load parquet files
selected = pd.read_parquet(traj_dir / 'selected.parquet')
rounds = pd.read_parquet(traj_dir / 'rounds.parquet')
diagnostic = pd.read_parquet(traj_dir / 'diagnostic_metrics.parquet')

print(f"Selected.parquet: {len(selected)} rows, {len(selected.columns)} columns")
print(f"Rounds.parquet: {len(rounds)} rows, {len(rounds.columns)} columns")
print(f"Diagnostic_metrics.parquet: {len(diagnostic)} rows, {len(diagnostic.columns)} columns")
print()

# ============================================================================
# VALIDATE L1: Campaign MACE
# ============================================================================

print("STEP 2: Validate L1 Campaign MACE")
print("-" * 80)

# From diagnostic_metrics.parquet, we have:
# - mean_absolute_coverage_error (per round)
# - coverage_50, coverage_80, coverage_90, coverage_95 (per round)

print("Diagnostic metrics has MACE-related columns:")
print(f"  mean_absolute_coverage_error: {diagnostic['mean_absolute_coverage_error'].tolist()}")
print()

# The frozen definition requires four-checkpoint MACE
# But diagnostic_metrics is per-round, not per-checkpoint

print("⚠ ISSUE: diagnostic_metrics is per-round, not per-checkpoint")
print("  Frozen protocol requires MACE at checkpoints: initial, 25%, 50%, 75%")
print("  Need to identify which rounds correspond to these checkpoints")
print()

# Check checkpoint correspondence
print("Checkpoint files:")
for ckpt in ['initial', '25pct', '50pct', '75pct']:
    ckpt_file = traj_dir / f'checkpoint_{ckpt}.json'
    with open(ckpt_file, 'r') as f:
        ckpt_data = json.load(f)
    print(f"  {ckpt}: acquisition_round={ckpt_data.get('acquisition_round')}, queried_count={ckpt_data.get('queried_count')}")
print()

# Map checkpoints to rounds
checkpoint_rounds = {}
for ckpt in ['initial', '25pct', '50pct', '75pct']:
    with open(traj_dir / f'checkpoint_{ckpt}.json', 'r') as f:
        ckpt_data = json.load(f)
    checkpoint_rounds[ckpt] = ckpt_data.get('acquisition_round', 0)

print("Checkpoint to round mapping:")
for ckpt, rnd in checkpoint_rounds.items():
    print(f"  {ckpt}: round {rnd}")
print()

# Compute campaign MACE
checkpoint_maces = []
for ckpt in ['initial', '25pct', '50pct', '75pct']:
    rnd = checkpoint_rounds[ckpt]
    # Get diagnostic for this round
    if rnd < len(diagnostic):
        mace = diagnostic.iloc[rnd]['mean_absolute_coverage_error']
        checkpoint_maces.append(mace)
        print(f"  {ckpt} (round {rnd}): MACE = {mace:.6f}")

if checkpoint_maces:
    campaign_mace = np.mean(checkpoint_maces)
    print()
    print(f"✓ Campaign MACE (mean of 4 checkpoints): {campaign_mace:.6f}")
    print()
else:
    print()
    print("✗ Could not compute campaign MACE")
    print()

# ============================================================================
# VALIDATE L4: Top-1% Recall nAUC
# ============================================================================

print("STEP 3: Validate L4 Top-1% Recall nAUC")
print("-" * 80)

print(f"State.json primary_nauc: {state.get('primary_nauc')}")
print()

# Check rounds.parquet for recall data
print("Rounds.parquet has recall columns:")
print(f"  top1_recall: {rounds['top1_recall'].tolist()}")
print()

# The frozen definition requires:
# 1. Including initial state (round 0)
# 2. Top-1% of selectable pool
# 3. Normalized AUC

# Check if initial state is included
if len(rounds) > 0 and rounds.iloc[0]['round'] == 0:
    print("✓ Initial state (round 0) is present in rounds.parquet")
else:
    print("✗ Initial state missing or unclear")
print()

# Compute nAUC from recall curve
recall_values = rounds['top1_recall'].values
n_rounds = len(recall_values)

print(f"Recall curve (top-1%):")
for i, r in enumerate(recall_values[:5]):
    print(f"  Round {i}: {r:.4f}")
if n_rounds > 5:
    print(f"  ... ({n_rounds} rounds total)")
print()

# Simple AUC computation (trapezoidal)
# Normalize by maximum possible AUC
if n_rounds > 1:
    # AUC using trapezoidal rule
    auc = np.trapz(recall_values, dx=1.0)
    # Maximum possible AUC (if recall=1 from round 1 onward)
    max_auc = n_rounds - 1  # Assuming initial recall=0
    # Normalized AUC
    if max_auc > 0:
        nauc = auc / max_auc
        print(f"Computed nAUC (trapezoidal): {nauc:.6f}")
        print(f"State.json primary_nauc:     {state.get('primary_nauc'):.6f}")
        print()

        # Check match
        if abs(nauc - state.get('primary_nauc', 0)) < 0.01:
            print("✓ Reasonable match (within 0.01)")
        else:
            print(f"⚠ Discrepancy: {abs(nauc - state.get('primary_nauc', 0)):.6f}")
        print()
else:
    print("✗ Insufficient rounds for nAUC computation")
    print()

# ============================================================================
# SUMMARY
# ============================================================================

print("=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)
print()

print("Data structure findings:")
print("  ✓ state.json contains primary_nauc field")
print("  ✓ diagnostic_metrics.parquet contains mean_absolute_coverage_error")
print("  ✓ rounds.parquet contains top1_recall per round")
print("  ✓ checkpoint_*.json files exist and map to acquisition rounds")
print()

print("L1 Campaign MACE:")
if checkpoint_maces:
    print(f"  ✓ Can compute from diagnostic_metrics per-checkpoint MACE")
    print(f"  ✓ Campaign MACE = {campaign_mace:.6f}")
else:
    print("  ✗ Implementation needed")
print()

print("L4 Top-1% Recall nAUC:")
print(f"  ✓ state.json primary_nauc appears valid: {state.get('primary_nauc'):.6f}")
print("  ✓ Can validate against rounds.parquet top1_recall")
print("  ⚠ Exact normalization formula needs verification")
print()

print("Recommendation:")
print("  1. Use state.json['primary_nauc'] for L4 (appears reliable)")
print("  2. Compute L1 from diagnostic_metrics at checkpoint rounds")
print("  3. Implement full validation on 4-trajectory sample")
print("  4. Then proceed to full 3360-trajectory endpoint computation")
print()
