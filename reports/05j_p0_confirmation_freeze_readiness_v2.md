# V6 P0 confirmation freeze-readiness v2

Final status: **READY_FOR_HUMAN_FREEZE_APPROVAL**

| Automated check | Result | Detail |
|---|---:|---|
| all candidate self-hashes | PASS | {"v6_p0_confirmation_selection_map_CANDIDATE.json": true, "v6_p0_confirmation_selection_map_CANDIDATE_v2.json": true, "v6_p0_confirmation_selection_map_CANDIDATE_v3.json": true} |
| source-table hashes | PASS | 12/12 match |
| no duplicate aliases | PASS | {"CS_JOINT": "SELECTED_CS", "GG_JOINT": "ORIGINAL_GG"} |
| strategy-to-endpoint consistency | PASS | [{"baseline_id": "RAW", "contrast_id": "H1", "endpoint": "L1", "strategy_id": "GG_CALIBRATION_ONLY"}, {"baseline_id": "RAW", "contrast_id": "H5A", "endpoint": "L1", "strategy_id": "CS_CALIBRATION_ONLY"}, {"baseline_id": "RAW", "contrast_id": "H2A", "endpoint": "L4", "strategy_id": "GG_ACQUISITION_ONLY"}, {"baseline_id": "RAW", "contrast_id": "H2B", "endpoint": "L4", "strategy_id": "ORIGINAL_GG"}, {"baseline_id": "RAW", "contrast_id": "H5B", "endpoint": "L4", "strategy_id": "CS_ACQUISITION_ONLY"}, {"baseline_id": "RAW", "contrast_id": "H5C", "endpoint": "L4", "strategy_id": "SELECTED_CS"}, {"baseline_id": "ORIGINAL_GG", "contrast_id": "H3", "endpoint": "L4", "strategy_id": "RAW_FIXED_BETA_MATCHED"}, {"baseline_id": "ORIGINAL_GG", "contrast_id": "H4", "endpoint": "L4", "strategy_id": "RAW_STAGE_BETA_MATCHED"}, {"baseline_id": "IDENTITY_CONTROL", "contrast_id": "H6A", "endpoint": "L1", "strategy_id": "SCALAR_TEMPERATURE_NLL"}, {"baseline_id": "IDENTITY_CONTROL", "contrast_id": "H6B", "endpoint": "L1", "strategy_id": "SCALAR_TEMPERATURE_RESIDUAL_RATIO"}, {"baseline_id": "SELECTED_CS", "contrast_id": "H6", "endpoint": "L1", "strategy_id": "SCALAR_TEMPERATURE_RESIDUAL_RATIO"}] |
| contrast-to-family membership | PASS | 10 inferential hypotheses assigned exactly once |
| exactly one canonical job per task/split/model/seed/strategy | PASS | in-memory uniqueness gate 14080/14080; no manifest persisted |
| confirmation seed prohibition | PASS | production runner blocks 7000-7039; candidate remains non-frozen |
| development/confirmation seed disjointness | PASS | intersection=[] |
| V5 authority hashes unchanged | PASS | {"checked_files": 18, "checks": [{"expected_sha256": "96ef1aa952b5f9cb52071cac90bddf04890501ae9af051ce49b6999153c094ef", "match": true, "observed_sha256": "96ef1aa952b5f9cb52071cac90bddf04890501ae9af051ce49b6999153c094ef", "path": "revision_v5/15_development_freeze_lock.json"}, {"expected_sha256": "814d1bdee6562b3e29f78afdc86fb92a303b97c60fa4c392d83681b6b1af55f2", "match": true, "observed_sha256": "814d1bdee6562b3e29f78afdc86fb92a303b97c60fa4c392d83681b6b1af55f2", "path": "revision_v5/19_selected_policy_lock.json"}, {"expected_sha256": "0c8991c1261799336eb7a1991cb004cc9e958f274031de05a3c964a27e897c29", "match": true, "observed_sha256": "0c8991c1261799336eb7a1991cb004cc9e958f274031de05a3c964a27e897c29", "path": "revision_v5/20_confirmation_protocol_v5_rc1.md"}, {"expected_sha256": "69074fceae6030ea0e92292f95be628e09afa9e66d14524424392c17fe138b50", "match": true, "observed_sha256": "69074fceae6030ea0e92292f95be628e09afa9e66d14524424392c17fe138b50", "path": "revision_v5/CONFIRMATION_RESULT_LOCK_V5_RC1.json"}, {"expected_sha256": "e960743bec1d282e9fb3c0bb01fb0c0b6a03d5744f2902e87ffeed3ad1ab366a", "match": true, "observed_sha256": "e960743bec1d282e9fb3c0bb01fb0c0b6a03d5744f2902e87ffeed3ad1ab366a", "path": "revision_v5/CONFIRMATION_TRAJECTORY_CONTENT_LOCK_V5_RC1.json"}, {"expected_sha256": "22bd05ebb49d3d5e6524fd5de62c28f35792fcf43cc3c69d2f7514bc5c48bc1d", "match": true, "observed_sha256": "22bd05ebb49d3d5e6524fd5de62c28f35792fcf43cc3c69d2f7514bc5c48bc1d", "path": "revision_v5/environment-lock.txt"}, {"expected_sha256": "51380a2f155281c61855cf06591f383c0f9c6f9fc4231a99271cfca4af17fba0", "match": true, "observed_sha256": "51380a2f155281c61855cf06591f383c0f9c6f9fc4231a99271cfca4af17fba0", "path": "revision_v5/environment-final-validation-lock.txt"}, {"expected_sha256": "cd88596a5f1cb3bbbce990945f5211e70ca7e024de86ab26a154353032d67a0e", "match": true, "observed_sha256": "cd88596a5f1cb3bbbce990945f5211e70ca7e024de86ab26a154353032d67a0e", "path": "revision_v5/manifests_v4/CONFIRMATION_FREEZE_LOCK_V5_RC1.json"}, {"expected_sha256": "6fbe0d79906df8523fb036800ccfec17f9bcb18a8845ddcaae9dadf3ce2c52a8", "match": true, "observed_sha256": "6fbe0d79906df8523fb036800ccfec17f9bcb18a8845ddcaae9dadf3ce2c52a8", "path": "revision_v5/manifests_v4/CONFIRMATION_JOB_MANIFEST_V5_RC1.csv"}, {"expected_sha256": "6a67a54589b809f46883423070c1e8b37599bb49fac0e0f79a58bec65f590dc4", "match": true, "observed_sha256": "6a67a54589b809f46883423070c1e8b37599bb49fac0e0f79a58bec65f590dc4", "path": "revision_v5/results_v4/confirmation/registry.sqlite"}, {"expected_sha256": "cf218bb8ba5d1647bf37213a83d2831fdddd3a1efc4a8d28a8f52dff6483a441", "match": true, "observed_sha256": "cf218bb8ba5d1647bf37213a83d2831fdddd3a1efc4a8d28a8f52dff6483a441", "path": "revision_v5/results_v4/confirmation/registry_snapshot.csv"}, {"expected_sha256": "14878052c950eab32c9059ae40d6a0faf42bbe642ae8b14cdfebcb9ad9feb2fd", "match": true, "observed_sha256": "14878052c950eab32c9059ae40d6a0faf42bbe642ae8b14cdfebcb9ad9feb2fd", "path": "revision_v5/audits_v5/confirmation_trajectory_hash_inventory.csv"}, {"expected_sha256": "5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d", "match": true, "observed_sha256": "5ffc2652368ea7399bf3c1f43c49d5ab989396e379bd7943d0010a118708074d", "path": "revision_v5/tables_v5/FINAL_TABLE_LOCK_V5.json"}, {"expected_sha256": "2466848a25cf7c92199387825cc9e3842c7c260df75a267ec110eea066ba485d", "match": true, "observed_sha256": "2466848a25cf7c92199387825cc9e3842c7c260df75a267ec110eea066ba485d", "path": "revision_v5/tables_v5/v5_rc1_seed_level_endpoints_final.csv"}, {"expected_sha256": "c73b531a2858f54da5d420eec23211eaf18aecf3f575af608101b9b7d427b453", "match": true, "observed_sha256": "c73b531a2858f54da5d420eec23211eaf18aecf3f575af608101b9b7d427b453", "path": "revision_v5/tables_v5/v5_rc1_primary_contrasts_final.csv"}, {"expected_sha256": "d67f647950a796d7c9154520337dde2fcab51095c2ff84bd977cb7c9b11502e5", "match": true, "observed_sha256": "d67f647950a796d7c9154520337dde2fcab51095c2ff84bd977cb7c9b11502e5", "path": "revision_v5/tables_v5/v5_rc1_recovery_sensitivity_final.csv"}, {"expected_sha256": "558c333e1e8fb26b65d04c680bd58c40590acc0d24481bd30c08631067509305", "match": true, "observed_sha256": "558c333e1e8fb26b65d04c680bd58c40590acc0d24481bd30c08631067509305", "path": "revision_v5/tables_v5/v5_rc1_multiplicity_sensitivity_final.csv"}, {"expected_sha256": "89d066689515b29c83fff4668b0c52a7ceeff66006d0effa65e1c2fae3036566", "match": true, "observed_sha256": "89d066689515b29c83fff4668b0c52a7ceeff66006d0effa65e1c2fae3036566", "path": "revision_v5/tables_v5/v5_rc1_environment_summary_final.csv"}], "passed": true, "schema_version": "v5-frozen-manifest-v1"} |
| recovery replay 8/8 | PASS | 8/8 accepted |
| no confirmation outcomes exist | PASS | [] |
| every non-alias strategy has one explicit role | PASS | 22/22 canonical methods |
| Candidate v4 self-hash | PASS | d2b6513c171a12c6edd48a6648115b7fd188ad396af89bd50014efc65c7ee25b |
| matched-beta source strategy equals registered joint baseline | PASS | H3/H4 source=baseline=ORIGINAL_GG |
| alias-resolved baseline identity | PASS | GG_JOINT -> ORIGINAL_GG |
| Original/Selected GG policy identity and nominal beta | PASS | ORIGINAL_GG=1.0; SELECTED_GG=0.5; exact V5 provenance present |
| effective beta equals nominal beta times fitted scale | PASS | scale=2.4 control gives 2.4 and 1.2 |
| no strategy-name/policy mismatch and no manifest substitution | PASS | canonical ID, nominal beta, and policy key are bound |
| analysis-only hypotheses generate no jobs | PASS | H7 has 11 explicit contrasts and no job |
| RAW policy is explicit and immutable | PASS | universal beta-1 mechanism reference |
| updated code-tree hash | PASS | 5612c35c5e436e9b4a4b9fbaac6172181c50a257a20c5aa54c38bcb7298b4f57 |
| no confirmation manifest generated | PASS | manifests/v6_p0_confirmation_manifest.csv |

## Scientific identity decisions

- H3/H4 baseline: `ORIGINAL_GG`, resolved from the earliest `GG_JOINT` registration.
- GG betas: `ORIGINAL_GG = 1.0`; V5 `SELECTED_GG = 0.5`.
- V6 `RAW`: universal beta-1 mechanism reference (choice A), not the V5 task-specific selected RAW policy.
- H7: analysis-only descriptive direction table; no singular strategy/baseline, job, familywise binary claim, or confirmation job.

## Boundary conditions

- Candidate v4 remains `CANDIDATE_DEVELOPMENT_ONLY_NOT_FROZEN`.
- No confirmation manifest was generated or executed.
- Confirmation seeds 7000-7039 remain prohibited and were not run.
- Broad development was not rerun.
- Development endpoints and matched-beta values were not changed.

## Exact blockers

- None. Human freeze approval is still required; this report does not freeze Candidate v4.
