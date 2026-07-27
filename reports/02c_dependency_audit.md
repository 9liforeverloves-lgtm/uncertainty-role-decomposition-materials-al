# Stage-2 dependency audit

## Package layout

- Canonical package: `src/transportability_v6/`.
- Build backend: setuptools.
- Package discovery: explicit `src` layout.
- CLI: `transportability-v6 = transportability_v6.cli:main`.

## Dependency groups

- Core: NumPy, pandas, SciPy, scikit-learn, PyArrow, joblib.
- Test: pytest.
- Plotting: matplotlib, Pillow.
- Materials: pymatgen.
- Deep learning: PyTorch range; optional and not installed for smoke.
- Development: build, pytest, Ruff.

P1 deep-learning dependencies are excluded from the minimal smoke environment.

## Files

- `pyproject.toml`: package metadata, discovery, CLI and optional groups.
- `requirements.txt`: minimal direct smoke/test dependencies.
- `requirements-lock.txt`: clean-environment resolved versions.
- `environment.yml`: Python 3.12 Conda wrapper around the pip lock.

## Clean-install validation

- Environment created from bundled Python 3.12.13.
- Installed `requirements.txt`.
- Installed root project editable with `--no-deps`.
- Package imported from `src/transportability_v6`.
- `pip check`: no broken requirements.
- Tests: 59/59 passed.
- CLI smoke: 8/8 jobs completed.

## Known limits

- The lock is Windows/Python-3.12 validated; Linux wheels/container remain untested.
- Python patch version is 3.12.13, whereas the historical V5 environment recorded
  3.12.3. V6 is separate evidence and declares `>=3.12,<3.13`.
- Optional plotting, materials and deep-learning groups were not installed in
  the minimal clean smoke environment.
