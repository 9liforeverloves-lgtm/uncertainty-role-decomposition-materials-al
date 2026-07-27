#!/usr/bin/env python3
"""
Generate trajectory content hash inventory for V5-RC1
Creates a deterministic hash lock of all trajectory output files
Does NOT modify any trajectory content
"""

from pathlib import Path
import hashlib
import csv
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
REVISION = ROOT
RESULTS_DIR = REVISION / "results_v4" / "confirmation" / "trajectories"
AUDITS = REVISION / "audits_v5"
AUDITS.mkdir(exist_ok=True)

def sha256_file(path: Path) -> str:
    """Compute SHA256 hash of file"""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def collect_trajectory_inventory():
    """Collect hash inventory of all trajectory files"""

    print("Collecting trajectory file inventory...")
    print("This will take several minutes for 3,360 trajectories...")
    print()

    inventory = []
    trajectory_dirs = sorted(RESULTS_DIR.glob("*"))

    for idx, traj_dir in enumerate(trajectory_dirs):
        if not traj_dir.is_dir():
            continue

        job_id = traj_dir.name

        # Process all files in trajectory directory
        for file_path in sorted(traj_dir.iterdir()):
            if file_path.is_file():
                relative_path = file_path.relative_to(REVISION)
                size = file_path.stat().st_size

                # Compute hash
                file_hash = sha256_file(file_path)

                inventory.append({
                    'relative_path': relative_path.as_posix(),
                    'job_id': job_id,
                    'filename': file_path.name,
                    'size_bytes': size,
                    'sha256': file_hash
                })

        # Progress indicator
        if (idx + 1) % 100 == 0:
            print(f"  Processed {idx + 1}/{len(trajectory_dirs)} trajectories...")

    print(f"  Completed: {len(trajectory_dirs)} trajectories, {len(inventory)} files")
    print()

    return inventory

def compute_inventory_hash(inventory: list) -> str:
    """Compute deterministic hash of entire inventory"""
    # Sort by relative path for determinism
    sorted_inv = sorted(inventory, key=lambda x: x['relative_path'])

    # Create canonical representation
    canonical = '\n'.join(
        f"{item['relative_path']}|{item['size_bytes']}|{item['sha256']}"
        for item in sorted_inv
    )

    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

# Main execution
print("=" * 80)
print("V5-RC1 TRAJECTORY CONTENT LOCK GENERATION")
print("=" * 80)
print()

# Collect inventory
inventory = collect_trajectory_inventory()

# Write CSV inventory
inventory_csv = AUDITS / "confirmation_trajectory_hash_inventory.csv"
fieldnames = ['relative_path', 'job_id', 'filename', 'size_bytes', 'sha256']

with open(inventory_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(inventory)

print(f"✓ Written: {inventory_csv.name}")
print(f"  Total files: {len(inventory)}")
print()

# Compute aggregate statistics
total_size = sum(item['size_bytes'] for item in inventory)
unique_jobs = len(set(item['job_id'] for item in inventory))
files_per_job = len(inventory) / unique_jobs if unique_jobs > 0 else 0

print("Inventory statistics:")
print(f"  Unique trajectories: {unique_jobs}")
print(f"  Total files: {len(inventory)}")
print(f"  Average files per trajectory: {files_per_job:.1f}")
print(f"  Total size: {total_size / (1024**3):.2f} GB")
print()

# Compute inventory hash
inventory_hash = compute_inventory_hash(inventory)
print(f"Deterministic inventory hash: {inventory_hash}")
print()

# Create content lock JSON
content_lock = {
    "schema_version": "trajectory-content-lock-v1",
    "protocol_version": "v5-rc1",
    "locked_at": datetime.now().isoformat(),
    "lock_type": "post-execution-pre-inference",
    "trajectory_directory": "results_v4/confirmation/trajectories",
    "inventory": {
        "path": str(inventory_csv.relative_to(REVISION)),
        "sha256": hashlib.sha256(inventory_csv.read_bytes()).hexdigest(),
        "file_count": len(inventory),
        "trajectory_count": unique_jobs,
        "total_size_bytes": total_size
    },
    "deterministic_tree_hash": inventory_hash,
    "immutability_pledge": "This lock freezes trajectory file content. Any modification to trajectory outputs invalidates this hash and violates the post-execution freeze.",
    "verification_instructions": "To verify: recompute inventory CSV, sort by relative_path, concatenate path|size|sha256 with newlines, SHA256 the result. Must match deterministic_tree_hash.",
    "relationship_to_result_lock": "This is an additive amendment to CONFIRMATION_RESULT_LOCK_V5_RC1.json. The original result lock remains unchanged and authoritative for manifest/registry/protocol hashes."
}

content_lock_path = REVISION / "CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json"
with open(content_lock_path, 'w', encoding='utf-8') as f:
    json.dump(content_lock, f, indent=2)

print(f"✓ Written: {content_lock_path.name}")
print()

# Generate amendment report
amendment_md = f"""# V5-RC1 Trajectory Content Lock Amendment

Generated: {datetime.now().isoformat()}

## Purpose

This is a **post-execution, pre-inference content lock** of all trajectory output files.

The original result lock (`CONFIRMATION_RESULT_LOCK_V5_RC1.json`) froze the manifest, registry, and protocol but did not hash individual trajectory files. This amendment adds deterministic content verification for all {len(inventory)} trajectory output files across {unique_jobs} trajectories.

## Status

**This is NOT a protocol change.**

All trajectories were executed and completed before this lock. No trajectory content has been modified. This lock documents the exact file state that will be used for endpoint computation and statistical inference.

## Content Lock Structure

### Inventory File

**File**: `audits_v5/confirmation_trajectory_hash_inventory.csv`
**Rows**: {len(inventory)} files
**Columns**: relative_path, job_id, filename, size_bytes, sha256

### Deterministic Tree Hash

**Method**: Sort inventory by relative_path, concatenate `path|size|sha256` lines, SHA256 the result
**Hash**: `{inventory_hash}`

### Verification

To verify trajectory content integrity:

1. Recompute SHA256 for each file in the inventory
2. Compare against recorded hash
3. Any mismatch indicates trajectory modification
4. Recompute deterministic tree hash from sorted inventory
5. Must match: `{inventory_hash}`

## Coverage

- **Trajectories**: {unique_jobs}
- **Files**: {len(inventory)}
- **Total size**: {total_size / (1024**3):.2f} GB
- **Files per trajectory**: ~{files_per_job:.0f}

Expected files per trajectory:
- state.json
- provenance.json
- source_code_hashes.json
- protocol_snapshot.yaml
- rounds.parquet
- selected.parquet
- diagnostic_metrics.parquet
- floor_ranking_audit.parquet
- checkpoint_*.json (4 checkpoints)
- checkpoint_*.joblib (4 checkpoints)

## Relationship to Original Result Lock

**Original lock** (`CONFIRMATION_RESULT_LOCK_V5_RC1.json`):
- Freezes manifest, registry, protocol
- Documents trajectory directory existence
- Creates immutability pledge

**This amendment** (`CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json`):
- Freezes individual trajectory file content
- Provides per-file verification
- Enables reproducible endpoint computation

Both locks are required for complete result verification.

## Immutability Guarantee

Any modification to trajectory output files after this lock:

1. Violates the post-execution freeze
2. Invalidates the deterministic tree hash
3. Breaks reproducibility of endpoint computation
4. Requires re-execution under the frozen protocol

## Execution Timeline

1. **Confirmation computation**: 2026-07-23 (trajectories executed)
2. **Result freeze**: 2026-07-25T05:43:20 (manifest/registry/protocol locked)
3. **Content lock amendment**: {datetime.now().isoformat()} (trajectory files hashed)
4. **Endpoint computation**: Pending (will use locked trajectory content)
5. **Statistical inference**: Pending (will use locked endpoints)

## Next Steps

1. Verify no trajectory modifications since execution
2. Audit endpoint computation script against frozen protocol definitions
3. Run endpoint computation using locked trajectory content only
4. Generate inference results from locked endpoints only
5. All manuscript numbers must trace to locked tables
"""

amendment_path = REVISION / "21A_trajectory_content_lock_amendment.md"
with open(amendment_path, 'w', encoding='utf-8') as f:
    f.write(amendment_md)

print(f"✓ Written: {amendment_path.name}")
print()

print("=" * 80)
print("TRAJECTORY CONTENT LOCK COMPLETE")
print("=" * 80)
print()
print("Created files:")
print(f"  1. audits_v5/confirmation_trajectory_hash_inventory.csv ({len(inventory)} files)")
print(f"  2. CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json (deterministic hash)")
print(f"  3. 21A_trajectory_content_lock_amendment.md (documentation)")
print()
print(f"Deterministic tree hash: {inventory_hash}")
print()
print("This lock is additive and does not modify CONFIRMATION_RESULT_LOCK_V5_RC1.json")
print("All {unique_jobs} trajectory outputs are now hash-locked for endpoint computation.")
