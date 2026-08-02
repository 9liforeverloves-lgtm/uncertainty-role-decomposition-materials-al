# Release v1.0.0 reproducibility package

## Scope

- publish the author-authorized BSD-3-Clause source and processed-output scope;
- preserve all V6/P1 authority hashes and registered identities;
- provide Windows/Ubuntu CI, checksum verification, smoke, table/figure reconstruction and wheel/sdist builds;
- exclude raw Matbench/Materials Project records, the 68+ GiB execution workspace, environments, caches, secrets and internal artifacts;
- prepare, but do not make public or permanently publish, the v1.0.0 GitHub/Zenodo artifacts.

## Verified evidence

- V6/P1: 14 locked files unchanged; five P1 contrasts; 3,520 unique jobs;
- local Windows candidate reproduction: PASS, 16 zero-return steps;
- local WSL/Linux candidate reproduction: PASS, 15 zero-return steps; Linux TeX NOT TESTED;
- tests: 147 passed in the full workspace and 146 passed/1 skipped in data-free release copies;
- package audit: wheel and sdist contain BSD-3-Clause, NOTICE and third-party notices;
- raw-data/secret scans: PASS;
- release candidate: checksum-complete.

## Remaining online gates

The repository starts private. GitHub Actions must return real success before main/tag/release decisions. Public visibility, the annotated `v1.0.0` tag, GitHub Release and Zenodo publication require later author confirmation.
