from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import re
import subprocess
from collections import Counter
from pathlib import Path


WORKSPACE = Path(r"C:\Users\ROG\Desktop\贝叶斯优化")
REVISION = WORKSPACE / "revision_v5"
V2 = WORKSPACE / "最终" / "_code_package" / "transportability_study"
V3 = WORKSPACE / "transportability_study_v3_l1_l4_exploratory"
REVIEW43 = (
    WORKSPACE
    / "transportability_study_v3_l1_codex_finalization"
    / "joint_v2_v3"
    / "manuscript_review4_3_supplement_finalization"
    / "final_author_package"
)
CRABNET_V4 = WORKSPACE / "transportability_study_v4_crabnet_l1_l4_confirmatory"

PROTECTED_ROOTS = {
    "v2_study": V2,
    "v3_exploratory": V3,
    "review4_3_author_package": REVIEW43,
    "crabnet_v4_reserved": CRABNET_V4,
}

SKIP_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mplconfig",
    ".venv",
    ".venv_corrected_v1",
    "cache",
    "build",
    "render",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path):
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".pytest_tmp"))
        base = Path(current)
        for name in sorted(files):
            yield base / name


def compact_tree(root: Path, depth: int = 2) -> list[str]:
    output = [f"{root.name}/"]
    root_parts = len(root.parts)
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".pytest_tmp"))
        current_path = Path(current)
        level = len(current_path.parts) - root_parts
        if level >= depth:
            dirs[:] = []
            continue
        prefix = "  " * (level + 1)
        for directory in dirs:
            output.append(f"{prefix}{directory}/")
        for file_name in sorted(files):
            output.append(f"{prefix}{file_name}")
    return output


def verify_json_hash_manifest(root: Path, manifest: Path) -> tuple[int, list[dict]]:
    expected = json.loads(manifest.read_text(encoding="utf-8"))
    rows = []
    for rel, expected_hash in expected.items():
        path = root / rel
        actual = sha256(path) if path.is_file() else ""
        rows.append(
            {
                "manifest": str(manifest),
                "relative_path": rel,
                "exists": path.is_file(),
                "expected_sha256": expected_hash,
                "actual_sha256": actual,
                "match": bool(actual and actual.lower() == expected_hash.lower()),
            }
        )
    return sum(row["match"] for row in rows), rows


def seed_evidence() -> tuple[dict[int, list[str]], list[str]]:
    seed_res = (
        re.compile(r"(?i)\bseed(?:s)?\b[^0-9\r\n]{0,12}([1-9]\d{3,4})\b"),
        re.compile(r"(?i)\bseed([1-9]\d{3,4})\b"),
    )
    evidence: dict[int, list[str]] = {}
    for root in (V2, V3, CRABNET_V4):
        for path in iter_files(root):
            if path.suffix.lower() not in {".csv", ".json", ".yaml", ".yml", ".md", ".py", ".txt"}:
                continue
            if path.stat().st_size > 15_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for seed_re in seed_res:
                for match in seed_re.finditer(text):
                    seed = int(match.group(1))
                    if 1000 <= seed <= 99999:
                        evidence.setdefault(seed, [])
                        if len(evidence[seed]) < 4:
                            evidence[seed].append(str(path.relative_to(WORKSPACE)))
    unused_5000 = [str(seed) for seed in range(5000, 5040) if seed not in evidence]
    return evidence, unused_5000


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows or [{"status": "NO_ROWS"}])


def main() -> None:
    REVISION.mkdir(parents=True, exist_ok=True)
    all_hash_rows: list[dict] = []
    counts = {}
    sizes = {}
    ext_counts = {}
    for label, root in PROTECTED_ROOTS.items():
        files = list(iter_files(root))
        counts[label] = len(files)
        sizes[label] = sum(path.stat().st_size for path in files)
        ext_counts[label] = Counter(path.suffix.lower() or "[none]" for path in files).most_common(12)
        for path in files:
            all_hash_rows.append(
                {
                    "protected_root": label,
                    "relative_path": path.relative_to(root).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    write_csv(REVISION / "audits_v4" / "baseline_protected_file_hashes.csv", all_hash_rows)

    review_match_count, review_rows = verify_json_hash_manifest(
        REVIEW43, REVIEW43 / "REVIEW4_3_PACKAGE_HASHES.json"
    )
    write_csv(REVISION / "audits_v4" / "review4_3_hash_verification.csv", review_rows)

    seed_map, unused_5000 = seed_evidence()
    seed_rows = [
        {"seed": seed, "evidence_count_capped": len(paths), "evidence_paths": " | ".join(paths)}
        for seed, paths in sorted(seed_map.items())
        if 1000 <= seed <= 5039
    ]
    write_csv(REVISION / "audits_v4" / "seed_namespace_audit.csv", seed_rows)

    tree = []
    for label, root in PROTECTED_ROOTS.items():
        tree.append(f"### {label}: `{root}`")
        tree.append("")
        tree.append("```text")
        tree.extend(compact_tree(root))
        tree.append("```")
        tree.append("")

    status = subprocess.run(
        [
            r"C:\Users\ROG\Desktop\贝叶斯优化\最终\_code_package\.venv_corrected_v1\Scripts\pytest.exe",
            "--version",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    inventory = f"""# Repository inventory for revision V5

Generated by `revision_v5/scripts/phase0_inventory.py`.

## Scope and immutable boundaries

The revision is isolated at `{REVISION}`. The following historical roots are read-only scientific evidence and were hashed into `audits_v4/baseline_protected_file_hashes.csv`:

- V2 study: `{V2}`
- frozen post hoc V3 L1-L4 package: `{V3}`
- Review 4.3 author package: `{REVIEW43}`
- separate CrabNet V4 proposal: `{CRABNET_V4}`

The CrabNet V4 proposal reserves formal seeds 4000-4019. No revision experiment may reuse those identifiers. The complete candidate range 5000-5039 was {"unused in the scanned study metadata" if len(unused_5000) == 40 else "not fully unused"}; exact unused count: {len(unused_5000)}/40.

## Inventory summary

| Root | Files hashed | Size (GiB) | Common extensions |
|---|---:|---:|---|
{os.linesep.join(f"| {label} | {counts[label]} | {sizes[label] / 2**30:.3f} | " + ", ".join(f"{ext}:{n}" for ext, n in ext_counts[label]) + " |" for label in PROTECTED_ROOTS)}

## Main entry points and assets

- V2 package metadata: `pyproject.toml`; runtime: `src/transportability/runner.py`.
- V2 strategy implementation: `src/transportability/strategies.py`.
- V2 split implementation: `src/transportability/splits.py`.
- V2 statistical analysis: `scripts/run_analysis_v2.py`.
- V2 freeze: `outputs/frozen_protocol_v2/FREEZE_LOCK_V2.json`.
- V2 raw-result lock: `outputs/confirmation_v2/frozen_results/RESULTS_LOCK.md`.
- V3 final gate: `finalization/gate/V3_LAYERED_FINAL_GATE.json`.
- Review 4.3 manuscript and Supplement sources and PDFs are present in the author package.
- Environment: Python 3.12 virtual environment at `_code_package/.venv_corrected_v1`; `{status.stdout.strip()}`.
- No usable Git metadata exists at the workspace root; the `.git` directory is empty. The only detected real Git worktree is the separate `material-active-learning` repository and is not the authoritative V2/V3 study root. A hash baseline is therefore used.

## Hash verification

Review 4.3 package manifest: {review_match_count}/{len(review_rows)} entries match exactly. Any mismatch is listed in `audits_v4/review4_3_hash_verification.csv`.

## Known missing or limited assets

- The historical Phase 1 `src/material_al/models.py` snapshot with the manifest-declared hash was not recovered in the prior provenance amendment; this remains a disclosed provenance limitation.
- V2 does not contain the diagnostic residual/target fields needed to retroactively estimate frozen V2 L1, CRPS, NLL, interval width, or standardized-residual endpoints.
- The V3 same-cohort L2-L4 reconstruction is post hoc exploratory and cannot become confirmatory by inclusion in this revision.
- The Review 4.3 manuscript still contains `AUTHOR_TODO` fields; author identity, affiliations, funding, conflicts, and email cannot be fabricated.

## Reproducibility and compute

The historical V2 confirmation completed 1,920/1,920 jobs with zero failed jobs. Its progress record reports 29,665.375 seconds, four workers, approximately 231.54 jobs/hour, and 43.86 GB of output. A seven-strategy, 40-seed, 16-environment revision cohort contains 4,480 trajectories. A direct historical-rate projection is approximately 19.35 wall-clock hours with four workers and approximately 102.3 GB if output density is unchanged. The code must remain checkpointed and resumable.

## Directory tree

{os.linesep.join(tree)}
"""
    (REVISION / "00_repository_inventory.md").write_text(inventory, encoding="utf-8")

    summary = {
        "protected_file_count": len(all_hash_rows),
        "review4_3_hash_matches": review_match_count,
        "review4_3_hash_entries": len(review_rows),
        "candidate_confirmation_seeds": list(range(5000, 5040)),
        "candidate_confirmation_seed_unused_count": len(unused_5000),
        "platform": platform.platform(),
    }
    (REVISION / "audits_v4" / "phase0_inventory_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
