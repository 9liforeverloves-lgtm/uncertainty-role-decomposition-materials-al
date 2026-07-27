# Repository inventory

Generated: 2026-07-27 (Asia/Shanghai)

## Audit boundary and repository status

The active scientific revision is `revision_v5/`, not the older nested repository
`material-active-learning/`. The workspace root contains an empty `.git/` directory
and is therefore not a valid Git worktree. The nested Git repository does not contain
`revision_v5/`.

Consequently, the requested branch `reviewer_p0_p1_p2_revision` could not be created
without either initializing a new, history-free repository or placing the revision on
an unrelated legacy branch. Neither action was taken. This is a reproducibility
blocker that requires restoration of the original root Git metadata or explicit
authorization to initialize a new repository.

## Project tree

```text
E:\贝叶斯优化\
├── revision_v5\                         active V5 scientific revision (152.6 GB)
│   ├── experiments_v4\                  Python package and campaign engine
│   │   └── src\transportability_v5\
│   ├── manifests_v4\                    development/confirmation manifests and locks
│   ├── results_v4\                      raw development and confirmation outputs
│   │   └── confirmation\
│   │       ├── trajectories\            3,360 jobs; 53,760 files; 89.6 GB locked corpus
│   │       ├── registry.sqlite
│   │       └── registry_snapshot.csv
│   ├── audits_v4\ and audits_v5\        provenance, trajectory, recovery and endpoint audits
│   ├── tables_v5\                       derived and final locked tables
│   ├── figures_v5\                      generated figures and figure manifests
│   ├── manuscript_v5\                   LaTeX, PDFs, DOCX, candidate exports
│   ├── scripts\                         experiment, analysis, plotting and build entry points
│   ├── tests\                           historical V5 regression/traceability tests
│   ├── qa\                              reviewer and acceptance records
│   ├── archive\                         explicitly superseded artifacts
│   └── EXPORT_SUBMISSION_*              assembled author/reviewer packages
├── material-active-learning\            older, separate Git repository
├── transportability_study_v3_*\         V3 historical/finalization studies
├── transportability_study_v4_*\         reserved V4 CrabNet study assets
├── 最终\                                  earlier packaged code/data/results
├── reports\                              new P0/P1/P2 audit reports (outside V5)
├── locks\                                new read-only V5 authority snapshot and manifest
├── scripts\                              new V6-safe audit tooling
└── tests\                                new cross-revision regression gates
```

## Size and file distribution

`revision_v5/` contains 115,084 files totaling 152,614,936,851 bytes.
The largest components are:

| Component | Files | Bytes | Role |
|---|---:|---:|---|
| `results_v4` | 89,639 | 151,166,514,767 | raw development/confirmation outputs |
| `.venv_final_validation` | 23,520 | 697,720,117 | relocated validation environment; launcher currently broken |
| `logs_v5` | 317 | 420,477,845 | execution/test/build logs |
| `tables_v5` | 79 | 104,614,431 | derived/final tables |
| `figures_v5` | 281 | 24,532,193 | generated figures |
| `audits_v5` | 16 | 21,934,558 | active V5 evidence audits |
| `manifests_v4` | 10 | 6,930,886 | experiment definitions and locks |
| `scripts` | 71 | 743,788 | pipeline scripts |
| `experiments_v4` | 32 | 183,766 | active Python package |
| `tests` | 12 | 142,126 | V5 test sources |

## Scientific code and entry points

The active campaign package is
`revision_v5/experiments_v4/src/transportability_v5/`.

Core modules:

- `data.py`: task data loading and validation.
- `splits.py`: IID-record and chemical-system group-disjoint splits.
- `surrogates.py`: random-forest and extra-randomized bagging surrogates.
- `strategies.py`: raw, Gaussian-global and candidate-specific uncertainty/acquisition logic.
- `runner.py`: deterministic campaign execution, checkpointing, atomic Parquet/JSON output.
- `metrics.py`: campaign discovery endpoints.
- `layers.py`: calibration, CRPS and Gaussian NLL summaries.
- `statistics.py`: paired inference utilities.
- `registry.py`: SQLite job registry and legal state transitions.
- `provenance.py`: stable hashes, atomic writes and source snapshots.
- `checkpoint.py`: checkpoint persistence and completeness gates.

Principal executable scripts:

- `scripts/run_job.py`
- `scripts/run_manifest_pool.py`
- `scripts/run_reduced_canary.py`
- `scripts/build_development_manifest.py`
- `scripts/build_confirmation_manifest.py`
- `scripts/compute_frozen_endpoints.py`
- `scripts/compute_frozen_inference.py`
- `scripts/final_l4_execution_reconstruction.py`
- `scripts/generate_final_scientific_tables.py`
- `scripts/freeze_final_tables.py`
- `scripts/generate_final_figures_v2.py`
- `scripts/final_r1/build_final_r1_manuscripts.py`
- `scripts/final_r1/compile_final_r1.ps1`

## Raw data and results

The V5 confirmation freeze records four composition-based Matbench task files:

- `最终/_code_package/results/benchmark/matbench_expt_gap/materials.csv`
- `最终/_code_package/results/benchmark/matbench_mp_gap/materials.csv`
- `最终/_code_package/results/benchmark/matbench_log_gvrh/materials.csv`
- `最终/_code_package/results/benchmark/matbench_log_kvrh/materials.csv`

Their content hashes are recorded in
`revision_v5/manifests_v4/CONFIRMATION_FREEZE_LOCK_V5_RC1.json`.
The confirmation manifest contains 3,360 jobs using seeds 5000–5039.
The execution registry contains 3,354 `COMPLETED` and 6 `RECOVERED` jobs.

Raw job outputs are under
`revision_v5/results_v4/confirmation/trajectories/`. Individual trajectories
retain rounds, selected candidates, checkpoint models, diagnostic summaries,
floor-ranking audits, provenance and protocol snapshots. They do not retain all
individual diagnostic vectors required for the prospective V6 NLL audit.

## Final tables, figures and manuscript

The authoritative final V5 table lock is
`revision_v5/tables_v5/FINAL_TABLE_LOCK_V5.json`. It covers five tables,
including 3,360 seed-level endpoint rows and 128 primary contrast rows.

The current submission candidate is:

- `revision_v5/manuscript_v5/submission_candidate_v4_final_r1/manuscript_submission_candidate_v4_final_r1.tex`
- `revision_v5/manuscript_v5/submission_candidate_v4_final_r1/manuscript_submission_candidate_v4_final_r1.pdf`
- `revision_v5/manuscript_v5/submission_candidate_v4_final_r1/supplement_submission_candidate_v4_final_r1.tex`
- `revision_v5/manuscript_v5/submission_candidate_v4_final_r1/supplement_submission_candidate_v4_final_r1.pdf`
- `revision_v5/manuscript_v5/submission_candidate_v4_final_r1/references_submission_candidate_v4_final_r1.bib`

Final V5 figures are under `revision_v5/figures_v5/final_v2/`, with
`figure_manifest_v2.json` recording provenance. The final-r1 build scripts and
tables are versioned separately from the frozen V5 evidence.

## Environment files

Present:

- `revision_v5/environment-lock.txt`
- `revision_v5/environment-final-validation-lock.txt`
- `revision_v5/pyproject.toml`
- `revision_v5/experiments_v4/pyproject.toml`
- `revision_v5/reproduce.ps1`

The copied virtual environment is not portable: its launcher still references
the former `C:\Users\ROG\AppData\Local\Programs\Python\Python312\python.exe`.
Tests were therefore run with the bundled Python 3.12 runtime plus the locked
site-packages directory. This is acceptable for an audit, but not a clean public
installation validation.

Missing from the publication-grade package at this stage:

- root `README.md`, `LICENSE`, `CITATION.cff`, `CODE_OF_CONDUCT.md`,
  `CONTRIBUTING.md`;
- `environment.yml`, portable `requirements.txt` and a validated lock;
- `Dockerfile`, `Makefile`, `RUNBOOK.md`, `COMPUTE_REQUIREMENTS.md`;
- `DATA_LICENSES.md`, `THIRD_PARTY_LICENSES.md`, `KNOWN_LIMITATIONS.md`;
- archive-wide `.reproducibility_manifest.json`;
- public repository identifier/URL and validated data/code licences.

## Test coverage

Historical records report:

- 446/446 protected historical tests passed;
- 47/47 canonical Revision V5 tests passed.

The new Stage-1 gate contains 11 tests covering:

- V5 authority hashes and trajectory tree hash;
- primary table schemas and row counts;
- development/confirmation seed disjointness;
- split-role and chemical-system leakage rejection;
- deterministic score tie-breaking;
- budget-fraction campaign geometry;
- one-to-one manifest/registry consistency and terminal status counts.

All 11 new tests passed on 2026-07-27 in a newly created isolated environment.
The 47 historical V5 tests were also rerun: 45 passed and 2 failed. Both failures
are traceability-schema drift: tests still require claim IDs `C01`–`C15` and
sentence IDs `M-*`, while the current traceability tables use `C-main-*` and
`main-line-*`. The five locked-table checks pass. No V5 file was changed to
silence these failures. Full coverage measurement was not available; the current
statement is test-count and gate based, not line-coverage based.

## Current reproducibility status

- V5 lock verification: complete; all 17 enumerated authority files match.
- V5 trajectory content verification: complete; 53,760/53,760 files match.
- Final-table hash verification: complete for all five locked tables.
- Clean isolated Python environment: installed successfully from
  `revision_v5/environment-lock.txt`; new Stage-1 tests pass 11/11.
- Historical V5 regression suite: 45/47 current pass; two stale traceability-ID
  assertions fail.
- Current main/supplement PDFs: present.
- Main/supplement PDF rebuild: completed in an isolated mirror with MiKTeX
  pdfTeX 1.40.29 and BibTeX. Both builds exit 0.
- Rebuild equivalence: numerically/content equivalent, not byte exact. Main:
  9 pages and 388,383 bytes in both copies; extracted-text SHA-256 identical.
  Supplement: 14 pages and 437,113 bytes in both copies; extracted-text
  SHA-256 identical. PDF SHA-256 differs only because `/CreationDate` and
  `/ModDate` changed.
- Figure/table regeneration: historical generation scripts and logs exist;
  clean-environment regeneration remains to be validated prospectively.
- Public release: not yet validated and must not be described as publicly
  reproducible.

## Duplicated, obsolete and superseded material

The repository intentionally retains multiple historical versions. Explicitly
invalid or superseded files are recorded in
`revision_v5/34_superseded_document_registry.csv` and include
`*_INVALID_ANALYSIS*`, earlier unversioned/v1/v2 endpoint tables, pre-final
submission packages, and superseded data-quality reports.

Large duplication also exists across:

- `EXPORT_SUBMISSION_CANDIDATE_V4*`;
- `archive/superseded_*`;
- `manuscript_v5/submission_candidate_v2`, `v3`, `v4`, `v4_final`, and
  `v4_final_r1`;
- historical V3/V4 project directories at workspace level.

These were not deleted because they carry audit history and belong to the user.
The V6 release should include only an explicit allow-list of authoritative
files, with historical packages excluded from the public archive.

## Missing P0/P1 components

The existing V5 code does not yet satisfy the requested V6 acceptance gates.
Notably absent or incomplete are:

- the complete calibration-only/acquisition-only/common-interface control set;
- fixed- and stage-matched beta confirmation controls;
- scalar, power, isotonic, conformal and equivalent-DoF baselines;
- prospective individual-level NLL vector retention;
- a frozen V6 development/confirmation selection and multiplicity registry;
- a non-tree confirmation model;
- a non-UCB acquisition confirmation family;
- a genuinely external dataset adapter plus completed external experiment;
- two stronger prespecified OOD definitions;
- V6 campaign-geometry design and Historical-CS ablations;
- the V6 manuscript, supplement, figures, reports and public release package.

No claim is made that these experiments are complete merely because some
related V5 exploratory code or historical assets exist.
