from __future__ import annotations

import csv
import json
import re
from pathlib import Path


WORKSPACE = Path(r"C:\Users\ROG\Desktop\贝叶斯优化")
REVISION = WORKSPACE / "revision_v5"
ROOTS = [
    WORKSPACE / "最终" / "_code_package" / "transportability_study",
    WORKSPACE / "最终" / "_code_package" / "transportability_study_v3_l1",
    WORKSPACE / "transportability_study_v3_l1_l4_exploratory",
    WORKSPACE / "transportability_study_v4_crabnet_l1_l4_confirmatory",
]
PATTERNS = (
    re.compile(r"(?i)\bseed(?:s)?\b[^0-9\r\n]{0,12}([1-9]\d{3,4})\b"),
    re.compile(r"(?i)\bseed([1-9]\d{3,4})\b"),
)


def main() -> None:
    rows = []
    used = set()
    for root in ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".csv",
                ".json",
                ".yaml",
                ".yml",
                ".md",
                ".py",
                ".txt",
            }:
                continue
            if any(part.startswith(".pytest_tmp") or part.startswith(".venv") for part in path.parts):
                continue
            if path.stat().st_size > 15_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in PATTERNS:
                for match in pattern.finditer(text):
                    seed = int(match.group(1))
                    if 1000 <= seed <= 99999:
                        used.add(seed)
                        rows.append(
                            {
                                "seed": seed,
                                "root": root.name,
                                "relative_path": path.relative_to(root).as_posix(),
                                "matched_text": match.group(0)[:80],
                            }
                        )
    output = REVISION / "audits_v4" / "seed_namespace_audit.csv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["seed", "root", "relative_path", "matched_text"])
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (row["seed"], row["root"], row["relative_path"])))
    candidate = list(range(5000, 5040))
    summary = {
        "historical_expected_ranges": {
            "v2_development": [1000, 1009],
            "v2_confirmation": [2000, 2019],
            "v3_confirmation": [3000, 3039],
            "crabnet_v4_reserved_not_run": [4000, 4019],
        },
        "revision_candidate_range": [5000, 5039],
        "candidate_used": sorted(set(candidate) & used),
        "candidate_unused": sorted(set(candidate) - used),
        "candidate_range_is_disjoint": not bool(set(candidate) & used),
        "parsing_rule": "Only numbers explicitly adjacent to a seed/seed(s) label or embedded as seedNNNN in an identifier are counted.",
        "superseded_false_positive": "The first broad numeric scan was invalid because it counted metric values, hashes, and bootstrap counts as seeds.",
    }
    (REVISION / "audits_v4" / "seed_namespace_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
