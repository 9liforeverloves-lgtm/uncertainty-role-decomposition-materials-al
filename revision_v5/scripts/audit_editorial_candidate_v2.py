#!/usr/bin/env python3
"""Audit and export editorial submission candidate v2 without scientific recomputation."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MAN = ROOT / "manuscript_v5" / "submission_candidate_v2"
FIG = ROOT / "figures_v5" / "submission_candidate_v2"
TAB = ROOT / "tables_v5" / "submission_candidate_v2"
ED = ROOT / "editorial_revision_v2"
EXPORT = ROOT / "EXPORT_SUBMISSION_CANDIDATE_V2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(
        timespec="seconds"
    )


checks: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str) -> None:
    checks.append((name, bool(condition), detail))
    if not condition:
        raise AssertionError(f"{name}: {detail}")


for directory in (MAN, FIG, TAB, ED):
    check(f"directory exists: {directory.relative_to(ROOT)}", directory.is_dir(), "")

main_tex = MAN / "manuscript_submission_candidate_v2.tex"
supp_tex = MAN / "supplement_submission_candidate_v2.tex"
main_pdf = MAN / "manuscript_submission_candidate_v2.pdf"
supp_pdf = MAN / "supplement_submission_candidate_v2.pdf"
for path in (main_tex, supp_tex, main_pdf, supp_pdf):
    check(f"file exists: {path.name}", path.is_file(), str(path))

main_source = main_tex.read_text(encoding="utf-8")
supp_source = supp_tex.read_text(encoding="utf-8")
main_figure_count = main_source.count(r"\begin{figure}")
supp_figure_count = supp_source.count(r"\begin{figure}")
check(
    "exactly four main figure environments",
    main_figure_count == 4,
    f"found {main_figure_count}",
)
check(
    "exactly five supplementary figure environments",
    supp_figure_count == 5,
    f"found {supp_figure_count}",
)
for label in ("S1", "S2", "S3", "S4", "S5"):
    check(
        f"Supplementary Figure {label} source",
        f"Supplementary Figure {label}." in supp_source,
        "",
    )

required_source = {
    "full CS algorithms and parameter table": (
        "Historical CS algorithm",
        "Development-selected parsimonious CS algorithm",
        "candidate_specific_parameters.tex",
    ),
    "36-configuration development inventory": (
        "Complete 36-configuration development inventory",
        "development_inventory_36.tex",
    ),
    "development selection by fold": (
        "Development selection by fold",
        "development_selection_by_fold.tex",
    ),
    "chemical-system OOD disclosure": (
        "Chemical-system OOD definition and split table",
        "Target values were not used in assignment",
        "160",
    ),
    "raw and BH p values": (
        r"$p_{\rm raw}$",
        r"$p_{\rm BH}$",
        "complete_primary_128_p_raw_p_BH.tex",
    ),
}
for name, tokens in required_source.items():
    check(name, all(token in supp_source for token in tokens), ", ".join(tokens))

inventory = pd.read_csv(TAB / "development_configuration_inventory_36.csv")
selection = pd.read_csv(TAB / "development_selection_by_fold.csv")
ood = pd.read_csv(TAB / "chemical_system_ood_split_summary.csv")
primary = pd.read_csv(TAB / "complete_primary_128_with_p_raw_p_BH.csv")
check("36 unique development configurations", len(inventory) == 36, str(len(inventory)))
check("12 fold-by-family selections", len(selection) == 12, str(len(selection)))
check("four OOD task summaries", len(ood) == 4, str(len(ood)))
check(
    "OOD overlap is zero",
    (ood["maximum_group_overlap"].eq(0) & ood["maximum_candidate_id_overlap"].eq(0)).all(),
    "",
)
check("complete primary table has 128 rows", len(primary) == 128, str(len(primary)))
check(
    "p_raw and p_BH complete",
    {"p_raw", "p_BH"}.issubset(primary.columns)
    and primary[["p_raw", "p_BH"]].notna().all().all(),
    "",
)

bib = (MAN / "references_submission_candidate_v2.bib").read_text(encoding="utf-8")
reference_count = len(re.findall(r"(?m)^@", bib))
bbl_count = len(
    re.findall(
        r"(?m)^\\bibitem",
        (MAN / "manuscript_submission_candidate_v2.bbl").read_text(encoding="utf-8"),
    )
)
check("47 verified references in bibliography", reference_count == 47, str(reference_count))
check("47 references compiled into PDF", bbl_count == 47, str(bbl_count))

pdftotext = shutil.which("pdftotext")
check("pdftotext available", pdftotext is not None, str(pdftotext))
main_text_path = ED / "main_pdf_visible_text_v2.txt"
supp_text_path = ED / "supplement_pdf_visible_text_v2.txt"
subprocess.run([pdftotext, "-layout", str(main_pdf), str(main_text_path)], check=True)
subprocess.run([pdftotext, "-layout", str(supp_pdf), str(supp_text_path)], check=True)
main_text = main_text_path.read_text(encoding="utf-8", errors="replace")
supp_text = supp_text_path.read_text(encoding="utf-8", errors="replace")
for token in ("Figure 1:", "Figure 2:", "Figure 3:", "Figure 4:"):
    check(f"main PDF visibly contains {token}", token in main_text, "")
check("main PDF has no Figure 5", "Figure 5:" not in main_text, "")
for token in (
    "Full candidate-specific algorithms and parameter table",
    "Complete 36-configuration development inventory",
    "Development selection by fold",
    "Chemical-system OOD definition and split table",
    "praw",
    "pBH",
    "Supplementary Figure S1.",
    "Supplementary Figure S2.",
    "Supplementary Figure S3.",
    "Supplementary Figure S4.",
    "Supplementary Figure S5.",
):
    check(f"supplement PDF visibly contains: {token}", token in supp_text, "")

for log in (
    MAN / "manuscript_submission_candidate_v2.log",
    MAN / "supplement_submission_candidate_v2.log",
):
    text = log.read_text(encoding="utf-8", errors="replace")
    bad = [
        line
        for line in text.splitlines()
        if line.startswith("LaTeX Warning") or "Overfull \\hbox" in line
    ]
    check(f"clean LaTeX layout log: {log.name}", not bad, " | ".join(bad))

old_main = ROOT / "manuscript_v5" / "manuscript_acquisition_transportability_v5_final.pdf"
old_supp = ROOT / "manuscript_v5" / "supplement_acquisition_transportability_v5_final.pdf"
for old, new in ((old_main, main_pdf), (old_supp, supp_pdf)):
    check(f"old artifact exists: {old.name}", old.is_file(), "")
    check(
        f"old artifact predates candidate: {old.name}",
        old.stat().st_mtime < new.stat().st_mtime,
        f"{iso_mtime(old)} vs {iso_mtime(new)}",
    )
    check(
        f"old artifact differs by SHA-256: {old.name}",
        sha256(old) != sha256(new),
        "",
    )

test_report = ED / "editorial_test_report_v2.md"
test_lines = [
    "# Editorial test report v2",
    "",
    "No scientific computation was rerun. This audit validates frozen-source editorial outputs.",
    "",
    f"- Passed: {len(checks)}",
    "- Failed: 0",
    "",
    "## Checks",
    "",
]
test_lines.extend(f"- PASS — {name}" + (f": {detail}" if detail else "") for name, _, detail in checks)
test_report.write_text("\n".join(test_lines) + "\n", encoding="utf-8")

readiness = ED / "editorial_submission_readiness_v2.md"
readiness_lines = [
    "# Editorial submission readiness v2",
    "",
    "Status: READY after editorial-only reconstruction from frozen evidence.",
    "",
    "## Requested directories",
    "",
    f"- `{MAN.relative_to(ROOT)}/`: exists",
    f"- `{FIG.relative_to(ROOT)}/`: exists",
    f"- `{TAB.relative_to(ROOT)}/`: exists",
    f"- `{ED.relative_to(ROOT)}/`: exists",
    "",
    "## Verified content",
    "",
    "- Main manuscript: exactly four numbered main figures.",
    "- Supplement: full Historical CS and selected parsimonious CS algorithms plus parameter table.",
    "- Supplement: complete 36-configuration development inventory.",
    "- Supplement: development selection by held-out-task fold.",
    "- Supplement: chemical-system OOD definition, split sizes, and 160/160 disjointness audit.",
    "- Supplement: complete 128-row primary table with `p_raw` and `p_BH`.",
    "- Supplement: Supplementary Figures S1–S5.",
    f"- Verified compiled reference count: {reference_count}.",
    "",
    "## Old `*_v5_final.pdf` comparison",
    "",
]
for old, new in ((old_main, main_pdf), (old_supp, supp_pdf)):
    readiness_lines += [
        f"- `{old.name}`: {iso_mtime(old)}, SHA-256 `{sha256(old)}`.",
        f"  Candidate `{new.name}`: {iso_mtime(new)}, SHA-256 `{sha256(new)}`.",
        "  Result: the old final is older and hash-distinct; it is not the requested candidate.",
    ]
readiness.write_text("\n".join(readiness_lines) + "\n", encoding="utf-8")

inventory_path = ED / "artifact_inventory_v2.csv"
inventory_targets = []
for directory in (MAN, FIG, TAB):
    inventory_targets.extend(path for path in directory.rglob("*") if path.is_file())
inventory_targets.extend([readiness, test_report, main_text_path, supp_text_path])
with inventory_path.open("w", newline="", encoding="utf-8-sig") as handle:
    writer = csv.DictWriter(
        handle, fieldnames=("relative_path", "bytes", "modified", "sha256")
    )
    writer.writeheader()
    for path in sorted(set(inventory_targets)):
        writer.writerow(
            {
                "relative_path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "modified": iso_mtime(path),
                "sha256": sha256(path),
            }
        )

if EXPORT.exists():
    raise FileExistsError(
        f"Refusing to silently overwrite existing export directory: {EXPORT}"
    )
EXPORT.mkdir(parents=True)
exports = {
    main_pdf: EXPORT / "manuscript_submission_candidate_v2.pdf",
    supp_pdf: EXPORT / "supplement_submission_candidate_v2.pdf",
    readiness: EXPORT / "editorial_submission_readiness_v2.md",
    test_report: EXPORT / "editorial_test_report_v2.md",
}
for source, destination in exports.items():
    shutil.copy2(source, destination)

result = {
    "status": "READY",
    "checks_passed": len(checks),
    "references": reference_count,
    "main_figures": 4,
    "supplementary_figures": 5,
    "export_files": {
        path.name: {"modified": iso_mtime(path), "sha256": sha256(path)}
        for path in exports.values()
    },
    "inventory": str(inventory_path),
}
(ED / "editorial_audit_result_v2.json").write_text(
    json.dumps(result, indent=2), encoding="utf-8"
)
print(json.dumps(result, indent=2))
