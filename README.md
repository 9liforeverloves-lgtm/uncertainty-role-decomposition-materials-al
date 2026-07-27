# Calibration and sequential discovery in materials screening

## Purpose

This repository audits and extends an offline composition-based materials-screening study. The
scientific question is whether uncertainty rescaling improves predictive-interval calibration,
sequential top-tail discovery, both, or neither.

## Evidence hierarchy

- **V5-RC1**: frozen confirmatory evidence. Immutable.
- **V6-MECH**: calibration/acquisition decoupling and mechanism controls.
- **V6-EXT**: non-tree, non-UCB and external-dataset evidence.
- **V6-SENS**: OOD, campaign-geometry and ablation sensitivity.
- **V6-REP**: reproducibility and numerical diagnostics.

V5 and V6 are never pooled. Smoke runs are non-inferential engineering validation.

## Layout

- `revision_v5/`: frozen V5 source, compact tables, manuscript and authority files.
- `locks/`: V5 frozen manifest and read-only compact authority snapshot.
- `v6_revision/src/transportability_v6/`: V6 implementation under development.
- `analysis_plan/`: prospective V6 hypotheses, endpoints, seeds and multiplicity rules.
- `tests/`: V5 immutability and cross-revision gates.
- `v6_revision/tests/`: V6 unit and end-to-end tests.
- `configs/smoke/`: non-inferential smoke manifests.
- `results/v6_smoke/`: smoke registries, results and manifests.
- `reports/`: audit and validation reports.

## Installation

Minimal smoke environment:

```powershell
python -m venv .venv_smoke
.\.venv_smoke\Scripts\python.exe -m pip install -r requirements.txt
.\.venv_smoke\Scripts\python.exe -m pip install -e .
```

Locked validation:

```powershell
.\.venv_smoke\Scripts\python.exe -m pip install -r requirements-lock.txt
```

## Profiles

- `smoke`: deterministic synthetic campaign plus one reduced real task; no scientific inference.
- `reduced`: future representative development validation; not confirmatory.
- `full`: future frozen V6 confirmation. Disabled until explicit approval.

## Commands

```powershell
python -m pytest tests v6_revision\tests -q
python scripts\audit_v5_frozen.py --verify-trajectories
python -m transportability_v6.cli smoke --manifest configs\smoke\v6_smoke_manifest.json
```

## Expected smoke outputs

- `results/v6_smoke/smoke_registry.csv`
- `results/v6_smoke/smoke_result_manifest.json`
- per-campaign compact summaries and logs
- `reports/02_stage2_smoke_validation.md`

Every smoke artifact is labeled `NON-INFERENTIAL ENGINEERING VALIDATION`.

## V5 immutability

Do not edit, rerun, relabel or overwrite V5-RC1 results. Before and after any V6 change, verify
`locks/v5_frozen_manifest.json`. V6 uses separate directories, seed namespaces and evidence labels.

## Current V6 status

Stage-1 audit is complete. Stage-2 implementation and smoke validation are in progress. No V6
development or confirmation result exists. The manuscript must not cite smoke outputs.

## Limitations

The frozen study covers four Matbench tasks, two split protocols and two related tree ensembles.
Forty seeds quantify Monte Carlo stability within an environment; they are not forty independent
materials problems. External datasets, non-tree confirmation and non-UCB confirmation remain
unverified.

## Citation status

No repository DOI or public release URL has been assigned. Citation metadata remains pending.
