# Third-party code provenance

## Scope and method

Tracked and proposed-release source was scanned for vendor directories, copied/adapted notices, Stack Overflow references, external copyright headers, notebooks, bundled binaries, fonts and journal classes. Historical V5 imports and local experimental workspaces are not treated as project-authored release source.

| Item | Source/author | Original license | Modified? | Notice required? | Redistribution status | Action |
|---|---|---|---:|---:|---|---|
| Python dependencies | Upstream distributions in `requirements-lock.txt` | Per dependency matrix | No vendoring | If redistributed | Reference/install only | Keep out of source archive; install from package index |
| `revision_v5/` historical import | Earlier local research delivery; authorship chain not fully documented | Unresolved | Mixed | Unknown | EXCLUDE_FROM_PUBLIC_CANDIDATE | Retain only locked V6 authority extracts and current implementation |
| Standard LaTeX packages | TeX Live upstream projects | Per TeX package | No | Toolchain notices handled by TeX distribution | Build dependency only | Do not bundle TeX distribution |
| Manuscript figure fonts | DejaVu/standard system fallbacks through Matplotlib | Upstream font licenses | No font files bundled | If font redistributed | OUTPUT_ONLY | PDFs contain embedded subsets; no standalone font files |
| Matbench dataset retrieval metadata | matminer/Matbench maintainers | Matbench software MIT; data-specific upstream rights | Adapted into manifests | Citations required | DOCUMENT_AND_FETCH | Do not bundle raw snapshots pending rights decision |
| `Codex-Windows-Installer.exe` | External binary | Not audited | No | Unknown | EXCLUDE | Never include in candidate |

No Stack Overflow attribution marker, vendored package directory or proprietary journal class was identified in the proposed current-code surface. This negative scan is not proof of authorship; the author must still confirm that current project source can be licensed.

