# V6 P0 matched-beta baseline identity audit

Decision: H3 and H4 must use `ORIGINAL_GG` as the final baseline. The earliest pre-development registry (`fa4ec48`) named `GG_JOINT`; the accepted alias registry resolves `GG_JOINT -> ORIGINAL_GG`. No pre-development record supports `SELECTED_GG` for these contrasts.

| Hypothesis | Earliest comparison | Alias-resolved baseline | Candidate v3 | Candidate v4 |
|---|---|---|---|---|
| H3 | `RAW_FIXED_BETA_MATCHED vs GG_JOINT` | `ORIGINAL_GG` | `SELECTED_GG` | `ORIGINAL_GG` |
| H4 | `RAW_STAGE_BETA_MATCHED vs GG_JOINT` | `ORIGINAL_GG` | `SELECTED_GG` | `ORIGINAL_GG` |

Both matched controls were fit from development-only `ORIGINAL_GG` effective-beta summaries in `tables/v6_p0_broad_effective_beta.csv`. Fixed and stage values are unchanged; their exact held-out-task sources are preserved in the machine-readable audit.

The beta identity is `ORIGINAL_GG = 1.0` and `SELECTED_GG = 0.5`. Broad-development dispatch and the V5 replay used 0.5 for `SELECTED_GG`, so Candidate v3's beta 1.0 was a metadata-only error, not a production-dispatch error and not a new V6 method.

Outcome availability is recorded at every definition point in the CSV. The final baseline decision uses only the earliest registry and alias identity, not development outcomes.

Machine-readable audit: `tables/v6_p0_matched_beta_baseline_identity_audit.csv` (SHA-256 `81a314ba57bd54e47876a48cbd144a102565132e533a5d952253ac8e435d3559`).
