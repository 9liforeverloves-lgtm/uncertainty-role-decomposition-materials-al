# Git baseline report

## Repository initialization

- Repository type: new history-free Git repository.
- Historical provenance restored: **no**.
- Branch: `reviewer_p0_p1_p2_revision`.
- First commit message: `V5 audited baseline import before V6 development`.
- First commit SHA-1: `9461a725f536ed5bb4dfb74d941b508c219bb821`.
- First commit tracked files: 176.

The empty workspace `.git` directory was initialized only after the Stage-1
hash audit. No V5 authority or result file was edited.

## Tracked allow-list

- V5 scientific Python source and tests;
- V5 experiment manifests and compact lock files;
- V5 trajectory hash inventory, not trajectory content;
- five compact frozen final tables;
- final-r1 LaTeX and BibTeX source;
- V5 reproducibility scripts and environment locks;
- Stage-1 audit reports, tests and frozen manifest;
- V6 source, tests, configuration and prospective analysis plans;
- root documentation and dependency specifications.

## Excluded large or mutable assets

- `revision_v5/results_v4/`, including the 150+ GB result corpus;
- V5/V6 trajectory directories and SQLite execution stores;
- model checkpoints and `*.joblib`, `*.pkl`, `*.pt`, `*.ckpt`;
- intermediate Parquet/Feather shards;
- virtual environments and build caches;
- LaTeX intermediates and temporary logs;
- legacy V3/V4 workspaces and duplicate delivery packages.

The Git object store after the first commit was approximately 3.78 MiB.

## V5 verification

- Before initialization: 18/18 authority files matched; 53,760/53,760
  trajectory files matched their frozen SHA-256 inventory.
- Immediately before the first commit: V5 hash regression 2/2 passed.
- After Stage-2 changes: V5 authority/table/registry regression 5/5 passed.
- `git diff -- revision_v5` after Stage-2 implementation: empty.

## Authority-count reconciliation

The original compact audit list contained 17 files. The final check contains
18 because it additionally hashes the authoritative
`revision_v5/results_v4/confirmation/registry.sqlite`. This explains the count
difference; it is not a V5 content change.
