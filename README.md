# Role-decomposed uncertainty evaluation in materials active learning

Code, locked machine-readable evidence, manuscript sources and reproducibility tooling for an offline materials active-learning study. Original project software is licensed under BSD-3-Clause. This repository is public. A historical experiment-data archive was published as a GitHub Release on 2026-08-17; it is separate from the planned formal software release. No formal v1.0.0 software release or Zenodo DOI has been published.

## Project summary and scientific scope

The study separates uncertainty used for interval evaluation from uncertainty used for acquisition. It covers four fixed Matbench task snapshots, study-defined IID/OOD splits, two bagged-tree surrogates and one quantile-gradient-boosting surrogate. It does not establish laboratory performance, universal superiority or a general theorem about calibration.

## Evidence architecture

- **V6:** immutable independent confirmation with seeds 7000–7039, 11 registered contrasts and 176 complete environment gates.
- **P1:** separate immutable confirmation with seeds 8200–8239, 3,520 manifest jobs, five contrasts and two P1-only multiplicity families.
- Exploratory diagnostics are not confirmatory, and P1 is never pooled with V6.
- `locks/p1_confirmation_inference_result_lock.json` binds both V6 authority hashes and P1 result tables.

## Repository map

`analysis_plan/`, `locks/` and `manifests/` contain frozen protocols and identities. `tables/` contains locked and presentation-only machine tables. `src/` and `p1_extension/` contain current code. `scripts/reproduce_*.py` are public entry points. `data_manifest/` describes upstream data without redistributing snapshots. `manuscript/` contains TeX, bibliography, figures and PDFs. `reports/public/` is the release-facing audit set.

## Quick start

Python 3.12 is required. From a clone or extracted release candidate:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install .
.venv/bin/python scripts/verify_release.py
.venv/bin/python scripts/reproduce_smoke.py --output-dir ../repro-smoke
.venv/bin/python scripts/reproduce_tables.py --output-dir ../repro-tables
.venv/bin/python scripts/reproduce_figures.py --output-dir ../repro-figures
```

On Windows replace `.venv/bin/python` with `.venv\Scripts\python.exe`. The single recommended first entry is `scripts/verify_release.py`; all output directories may be outside the repository.

## Three reproduction levels

### Level 1 — audit reproduction

Minutes: install, verify authority hashes and numeric identities, run unit tests/synthetic smoke, and inspect/compile the manuscript. It does not require raw Matbench snapshots or full experiment outputs.

### Level 2 — result reconstruction

Minutes to about one hour: rebuild presentation tables and all P1 figures from locked machine-readable tables, then compile PDFs. Figure/PDF bytes can differ across font, Matplotlib and TeX installations; numeric tables, source hashes and semantic identities are the cross-platform acceptance criteria. Fixed-container builds may additionally compare bytes.

### Level 3 — full experiment rerun

Explicit opt-in only. P1 contains 3,520 jobs and used 9.095 h elapsed on one 12-core/24-thread host with at most six concurrent workers; durable output was 68.593 GiB. CPU-hours, peak RAM and peak temporary disk were not instrumented. Full rerun requires users to retrieve upstream data and is not the minimum verification route. Locked V6/P1 evidence must never be overwritten.

## Verify published results

```bash
python scripts/verify_release.py
python -m pytest tests v6_revision/tests -q
```

The verifier returns nonzero for missing/mismatched authority, release files, secret patterns or developer absolute paths. Missing author publication metadata is reported honestly as a state gate, not as an integrity failure.

## Rebuild tables

```bash
python scripts/reproduce_tables.py --output-dir ../repro-tables
python scripts/reproduce_tables.py --output-dir ../repro-tables --verify-only
```

## Rebuild figures

```bash
python scripts/reproduce_figures.py --output-dir ../repro-figures
python scripts/reproduce_figures.py --output-dir ../repro-figures --verify-only
```

This generates 18 P1 figure sets in PDF/PNG/SVG, including main Figures 5/6 and Supplement diagnostics, without running model jobs.

## Compile manuscript

TeX Live with `pdflatex` and `bibtex`, plus Poppler for font inspection, is required:

```bash
python scripts/reproduce_manuscript.py --output-dir ../repro-manuscript
```

The two-column PDF is a generic preview, not a claimed journal template.

## Data acquisition and rights

Raw Matbench snapshots are not bundled. Retrieve official objects and generate composition-only snapshots outside the repository:

```bash
python scripts/fetch_matbench_data.py --task matbench_expt_gap --output-dir ../study-data
```

The script validates recorded upstream SHA-256 values, performs deterministic preparation and stops on mismatch. Users remain responsible for the upstream data terms. See `docs/data_reproduction.md`, `LICENSE_AND_DATA_SCOPE.md` and `reports/THIRD_PARTY_DATA_RIGHTS_MATRIX.md` before use.

## Environment and containers

`requirements-lock.txt` is the pip authority; `environment.yml` delegates to it rather than duplicating versions. `Dockerfile` provides an optional non-root Linux analysis image and does not contain raw data, secrets or LaTeX. PDF compilation remains a host/CI TeX step.

## Determinism and expected differences

CSV authorities and locks require byte-exact hashes. Rebuilt numeric tables use exact/tight numeric comparison. Matplotlib/LaTeX output can vary by platform; source-table hashes, plotted values, labels, page validity and embedded fonts are checked separately. Scientific authority files are read-only inputs.

## Testing and CI

Local Windows Python 3.12 testing is recorded under `reports/`. GitHub Actions has run online: the main-branch tests and reproducibility workflows passed on 2026-08-02, and the tests workflow passed for the historical archive tag on 2026-08-17. See `reports/ONLINE_CI_RESULTS.md` for the recorded main-branch results. macOS and online Linux TeX remain unverified.

## Citation

Use `CITATION.cff` to cite the software repository. The repository is public at `https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al`. The [historical experiment-data archive](https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al/releases/tag/research-data-archive-2026-08-17), published on 2026-08-17, preserves experiment outputs and is not a formal software release. The planned `v1.0.0` software release has not been published, and no Zenodo DOI exists.

## License

Original project software is licensed under the BSD 3-Clause License; see `LICENSE`. Rights-audited author-generated outputs are distributable within the explicit scope in `LICENSE_AND_DATA_SCOPE.md`. Third-party raw data and software retain their upstream terms and are not relicensed by this project.

## Contributing and security

See `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `SECURITY.md`. Never alter frozen authority files or submit credentials/raw third-party data.

## Known limitations and publication state

Repository: public. Historical experiment-data GitHub Release: published 2026-08-17 under `research-data-archive-2026-08-17`. Formal software release: `v1.0.0` is planned, but no `v1.0.0` tag or software Release exists yet. Zenodo DOI: not created. License: BSD-3-Clause. Docker is not claimed as PASS.

Current formal software-release gate after local validation: `READY_FOR_AUTHOR_PUBLICATION`; `PUBLIC_RELEASE_READY = false`; `SUBMISSION_READY = false`. These gate values describe the planned formal `v1.0.0` release and manuscript submission; they do not describe the repository's visibility or the already-published historical archive.
