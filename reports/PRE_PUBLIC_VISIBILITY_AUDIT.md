# Pre-public visibility audit

Current result: **READY_TO_MAKE_PUBLIC**, subject to explicit author confirmation.

| Gate | Result |
|---|---|
| Repository identity/default branch | PASS; target repository, private, default `main` |
| Main exact commit | `1d6fef9ca8dca3fc92877405d967dde40dcdedc6` |
| Online Ubuntu/Windows CI | PASS |
| Authority verification | PASS; V6/P1 hashes unchanged |
| Secret and absolute-path scan | PASS |
| Raw-data exclusion | PASS; raw Matbench/Materials Project data not bundled |
| Large-file policy | PASS; two enumerated processed CSVs use Git LFS |
| Package/license audit | PASS; BSD-3-Clause and notices included |
| Public visibility | NOT EXECUTED |
| `v1.0.0` tag/GitHub Release | NOT CREATED |
| Zenodo credential/draft/DOI | false / not created / null |

The repository may be changed from private to public only after the author explicitly confirms that irreversible visibility action. Zenodo publication additionally requires a securely configured production credential and a separately reviewed draft. Missing manuscript-author metadata does not invalidate the code-release audit, but it keeps `SUBMISSION_READY = false`.
