"""Compile the P1-complete main, two-column, and supplement PDFs cleanly."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript"
AUDIT = ROOT / "revision_audit/p1_complete"
BIB = MANUSCRIPT / "references_submission_candidate_v4_final_r1.bib"
TARGETS = {"main": ("manuscript_submission_P1_COMPLETE", True), "twocolumn": ("manuscript_submission_P1_COMPLETE_twocolumn", True), "supplement": ("supplement_submission_P1_COMPLETE", False)}


def run(command: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="p1_complete_compile_", dir=ROOT) as temporary:
        for name, (stem, bibliography) in TARGETS.items():
            build = Path(temporary) / name
            build.mkdir()
            if bibliography:
                shutil.copy2(BIB, build / BIB.name)
            command = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", f"-output-directory={build}", f"{stem}.tex"]
            logs: list[str] = []
            code, output = run(command, MANUSCRIPT); logs.append(output)
            if code == 0 and bibliography:
                code, output = run(["bibtex", stem], build); logs.append(output)
            if code == 0:
                for _ in range(3):
                    code, output = run(command, MANUSCRIPT); logs.append(output)
                    if code:
                        break
            (AUDIT / f"compile_{name}.log").write_text("\n\n".join(logs), encoding="utf-8")
            (AUDIT / f"compile_{name}_final.log").write_text(logs[-1], encoding="utf-8")
            if code:
                raise RuntimeError(f"{name} compilation failed; inspect {AUDIT / f'compile_{name}.log'}")
            target = MANUSCRIPT / f"{stem}.pdf"
            shutil.copy2(build / f"{stem}.pdf", target)
            summary[name] = target.relative_to(ROOT).as_posix()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
