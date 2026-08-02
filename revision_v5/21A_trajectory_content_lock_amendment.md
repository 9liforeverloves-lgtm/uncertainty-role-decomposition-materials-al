# V5-RC1 Trajectory Content Lock Amendment

Generated: 2026-07-25T06:35:04.147212

## Purpose

This is a **post-execution, pre-inference content lock** of all trajectory output files.

The original result lock (`CONFIRMATION_RESULT_LOCK_V5_RC1.json`) froze the manifest, registry, and protocol but did not hash individual trajectory files. This amendment adds deterministic content verification for all 53760 trajectory output files across 3360 trajectories.

## Status

**This is NOT a protocol change.**

All trajectories were executed and completed before this lock. No trajectory content has been modified. This lock documents the exact file state that will be used for endpoint computation and statistical inference.

## Content Lock Structure

### Inventory File

**File**: `audits_v5/confirmation_trajectory_hash_inventory.csv`
**Rows**: 53760 files
**Columns**: relative_path, job_id, filename, size_bytes, sha256

### Deterministic Tree Hash

**Method**: Sort inventory by relative_path, concatenate `path|size|sha256` lines, SHA256 the result
**Hash**: `03a7576720863e4cb17ee2e5bfba14a144d78f848d2547e9c8efa1133701d2b8`

### Verification

To verify trajectory content integrity:

1. Recompute SHA256 for each file in the inventory
2. Compare against recorded hash
3. Any mismatch indicates trajectory modification
4. Recompute deterministic tree hash from sorted inventory
5. Must match: `03a7576720863e4cb17ee2e5bfba14a144d78f848d2547e9c8efa1133701d2b8`

## Coverage

- **Trajectories**: 3360
- **Files**: 53760
- **Total size**: 83.48 GB
- **Files per trajectory**: ~16

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
3. **Content lock amendment**: 2026-07-25T06:35:04.147234 (trajectory files hashed)
4. **Endpoint computation**: Pending (will use locked trajectory content)
5. **Statistical inference**: Pending (will use locked endpoints)

## Next Steps

1. Verify no trajectory modifications since execution
2. Audit endpoint computation script against frozen protocol definitions
3. Run endpoint computation using locked trajectory content only
4. Generate inference results from locked endpoints only
5. All manuscript numbers must trace to locked tables
