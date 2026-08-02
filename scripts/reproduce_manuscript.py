"""Compile and copy the three current manuscript PDFs to a selected directory."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

from release_common import assert_authorities, repository_root


PDFS = ["manuscript_submission_P1_COMPLETE.pdf", "manuscript_submission_P1_COMPLETE_twocolumn.pdf", "supplement_submission_P1_COMPLETE.pdf"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Manuscript rebuild; expected 1–5 min, TeX Live/Poppler required.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = repository_root(Path(__file__).resolve().parent)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    assert_authorities(root)
    print("Expected: 1–5 minutes and <1 GiB; requires pdflatex, bibtex and pdffonts.")
    if not args.verify_only:
        subprocess.run([sys.executable, str(root / "scripts/compile_p1_complete_manuscript.py")], cwd=root, check=True)
        for name in PDFS:
            shutil.copy2(root / "manuscript" / name, output / name)
    for name in PDFS:
        path = output / name
        if not path.is_file() or len(PdfReader(path).pages) < 1:
            raise RuntimeError(f"invalid PDF: {path}")
    assert_authorities(root)
    print("verified three manuscript PDFs")


if __name__ == "__main__":
    main()

