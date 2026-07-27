# Registry and restart validation

Status: **PASS**. V6 uses the authoritative V5 SQLite state machine through a thin adapter. Tests cover legal transitions, atomic concurrent claims, duplicate-claim rejection, unchanged retry, crash injection before checkpoint write, crash injection after temporary write and before rename, recovery of a hash-validated temporary payload, last-valid-checkpoint discovery, and divergent-overwrite rejection.

Checkpoint metadata carries the V5 labels, thresholds, progress, acquisition round, queried count, payload hash, and run identity fields.
