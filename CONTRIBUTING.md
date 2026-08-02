# Contributing

Before proposing a change, run `python scripts/verify_release.py` and the test
suite described in README. Do not modify frozen files under `locks/`, frozen
registries, confirmation manifests or authority CSVs. Derived presentation
changes must remain traceable to those sources.

Use a focused branch, add tests for behavioral changes, keep paths portable
and UTF-8, and never commit credentials, local environments, raw third-party
data or full experimental output stores. Scientific changes require a new
prospective protocol and evidence stage; they cannot be folded into V6/P1.

