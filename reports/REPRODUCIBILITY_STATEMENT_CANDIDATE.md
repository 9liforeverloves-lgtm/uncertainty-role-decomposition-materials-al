# Computational reproducibility statement candidate

The package defines three levels. Level 1 verifies V6/P1 hashes, numeric identities, tests, a synthetic smoke path and manuscript artifacts in minutes. Level 2 reconstructs presentation tables, 18 P1 figure sets and the manuscript from locked machine tables without rerunning model jobs. Level 3 is an explicit full-experiment rerun requiring upstream data and substantial storage. Local validation used Windows 11 and Python 3.12 and Ubuntu 26.04 under WSL2 with Python 3.12.13. GitHub Actions and a non-root Linux Docker definition are supplied but have not yet run on a public CI service. P1 comprised 3,520 jobs and completed in 9.095 h elapsed with at most six concurrent workers; CPU-hours, peak RAM and peak temporary disk were not instrumented.

Original project software is licensed under BSD-3-Clause. This text remains a candidate until the repository, real release tag, archive DOI and remaining author metadata are verified.
