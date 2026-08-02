# BSD-3-Clause release validation report

Validation date: 2026-08-02. Overall result: **PASS**. State: `READY_FOR_AUTHOR_PUBLICATION`.

## License and rights

- Root license SHA-256: `8cffe8837f038e3a6ebe69977b66f39ae90dd895cf31530e3885e48ea54b20bc`; the legal body matches SPDX `BSD-3-Clause` after substituting the authorized copyright line.
- Copyright identity: `Copyright (c) 2026 Renjie Li`.
- Author config: BSD-3-Clause, public code true, enumerated processed outputs true, raw data false.
- Old license-decision files are absent from the root/candidate and preserved as resolved records under `reports/archive/`.
- Dependency license audit: 47/47 verified, unresolved 0.
- Third-party software/data remain under upstream terms; raw task records are absent.

## Scientific integrity

The final machine validator confirms all 14 V6/P1 authority hashes, five P1 contrasts and 3,520 unique manifest jobs. It separately verifies all 14 source/generated files bound by `locks/final_optimization_presentation_lock.json` and the P1 figure-source inventory hash. No effect, interval, p-value, BH family, seed range, contrast, strategy mapping or authority CSV changed.

## Python packages

`python -m build` produced the 1.0.0 wheel and sdist. Both contain `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES`; package scans found no raw data, secret, environment, result store or local absolute path. Both artifacts were built and forcibly installed in fresh Windows and WSL/Linux environments; imports and distribution version assertions passed.

## External reproduction

- Windows: PASS, 16 zero-return steps; package build/install, pip check, CLI, locks, smoke, tables, 18 figure sets, manuscript compilation, 146 passed/1 skipped and post-run verification.
- Ubuntu 26.04/WSL2: PASS, 15 zero-return steps; equivalent flow excluding TeX compilation, which is explicitly `NOT TESTED`; 146 passed/1 skipped.
- Docker/Podman: `NOT TESTED` because neither executable is installed.
- GitHub Actions: YAML parsed locally; online status `NOT_RUN`.

## Publication truthfulness

A real private repository now exists at `https://github.com/9liforeverloves-lgtm/uncertainty-role-decomposition-materials-al`; it is not yet public. Archive DOI remains null and no real `v1.0.0` tag exists. CFF/Zenodo/CodeMeta contain BSD-3-Clause, Renjie Li and the real private repository URL but no fabricated DOI. Final availability templates remain under `reports/` and are not inserted into the submission TeX.

Machine evidence: `reports/bsd3_release_validation_status.json`. Final gates: `PUBLIC_RELEASE_READY = false`; `SUBMISSION_READY = false`.
