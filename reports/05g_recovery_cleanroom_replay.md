# V6 P0 recovery clean-room replay

Status: **PASS_8_OF_8**

- Replayed jobs: 8 (exactly the eight registered recovered development jobs).
- Logical trajectories and corrected endpoints matched: 8/8.
- Final broad lock identity: `edca62dd041f7ab6d02bfd63af381c60bb26dfee187df6d290c686848f202f4b`.
- Final broad manifest SHA-256: `b8d0eca1d3d0625203d04458fcd07232999ecadaa5ca94241292cd271e71b496`.
- Isolated replay directory: `results/v6_p0_recovery_cleanroom_replay/trajectories`.
- Original recovery records overwritten: no.
- Historical point-in-time checkpoint hashes reconstructed: no; they remain unavailable.
- Broad 2,720-job cohort rerun: no.
- Confirmation seeds used: none.

Each row compares source/target/diagnostic split hashes, the ordered initial IDs,
every ordered queried batch, four checkpoint logical hashes, the final logical
trajectory hash, corrected L1, and L4. The checkpoint logical hash binds stable
checkpoint metadata to its internally verified model-state SHA-256.
Endpoint equality uses absolute tolerance `1e-15` solely for CSV/in-memory
round-trip effects; exact values and absolute differences are retained in the
CSV. The aggregate logical hash stores endpoints at `1e-14`; the stricter
standalone endpoint acceptance check remains `1e-15`.

Failed jobs: [].

Acceptance rule: all eight rows must pass. If any row fails, the affected jobs
must be excluded from development selection and all LOTO maps regenerated
prospectively from the remaining registered data.
