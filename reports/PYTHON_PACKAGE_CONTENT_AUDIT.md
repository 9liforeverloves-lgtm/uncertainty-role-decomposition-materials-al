# Python package content audit

Build command: `python -m build` with isolated `setuptools==75.8.2` and `wheel==0.45.1`. Final package version: 1.0.0.

| Artifact | Bytes | SHA-256 | Members | Result |
|---|---:|---|---:|---|
| `materials_transportability_v6-1.0.0-py3-none-any.whl` | 99,482 | `b1b78f21218aa5f0a063ee3bda74ed0a9c808b712df9e194922dffefa21f1a88` | 40 | PASS |
| `materials_transportability_v6-1.0.0.tar.gz` | 95,629 | `8111c2e46154fe9126b599092fb5b33ce0c02fbac9da115d7f79de69414a51d2` | 66 | PASS |

Both artifacts contain `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES`. The wheel metadata records version 1.0.0, author Renjie Li, BSD-3-Clause license text and the BSD OSI classifier.

Archive-member scans found zero secret patterns, zero local absolute paths, zero virtual environments/caches, zero raw `materials.csv` snapshots, zero registries/result workspaces and no oversized member. The first sdist audit detected only a negative-test absolute-path literal; the test was changed to construct the forbidden prefix without embedding it, and the rebuilt artifacts passed.

Fresh wheel and sdist build, forced installation, import and version-1.0.0 assertions passed in both external Windows and WSL/Linux environments. Windows recorded 16 zero-return steps and Linux recorded 15.
