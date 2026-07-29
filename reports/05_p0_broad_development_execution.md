# P0 broad development execution

Status: **COMPLETED, development-only**. Evidence class: `V6-P0-BROAD-DEVELOPMENT`.

The final prospective broad lock `edca62dd041f7ab6d02bfd63af381c60bb26dfee187df6d290c686848f202f4b` covers `2720` jobs: 16 task/split/model environments × 10 non-overlapping development seeds × 17 registered jobs. The final registry counts are `{'COMPLETED': 2720}`.

Scope: four frozen Matbench tasks, IID-record and chemical-system group-disjoint splits, Random Forest and ExtraTrees-compatible ensembles, seeds 6100–6109. The sentinel cohort remains separate and is not pooled into this table.

- Manifest: `manifests/v6_p0_broad_development_manifest.csv` (`b8d0eca1d3d0625203d04458fcd07232999ecadaa5ca94241292cd271e71b496`)
- Final run root: `results/v6_p0_broad_development/final_broad_development`
- Endpoint table: `tables/v6_p0_broad_seed_endpoints.csv`
- Effective-beta table: `tables/v6_p0_broad_effective_beta.csv`
- Candidate-only LOTO map: `analysis_plan/v6_p0_confirmation_selection_map_CANDIDATE.json`

No confirmation manifest or confirmation jobs were generated. Seeds 7000–7039 were neither read nor run. This report stops at broad-development analysis.
