# V6 P0 confirmation manifest dry-run audit

Final status: **READY_TO_EXECUTE_FROZEN_P0_CONFIRMATION**

| Check | Result | Detail |
|---|---:|---|
| manifest row count | PASS | 12800/12800 |
| unique job IDs | PASS | 12800 unique |
| exact confirmation seed range | PASS | 7000-7039 |
| no development or V5 seed | PASS | no intersection |
| no aliases | PASS | ['CS_JOINT', 'GG_JOINT'] |
| no H7 jobs | PASS | H7 is analysis_only |
| no duplicate canonical jobs | PASS | 12800 unique canonical keys |
| exact policy ID/beta/key consistency | PASS | all canonical ID/beta/key triples match |
| Original/Selected GG manifest identity | PASS | beta/key bindings exact |
| matched-beta task-map binding | PASS | all four frozen LOTO maps bound |
| dependency paths exist where required | PASS | all replay dependencies resolve to RAW jobs in the frozen manifest graph |
| every registered contrast has 40 paired seeds | PASS | all 11 non-analysis-only contrasts complete |
| every required strategy and baseline exists | PASS | 12 required IDs present |
| multiplicity-family members complete | PASS | 10 inferential members registered |
| frozen-map hash matches every row | PASS | 779608733b1b7e8727a28b3d08666227d69241756e30f685180ea2ca0f8909dd |
| freeze-lock hash matches every row | PASS | bea5809d5342417dc53b8210852370a3db372d1bb8bad208faac3cd87f00186a |
| V5 locks remain unchanged | PASS | 18 authority files checked |
| no output or outcome file currently exists | PASS | results/v6_p0_confirmation |
| frozen scientific identity remains exact | PASS | administrative fields excluded |
| freeze self-hashes remain valid | PASS | frozen map and lock |

## Freeze commit record

- Commit before freeze: `1b22410f8ae12de757ca5b89508b56e638e4a58e`.
- Freeze commit: `ff04a22158916b6b34ae0fa442f015f0b55f5c70`.
- Clean-tree status immediately after freeze commit and before manifest generation: `CLEAN`.
- Code-tree hash after commit: `5612c35c5e436e9b4a4b9fbaac6172181c50a257a20c5aa54c38bcb7298b4f57`.

## Execution boundary

- The manifest was generated only after the freeze commit.
- This was a structural dry run; no confirmation worker or job was started.
- No confirmation output or outcome file was read.
- Final execution approval is still required.

## Exact blockers

- None.
