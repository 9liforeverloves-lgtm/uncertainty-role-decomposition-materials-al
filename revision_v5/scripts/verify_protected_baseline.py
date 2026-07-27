from __future__ import annotations

import csv
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WORKSPACE = Path(r"C:\Users\ROG\Desktop\贝叶斯优化")
REVISION = WORKSPACE / "revision_v5"
ROOTS = {
    "v2_study": WORKSPACE / "最终" / "_code_package" / "transportability_study",
    "v3_exploratory": WORKSPACE / "transportability_study_v3_l1_l4_exploratory",
    "review4_3_author_package": WORKSPACE
    / "transportability_study_v3_l1_codex_finalization"
    / "joint_v2_v3"
    / "manuscript_review4_3_supplement_finalization"
    / "final_author_package",
    "crabnet_v4_reserved": WORKSPACE / "transportability_study_v4_crabnet_l1_l4_confirmatory",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(row: dict[str, str]) -> dict[str, object]:
    path = ROOTS[row["protected_root"]] / Path(row["relative_path"])
    exists = path.is_file()
    size_match = exists and path.stat().st_size == int(row["size_bytes"])
    hash_match = size_match and sha256(path) == row["sha256"]
    return {
        "protected_root": row["protected_root"],
        "relative_path": row["relative_path"],
        "exists": exists,
        "size_match": size_match,
        "sha256_match": hash_match,
    }


def main() -> None:
    baseline = REVISION / "audits_v4" / "baseline_protected_file_hashes.csv"
    with baseline.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, rows))
    mismatches = [row for row in results if not row["sha256_match"]]
    summary = {
        "baseline_entries": len(rows),
        "exact_matches": len(rows) - len(mismatches),
        "mismatches": len(mismatches),
        "protected_baseline_unchanged": not mismatches,
    }
    (REVISION / "audits_v4" / "protected_baseline_reverification.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    with (REVISION / "audits_v4" / "protected_baseline_mismatches.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(mismatches)
    print(json.dumps(summary))
    raise SystemExit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
