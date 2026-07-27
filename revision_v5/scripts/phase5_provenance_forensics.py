#!/usr/bin/env python3
"""Inventory and forensic audit for the historical Phase 5 Markdown drift."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


REV = Path(__file__).resolve().parents[1]
PKG = Path(r"D:\贝叶斯优化\最终\_code_package")
TARGET = PKG / "reports/corrected_v5/phase5_full_benchmark.md"
STAT = PKG / "reports/corrected_v5/phase5_statistical_analysis.md"
MANIFEST = PKG / "reports/corrected_v5/phase5_frozen_manifest.json"
ORIGINAL_HASH = "db8a62e658f6efd17b48430a8a61b578cfa1d40c16b82817bc57d9681678698b"
CURRENT_HASH = "9cc5a55ca76b2999bda44537ab0df48ac3e24c6046c249b5bd813ab3830a40a1"
PREFIX_CRLF = (
    b"# Phase 5 corrected full benchmark\r\n\r\n"
    b"The 720-job benchmark and preregistered Phase 5D analysis are complete.\r\n\r\n"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path),
        "bytes": stat.st_size,
        "sha256": sha(path.read_bytes()),
        "created_utc": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def references() -> list[str]:
    found = []
    skip = {".venv_corrected_v1", ".pytest_cache"}
    for path in PKG.rglob("*"):
        if not path.is_file() or any(part in skip or part.startswith(".pytest_tmp") for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".json", ".md", ".csv", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "phase5_full_benchmark.md" in text:
            found.append(path.relative_to(PKG).as_posix())
    return sorted(found)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest_entry = next(
        x for x in manifest["report_sha256"]
        if x["path"] == "reports/corrected_v5/phase5_full_benchmark.md"
    )
    stat_bytes = STAT.read_bytes()
    original = PREFIX_CRLF + stat_bytes
    current = TARGET.read_bytes()
    assert len(original) == manifest_entry["bytes"] == 4188
    assert sha(original) == manifest_entry["sha256"] == ORIGINAL_HASH
    assert sha(current) == CURRENT_HASH
    assert current.replace(b"\n", b"\r\n") == original
    assert original.replace(b"\r\n", b"\n") == current

    refs = references()
    amendment = PKG / "reports/corrected_v8_5b/phase1_8_provenance_amendment.json"
    later_manifest = PKG / "release/corrected_v9_2_2b/manifests/upstream_integrity_manifest.json"
    tests = [
        PKG / "tests/test_phase5_1.py",
        PKG / "tests/test_phase5_2_figures.py",
        PKG / "tests/test_phase6_audit.py",
    ]

    inventory = f"""# Phase 5 provenance inventory

Generated: {datetime.now(timezone.utc).isoformat()}

## Decision-relevant inventory

| Version/object | Path | Bytes | SHA-256 | Modified UTC | Git commit | Status |
|---|---|---:|---|---|---|---|
| Reconstructed original | deterministic bytes from `src/analyze_phase5d.py` prefix + frozen `phase5_statistical_analysis.md` | 4,188 | `{ORIGINAL_HASH}` | frozen manifest: 2026-07-12 | unavailable; repository has no usable `.git` | historical, exactly recoverable |
| Current LF copy | `{TARGET}` | 4,142 | `{CURRENT_HASH}` | {metadata(TARGET)["modified_utc"]} | unavailable | current before Path A |
| Frozen statistical body | `{STAT}` | 4,075 | `{metadata(STAT)["sha256"]}` | {metadata(STAT)["modified_utc"]} | unavailable | historical authority; matches frozen manifest |
| Original manifest | `{MANIFEST}` | {metadata(MANIFEST)["bytes"]:,} | `{metadata(MANIFEST)["sha256"]}` | {metadata(MANIFEST)["modified_utc"]} | unavailable | immutable historical manifest |
| Phase 8.5B amendment | `{amendment}` | {metadata(amendment)["bytes"]:,} | `{metadata(amendment)["sha256"]}` | {metadata(amendment)["modified_utc"]} | unavailable | later explanatory record; contains a one-character typo in the original hash |
| Later integrity manifest | `{later_manifest}` | {metadata(later_manifest)["bytes"]:,} | `{metadata(later_manifest)["sha256"]}` | {metadata(later_manifest)["modified_utc"]} | unavailable | records the LF copy as supporting documentation |

No second on-disk copy named `phase5_full_benchmark.md` was found. The original is nevertheless exactly recoverable because its frozen 4,075-byte body remains byte-identical to the manifest and the generating prefix is explicit in `src/analyze_phase5d.py`.

## Failed-test expectations

All three failing tests resolve through `reports/corrected_v5/phase5_frozen_manifest.json` and therefore expect `{ORIGINAL_HASH}`:

- `tests/test_phase5_1.py::test_phase5_frozen_hashes_unchanged`
- `tests/test_phase5_2_figures.py::test_phase5_and_phase5_1_hashes_unchanged`
- `tests/test_phase6_audit.py::test_phase6_upstream_frozen_manifests_are_unchanged`

## Reference inventory

{chr(10).join(f"- `{x}`" for x in refs)}

## Version classification

- Historical: reconstructed CRLF object, 4,188 bytes.
- Current before resolution: LF-normalized object, 4,142 bytes.
- Amended/supporting: the LF object as recorded by later Phase 8.5B/9.2.2 manifests.
- Unknown versions: none found.
- Git history: unavailable; `D:\\贝叶斯优化\\最终\\_code_package` is not a Git repository.
"""
    (REV / "44_phase5_provenance_inventory.md").write_text(inventory, encoding="utf-8")

    rows = [
        {
            "object_id": "historical_original_reconstructed",
            "path": "reports/corrected_v5/phase5_full_benchmark.md",
            "bytes": len(original),
            "sha256": sha(original),
            "timestamp_utc": "manifest created 2026-07-12T05:58:06.5637249Z",
            "source": "generator prefix + frozen phase5_statistical_analysis.md",
            "status": "historical_exactly_recoverable",
            "scientific_impact": "none",
            "notes": "CRLF line endings; content identical after newline normalization",
        },
        {
            "object_id": "current_before_path_a",
            "path": "reports/corrected_v5/phase5_full_benchmark.md",
            "bytes": len(current),
            "sha256": sha(current),
            "timestamp_utc": metadata(TARGET)["modified_utc"],
            "source": "current filesystem",
            "status": "lf_normalized_documentation_copy",
            "scientific_impact": "none",
            "notes": "LF line endings; 46 CR bytes removed; no textual change",
        },
        {
            "object_id": "frozen_body_authority",
            "path": "reports/corrected_v5/phase5_statistical_analysis.md",
            "bytes": len(stat_bytes),
            "sha256": sha(stat_bytes),
            "timestamp_utc": metadata(STAT)["modified_utc"],
            "source": "current filesystem and original manifest",
            "status": "historical_unchanged",
            "scientific_impact": "authoritative",
            "notes": "body used to recover exact original",
        },
        {
            "object_id": "phase8_5b_amendment_record",
            "path": "reports/corrected_v8_5b/phase1_8_provenance_amendment.json",
            "bytes": metadata(amendment)["bytes"],
            "sha256": metadata(amendment)["sha256"],
            "timestamp_utc": metadata(amendment)["modified_utc"],
            "source": "later amendment",
            "status": "defective_hash_reference",
            "scientific_impact": "none",
            "notes": "records ...17dc... instead of manifest ...17bc...; author/process identity absent",
        },
    ]
    audit = REV / "audits_v5/phase5_hash_chain_audit.csv"
    audit.parent.mkdir(parents=True, exist_ok=True)
    with audit.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    patch = f"""--- phase5_full_benchmark.original.md
+++ phase5_full_benchmark.current_before_path_a.md
@@ exact-byte-diff @@
- original bytes: 4188
+ current bytes: 4142
- original SHA-256: {ORIGINAL_HASH}
+ current SHA-256: {CURRENT_HASH}
- line terminators: 46 x CRLF (0d0a)
+ line terminators: 46 x LF (0a)
  UTF-8 decoded lines: identical, 46/46
  normalized-LF bytes: identical
  added textual lines: 0
  deleted textual lines: 0
  changed textual lines: 0
  numerical changes: 0
  scientific interpretation changes: 0
"""
    (REV / "phase5_full_benchmark_exact_diff.patch").write_text(patch, encoding="utf-8")
    diff_hash = sha((REV / "phase5_full_benchmark_exact_diff.patch").read_bytes())

    report = f"""# Phase 5 hash forensics report

## Finding

The file changed only by newline normalization: 46 CRLF terminators became LF. No decoded line, number, table reference, conclusion, or scientific claim changed.

## Questions answered

1. **Changed file:** `reports/corrected_v5/phase5_full_benchmark.md`.
2. **Changed lines:** no textual lines. Exact byte change: remove one `0d` byte before each of 46 `0a` bytes.
3. **Timing:** original manifest written 2026-07-12T05:58:06Z; target modified 2026-07-16T02:53:26Z.
4. **Reason:** exact evidence establishes newline normalization. No record identifies the person or process that performed it.
5. **Classification:** formatting-only documentation drift.
6. **Downstream computation:** none. Code writes this Markdown; no numerical script reads it. Later uses are manifests, tests, audits, QC prose, and release packaging.
7. **Amendment timing:** Phase 8.5B amendment modified 2026-07-16T03:28:19Z, after the target modification and before later release copies.
8. **Amendment completeness:** it records path, current hash, timestamp, reason/classification, and scientific impact. Its old hash is defective (`...17dc...` rather than manifest `...17bc...`); it lacks author/process identity. It is not a complete Path B chain.
9. **Original recovery:** yes. The deterministic reconstruction is 4,188 bytes and exactly matches `{ORIGINAL_HASH}`.
10. **Scientific equivalence:** yes. After CRLF-to-LF normalization, the byte streams are identical.

## Dependency analysis

The Markdown is supporting human-readable output. Frozen numerical tables, statistical body, figures, and trajectory artifacts remain unchanged. Restoring the CRLF object does not change any scientific computation. The LF object must be retained under a versioned amendment path for later documentation manifests.

## Resolution

**Path A.** Path B is unnecessary and its existing old-hash record is defective. Preserve the LF object, restore the exact CRLF object at the historical path, keep all old manifests/tests unchanged, and rerun the complete suites.

Diff artifact SHA-256: `{diff_hash}`.
"""
    (REV / "45_phase5_hash_forensics_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({
        "original_sha256": sha(original),
        "current_sha256": sha(current),
        "references": len(refs),
        "resolution": "A",
    }, indent=2))


if __name__ == "__main__":
    main()
