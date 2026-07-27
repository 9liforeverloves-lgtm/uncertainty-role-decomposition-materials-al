# Stage-2.5 test validation

- Clean production-validation environment: Python 3.12, `pymatgen==2024.10.29`, V5-compatible dependencies from `requirements-lock.txt`.
- Full test suite: `78 passed` (one expected deprecation warning for the retained smoke compatibility alias).
- Read-only production-adapter validation: 13 actual production strategy adapters exercised on a frozen V5 RAW checkpoint.
