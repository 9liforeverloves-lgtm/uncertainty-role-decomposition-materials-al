# Effective-beta reconciliation

The frozen V5 Original-GG value and the accepted sentinel DRAFT value are not interchangeable. The sentinel records are now explicitly classified as `V6-P0-SENTINEL-DEVELOPMENT`: matbench_expt_gap only, two splits, Random Forest only, seeds 6000–6009, development-only.

## Paired compatibility result

For one frozen V5 seed (5000) in every 16 task/split/model environments, V6 Original-GG and Selected-GG adapters reproduce every retained V5 trajectory field exactly. The maximum absolute difference of the per-environment active-round effective-beta medians is `0` for Original-GG and `0` for Selected-GG. The full field-level evidence is in `tables/v6_v5_strategy_replay_audit.csv`.

Here, exact trajectory agreement requires exact split, retained round, endpoint, checkpoint-metadata, and canonical-domain checkpoint-model semantics. Raw checkpoint payload bytes are reported separately because the frozen V5 ExtraTrees-compatible serializer is byte-volatile even in a V5 self-replay; that explicitly controlled serialization artifact is not a scientific trajectory difference.

## Aggregated comparison

| cohort / strategy | environments | seeds | nominal beta | fitted-scale environment-balanced median | effective-beta environment-balanced median | aggregation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| V5 frozen full universe / Original GG | 16 | 40 | 1 | 3.0141121699142275 | 3.0141121699142275 | median within each of 16 task/split/model environments, then median across environments |
| V6 historical adapter paired V5 seed-5000 audit / Original GG | 16 | 1 | 1 | 2.9816780405987773 | 2.9816780405987773 | one per environment median over retained active rounds, then median across 16 environments |
| V6-P0-SENTINEL-DEVELOPMENT pre-correction aligned-OOB artifact / Original GG label retained for provenance only | 2 | 10 | 1 | 0.94214015194137402 | 0.94214015194137402 | median within the two expt-gap/RF environments, then median across those environments |
| V5 frozen full universe / Selected GG | 16 | 40 | 0.5 | 2.721374058711993 | 1.3606870293559965 | median within each of 16 task/split/model environments, then median across environments |
| V6 historical adapter paired V5 seed-5000 audit / Selected GG | 16 | 1 | 0.5 | 2.6919878567172568 | 1.3459939283586284 | one per environment median over retained active rounds, then median across 16 environments |


The frozen-manuscript Original-GG summary is approximately 2.938; the V5 full-universe calculation above retains its exact source-specific aggregation. The sentinel DRAFT fixed beta is exactly `0.94214015194137402` and is reproduced from its compact table, but it is a pre-correction aligned-OOB sentinel quantity rather than a transferable V5 Original-GG estimate.

## Mechanistic reconciliation

| item | V5 Original/Selected GG and corrected V6 adapters | accepted sentinel artifact |
| --- | --- | --- |
| scale convention | `effective beta = nominal beta × fitted scale` | same multiplicative convention |
| OOB residual target pairing | frozen V5 query-order target vector (`y[queried]`) paired with OOB predictions after the model's stable-ID ordering | aligned `model.y_train_` pairing used before the correction |
| minimum valid OOB observations | 8 | 8 |
| scale objective | V5 Gaussian-consistent global residual-ratio objective | same named objective but different pairing implementation |
| scale bounds | none | none |
| checkpoint weighting | equal weights for frozen initial/25/50/75% definitions; initial retains V5 `iloc[-1]` execution semantics | same endpoint convention in the accepted artifact |
| environment aggregation | frozen V5 universe versus paired 16-environment audit | two expt-gap/RF environments only |

The discrepancy is not an inverse-scale convention. Scope and aggregation differ, but the decisive implementation mismatch was OOB target ordering: the pre-correction V6 sentinel adapter used aligned targets, whereas frozen V5 uses the historical query-order target vector after the surrogate sorts its training records. The production adapter was corrected before broad development by preserving that legacy order only for named V5-derived GG/CS strategies. The accepted sentinel artifacts were not altered; they remain a clearly labeled, non-transferable development record.

Reconciliation table SHA-256: `e69c4cc2fe592155f5d73597aeb6aa464fcc04990e44c4ee687761f9131689c4`.
