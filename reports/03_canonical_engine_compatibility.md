# Canonical V5 engine compatibility

Status: **PASS**. V6 calls the frozen V5 loader, pymatgen Composition fallback descriptor, V5 split, surrogate, OOB, checkpoint, metric, tie-breaking and registry modules through `transportability_v6.canonical_adapter`; the old reduced modules are labeled smoke-only.

Read-only RAW replay: `matbench_expt_gap__iid_record__random_forest__raw_ucb_beta_1__seed5000`.

- `source_split_hash`: pass
- `target_split_hash`: pass
- `diagnostic_split_hash`: pass
- `initial_labeled_ids`: pass
- `every_queried_batch`: pass
- `checkpoint_definitions`: pass
- `l1_campaign_mace`: pass
- `l4_top1pct_recall_nauc`: pass
- `logical_trajectory_hash`: pass

- First divergence: `none`
- L1 campaign MACE (reference/replay): `0.047794516829533097` / `0.047794516829533097`
- L4 top-1% recall nAUC (reference/replay): `0.46726190476190477` / `0.46726190476190477`
- Logical trajectory hash: `a3638b035dbd1624933eb851ebe702f3583bc61bd7b610d949c22077816ac20c`
- Temporary V6-owned replay output: `.tmp_stage25_raw_replay_final_reports_78_relative/matbench_expt_gap__iid_record__random_forest__raw_ucb_beta_1__seed5000`

V5-RC1 was read only and was not modified.
