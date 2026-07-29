# Identity control reconciliation

## Exact cause

Canonical full-trajectory extraction used `initial=-1` and each acquisition-round index `r`.
Diagnostics are recorded before acquisition, so the matching checkpoint rows are `initial=0`
and `r+1`. The legacy mapping therefore aliased the final diagnostic row for initial and used
the pre-acquisition model for the remaining checkpoints.

Identity replay was correct. It loaded the retained RAW checkpoint models. The corrected RAW
checkpoint aggregates equal Identity exactly in all 2560 environment × seed ×
checkpoint × coverage rows.

## Resolution

- Original broad endpoint table: archived byte-for-byte and unchanged.
- Corrected RAW values: versioned V6 endpoint layer.
- Maximum absolute RAW L1 correction: 0.037067592171142527.
- Independent trajectories rerun: 0.
- Cause is checkpoint semantics, unrelated to outcome direction.
