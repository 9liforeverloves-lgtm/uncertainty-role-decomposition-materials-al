#!/usr/bin/env python3
"""Apply provenance resolution Path A without changing any manifest or test."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


PKG = Path(r"D:\贝叶斯优化\最终\_code_package").resolve()
TARGET = (PKG / "reports/corrected_v5/phase5_full_benchmark.md").resolve()
BODY = (PKG / "reports/corrected_v5/phase5_statistical_analysis.md").resolve()
AMENDMENTS = (PKG / "reports/corrected_v5/amendments").resolve()
AMENDED = (AMENDMENTS / "phase5_full_benchmark_amended_lf.md").resolve()
RECORD = (AMENDMENTS / "phase5_path_a_resolution.json").resolve()
OLD = "db8a62e658f6efd17b48430a8a61b578cfa1d40c16b82817bc57d9681678698b"
LF = "9cc5a55ca76b2999bda44537ab0df48ac3e24c6046c249b5bd813ab3830a40a1"
PREFIX = (
    b"# Phase 5 corrected full benchmark\r\n\r\n"
    b"The 720-job benchmark and preregistered Phase 5D analysis are complete.\r\n\r\n"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    expected_parent = (PKG / "reports/corrected_v5").resolve()
    if TARGET.parent != expected_parent or AMENDMENTS.parent != expected_parent:
        raise RuntimeError("resolved targets escaped intended corrected_v5 directory")
    current = TARGET.read_bytes()
    if sha(current) != LF:
        raise RuntimeError("target no longer matches audited LF object")
    original = PREFIX + BODY.read_bytes()
    if sha(original) != OLD or len(original) != 4188:
        raise RuntimeError("exact original reconstruction failed")

    AMENDMENTS.mkdir(parents=True, exist_ok=True)
    if AMENDED.exists() and AMENDED.read_bytes() != current:
        raise RuntimeError("existing amended copy has unexpected content")
    AMENDED.write_bytes(current)
    if sha(AMENDED.read_bytes()) != LF:
        raise RuntimeError("amended preservation verification failed")

    TARGET.write_bytes(original)
    if sha(TARGET.read_bytes()) != OLD:
        raise RuntimeError("historical restoration verification failed")

    record = {
        "schema_version": "phase5-path-a-resolution-v1",
        "resolution": "PATH_A_RESTORE_HISTORICAL_FROZEN_FILE",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "historical_path": "reports/corrected_v5/phase5_full_benchmark.md",
        "historical_sha256": OLD,
        "historical_bytes": 4188,
        "preserved_lf_path": "reports/corrected_v5/amendments/phase5_full_benchmark_amended_lf.md",
        "preserved_lf_sha256": LF,
        "preserved_lf_bytes": 4142,
        "exact_change": "46 CRLF line endings were normalized to LF; decoded text is identical",
        "scientific_impact": "none",
        "old_manifests_modified": False,
        "old_tests_modified": False,
        "recovery_basis": (
            "fixed generator prefix from src/analyze_phase5d.py plus frozen "
            "reports/corrected_v5/phase5_statistical_analysis.md"
        ),
        "audit_sources": [
            "revision_v5/44_phase5_provenance_inventory.md",
            "revision_v5/45_phase5_hash_forensics_report.md",
            "revision_v5/audits_v5/phase5_hash_chain_audit.csv",
            "revision_v5/phase5_full_benchmark_exact_diff.patch",
        ],
    }
    RECORD.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
