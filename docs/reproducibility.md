# Reproducibility guide

## Level 1: audit reproduction

Expected time: several minutes; expected disk: below 2 GiB beyond the installed environment. Run `scripts/verify_release.py`, the tests and `scripts/reproduce_smoke.py`. This verifies immutable hashes, contrast identities, table schemas and a synthetic execution path. The fixture is not scientific data.

## Level 2: result reconstruction

Expected time: minutes to approximately one hour; expected disk: below 5 GiB. Run the table, figure and manuscript entry points with external `--output-dir` locations. Machine tables and numeric semantics are cross-platform authorities. PDF/PNG/SVG bytes are only expected to match in a fixed toolchain because fonts, renderers and compression metadata can vary.

## Level 3: full experiment rerun

Not a reviewer minimum and never the default. Users must retrieve Matbench data under upstream terms. P1 has 3,520 jobs, checkpoint/resume support and measured 9.095 h elapsed with six concurrent workers on one 12-core/24-thread Windows host. The durable local corpus is 68.593 GiB. CPU time, peak RAM and peak temporary disk were not instrumented. V6 execution scope is documented in its frozen manifests; no release command overwrites V6/P1 authority.

## Platform status

- Windows 11, Python 3.12: locally validated.
- Ubuntu LTS/Python 3.12: workflow and Docker definitions prepared; online CI not yet executed.
- macOS: unverified.
- Locale: release sources are UTF-8; tests exercise a path containing spaces and non-ASCII characters.

## Offline behavior

Level 1/2 reproduction is offline after dependencies are installed. `fetch_matbench_data.py` is the only standard entry requiring network access; it reports HTTP/checksum failures and never continues with invalid data.

