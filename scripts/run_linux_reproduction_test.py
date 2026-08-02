"""Run an isolated Linux reproduction from only the curated candidate tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--python-runtime", type=Path, required=True)
    args = parser.parse_args()
    candidate = args.candidate.resolve()
    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="materials_linux_external_"))
    release = temporary / "release candidate spaces UTF8"
    outputs = temporary / "outputs spaces UTF8"
    shutil.copytree(candidate, release)
    python = temporary / "venv/bin/python"
    started = datetime.now(timezone.utc)
    records: list[dict[str, object]] = []
    passed = True
    try:
        subprocess.run([str(args.python_runtime), "-m", "venv", str(temporary / "venv")], check=True)
        commands = [
            [str(python), "-m", "pip", "install", "--no-cache-dir", "-r", "requirements-lock.txt"],
            [str(python), "-m", "pip", "install", "--no-cache-dir", "build==1.3.0"],
            [str(python), "-m", "build", "--outdir", str(outputs / "packages"), "."],
            [str(python), "-m", "pip", "install", "--no-cache-dir", "--no-deps", "--force-reinstall", str(outputs / "packages/materials_transportability_v6-1.0.0-py3-none-any.whl")],
            [str(python), "-c", "import importlib.metadata as m, transportability_v6, p1_extension; assert m.version('materials-transportability-v6') == '1.0.0'"],
            [str(python), "-m", "pip", "install", "--no-cache-dir", "--no-deps", "--force-reinstall", str(outputs / "packages/materials_transportability_v6-1.0.0.tar.gz")],
            [str(python), "-c", "import importlib.metadata as m, transportability_v6, p1_extension; assert m.version('materials-transportability-v6') == '1.0.0'"],
            [str(python), "-m", "pip", "check"],
            [str(python), "-m", "transportability_v6", "--help"],
            [str(python), "scripts/verify_release.py", "--json-output", str(outputs / "verify.json")],
            [str(python), "scripts/reproduce_smoke.py", "--output-dir", str(outputs / "smoke")],
            [str(python), "scripts/reproduce_tables.py", "--output-dir", str(outputs / "tables")],
            [str(python), "scripts/reproduce_figures.py", "--output-dir", str(outputs / "figures")],
            [str(python), "-m", "pytest", "tests", "v6_revision/tests", "-q"],
            [str(python), "scripts/verify_release.py", "--json-output", str(outputs / "verify_after.json")],
        ]
        for command in commands:
            tick = time.perf_counter()
            result = subprocess.run(command, cwd=release, capture_output=True, text=True, errors="replace")
            records.append({
                "command": ["<PYTHON>" if part == str(python) else part.replace(str(temporary), "<TEMP_ROOT>") for part in command],
                "returncode": result.returncode,
                "elapsed_seconds": round(time.perf_counter() - tick, 3),
                "stdout_tail": result.stdout[-3000:].replace(str(temporary), "<TEMP_ROOT>"),
                "stderr_tail": result.stderr[-3000:].replace(str(temporary), "<TEMP_ROOT>"),
            })
            if result.returncode:
                passed = False
                break
        pdfs = release / "manuscript"
        pdf_hashes = {path.name: digest(path) for path in pdfs.glob("*P1_COMPLETE*.pdf")}
        payload = {
            "status": "PASS" if passed else "FAIL",
            "platform": "Ubuntu 26.04 under local WSL2",
            "python": subprocess.check_output([str(python), "--version"], text=True).strip(),
            "source": "copied dist/release_candidate only",
            "network": "package installation only; no scientific data retrieval",
            "latex_compilation": "NOT TESTED: TeX toolchain absent in WSL; bundled PDFs hash-verified only",
            "started_utc": started.isoformat(),
            "ended_utc": datetime.now(timezone.utc).isoformat(),
            "commands": records,
            "bundled_pdf_hashes": pdf_hashes,
            "used_parent_repository_files": False,
        }
        json_path = report_dir / "linux_reproduction_status.json"
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# Local Linux reproduction test", "", f"Overall status: **{payload['status']}**", "",
            "This is a local WSL2 validation, not an online CI result. A managed Python 3.12 runtime and fresh venv were used. Only a copied release-candidate tree was executed.", "",
            "TeX compilation was not tested because the WSL image has no TeX toolchain; the three bundled PDFs were hash-inventoried.", "",
            "| Step | Return code | Seconds |", "|---|---:|---:|",
        ]
        lines.extend(f"| `{' '.join(item['command'])}` | {item['returncode']} | {item['elapsed_seconds']} |" for item in records)
        (report_dir / "LINUX_REPRODUCTION_TEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(json.dumps({"status": payload["status"], "steps": len(records)}))
        if not passed:
            raise SystemExit(1)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    main()
