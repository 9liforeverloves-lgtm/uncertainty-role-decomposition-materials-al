# Public release security audit

Status: **PASS for the BSD3 curated candidate**.

The builder and verifier scan public executable/document surfaces for common private-key, GitHub-token and AWS access-key patterns, non-approved email addresses and operational developer absolute paths. Candidate and Python-package scans returned zero secret findings, zero package absolute paths and zero raw-data matches.

The release excludes credentials, local virtual environments, caches, raw Matbench/Materials Project records, 68+ GiB execution stores, unrestricted logs, unrelated installers, private editorial documents and temporary LaTeX files. The only `results/` path retained is an explicit `DATA_NOT_BUNDLED.md` compatibility marker with no scientific record.

Immutable V5 provenance retains historical paths inside frozen evidence files; these are non-executable audit literals. The portability regression test no longer embeds an absolute-path literal and constructs its forbidden prefixes at runtime. Windows and Linux external runs both succeeded from unrelated paths containing spaces and Unicode/UTF-8 text.

The three GitHub Actions YAML files contain no token or credential. They do not run a full 3,520-job experiment and do not publish to Zenodo. Online Windows, Ubuntu and reproducibility workflows passed on final private main commit `1906979ca00aab4d440367301439baab92f1e42b`; public-source reproduction remains `NOT_RUN` until publication is authorized.
