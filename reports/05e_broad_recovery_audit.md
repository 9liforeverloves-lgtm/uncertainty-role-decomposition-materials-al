# Broad recovery audit

- `execution_summary recovered`: 8
- registry `attempt=2` rows: 8
- recovery record files: 8
- count reconciliation: True
- final output hashes: True
- unchanged final lock: True
- duplicate final outputs absent: True

The original recovery records do not contain point-in-time `last_valid_checkpoint` or
checkpoint hash fields. Final recovered outputs contain hash-verifiable `75pct` checkpoints,
but that does not reconstruct the exact durable checkpoint present when stale-worker recovery
was authorized. Count/final-output reconciliation passes; recovery-record completeness remains
a formal freeze blocker.
