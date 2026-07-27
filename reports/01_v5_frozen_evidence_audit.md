# V5 frozen evidence audit

Generated: 2026-07-27T09:12:43.765420+00:00

## Verdict

**PASS for the enumerated V5 authority chain.**

- No V5 file was edited by this audit.
- Authority files checked: 18.
- Lock-named files discovered and hashed: 26.
- Confirmation jobs: 3360; seeds: 5000–5039.
- Tasks: 4; splits: 2; models: 2.
- Environments: 16 (4 tasks × 2 splits × 2 related tree ensembles).
- Strategies: 6; primary endpoints: 2.
- Registry status: `{"COMPLETED": 3354, "RECOVERED": 6}`.
- Trajectory inventory: 53760 files across 3360 jobs.
- Deterministic trajectory tree hash: `03a7576720863e4cb17ee2e5bfba14a144d78f848d2547e9c8efa1133701d2b8`.
- Full trajectory byte verification: `complete`.

## Evidence scope

The 40 seeds quantify Monte Carlo stability within each environment. The 16 environments are not 16 independent materials domains; they are four tasks crossed with two split protocols and two related tree ensembles. Task-level external generalization is therefore based on only four tasks.

## Frozen files

| Path | Rows | SHA-256 | Authority match |
|---|---:|---|---|
| `revision_v5/15_development_freeze_lock.json` |  | `96ef1aa952b5f9cb52071cac90bddf04890501ae9af051ce49b6999153c094ef` | True |
| `revision_v5/19_selected_policy_lock.json` |  | `814d1bdee6562b3e29f78afdc86fb92a303b97c60fa4c392d83681b6b1af55f2` | True |
| `revision_v5/20_confirmation_protocol_v5_rc1.md` |  | `0c8991c1261799336eb7a1991cb004cc9e958f274031de05a3c964a27e897c29` | True |
| `revision_v5/CONFIRMATION_RESULT_LOCK_V5_RC1.json` |  | `69074fceae6030ea0e92292f95be628e09afa9e66d14524424392c17fe138b50` | True |
| `revision_v5/CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json` |  | `e960743bec1d282e9fb3c0bb01fb0c0b6a03d5744f2902e87ffeed3ad1ab366a` | True |
| `revision_v5/environment-lock.txt` |  | `22bd05ebb49d3d5e6524fd5de62c28f35792fcf43cc3c69d2f7514bc5c48bc1d` | True |
| `revision_v5/environment-final-validation-lock.txt` |  | `51380a2f155281c61855cf06591f383c0f9c6f9fc4231a99271cfca4af17fba0` | True |
| `revision_v5/manifests_v4/CONFIRMATION_FREEZE_LOCK_V5_RC1.json` |  | `cd88596a5f1cb3bbbce990945f5211e70ca7e024de86ab26a154353032d67a0e` | True |
| `revision_v5/manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv` | 3360 | `6fbe0d79906df8523fb036800ccfec17f9bcb18a8845ddcaae9dadf3ce2c52a8` | True |
| `revision_v5/results_v4/confirmation/registry.sqlite` |  | `6a67a54589b809f46883423070c1e8b37599bb49fac0e0f79a58bec65f590dc4` | True |
| `revision_v5/results_v4/confirmation/registry_snapshot.csv` | 3360 | `cf218bb8ba5d1647bf37213a83d2831fdddd3a1efc4a8d28a8f52dff6483a441` | True |
| `revision_v5/audits_v5/confirmation_trajectory_hash_inventory.csv` | 53760 | `14878052c950eab32c9059ae40d6a0faf42bbe642ae8b14cdfebcb9ad9feb2fd` | True |
| `revision_v5/tables_v5/FINAL_TABLE_LOCK_V5.json` |  | `5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d` | True |
| `revision_v5/tables_v5/v5_rc1_seed_level_endpoints_final.csv` | 3360 | `2466848a25cf7c92199387825cc9e3842c7c260df75a267ec110eea066ba485d` | True |
| `revision_v5/tables_v5/v5_rc1_primary_contrasts_final.csv` | 128 | `c73b531a2858f54da5d420eec23211eaf18aecf3f575af608101b9b7d427b453` | True |
| `revision_v5/tables_v5/v5_rc1_recovery_sensitivity_final.csv` | 8 | `d67f647950a796d7c9154520337dde2fcab51095c2ff84bd977cb7c9b11502e5` | True |
| `revision_v5/tables_v5/v5_rc1_multiplicity_sensitivity_final.csv` | 128 | `558c333e1e8fb26b65d04c680bd58c40590acc0d24481bd30c08631067509305` | True |
| `revision_v5/tables_v5/v5_rc1_environment_summary_final.csv` | 128 | `89d066689515b29c83fff4668b0c52a7ceeff66006d0effa65e1c2fae3036566` | True |

## Snapshot

A read-only metadata/authority snapshot is stored at `locks/v5_readonly_snapshot`. The 89.6 GB trajectory corpus is not duplicated; it is protected by the frozen 53,760-row inventory and deterministic tree hash.

## Git blocker

The requested branch `reviewer_p0_p1_p2_revision` could not be created at the workspace root because `.git` is empty and the root is not a valid Git repository. A separate legacy repository exists under `material-active-learning`, but it does not contain `revision_v5`; creating the branch there would not protect the V5 revision. No repository was initialized and no history was fabricated.

## Failures

- None.
