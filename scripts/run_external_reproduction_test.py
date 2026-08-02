"""Simulate a new Windows researcher using only the curated release candidate."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "dist/release_candidate"
REPORT_JSON = ROOT / "reports/external_reproduction_status.json"
REPORT_MD = ROOT / "reports/EXTERNAL_REPRODUCTION_TEST.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: str, temporary: Path) -> str:
    result = value.replace(str(temporary), "<TEMP_ROOT>")
    result = result.replace(str(Path.home()), "<USER_HOME>")
    return result[-3000:]


def main() -> None:
    if not CANDIDATE.is_dir():
        raise RuntimeError("build dist/release_candidate first")
    temp_root = Path(tempfile.mkdtemp(prefix="materials_release_external_"))
    release = temp_root / "release candidate 空格"
    outputs = temp_root / "outputs 空格"
    shutil.copytree(CANDIDATE, release)
    records = []
    started = datetime.now(timezone.utc)
    try:
        subprocess.run(["py", "-3.12", "-m", "venv", str(temp_root / "venv")], check=True, capture_output=True, text=True)
        python = temp_root / "venv/Scripts/python.exe"
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
            [str(python), "scripts/reproduce_smoke.py", "--output-dir", str(outputs / "smoke 复现")],
            [str(python), "scripts/reproduce_tables.py", "--output-dir", str(outputs / "tables 复现")],
            [str(python), "scripts/reproduce_figures.py", "--output-dir", str(outputs / "figures 复现")],
            [str(python), "scripts/reproduce_manuscript.py", "--output-dir", str(outputs / "manuscript 复现")],
            [str(python), "-m", "pytest", "tests", "v6_revision/tests", "-q"],
            [str(python), "scripts/verify_release.py", "--json-output", str(outputs / "verify_after.json")],
        ]
        passed = True
        for command in commands:
            step_started = time.perf_counter()
            result = subprocess.run(command, cwd=release, capture_output=True, text=True, encoding="utf-8", errors="replace")
            records.append({
                "command": ["<PYTHON>" if item == str(python) else sanitize(item, temp_root) for item in command],
                "returncode": result.returncode,
                "elapsed_seconds": round(time.perf_counter() - step_started, 3),
                "stdout_tail": sanitize(result.stdout, temp_root),
                "stderr_tail": sanitize(result.stderr, temp_root),
            })
            if result.returncode:
                passed = False
                break
        artifacts = {}
        if outputs.exists():
            for path in outputs.rglob("*"):
                if path.is_file() and path.stat().st_size < 20 * 1024**2:
                    artifacts[path.relative_to(outputs).as_posix()] = sha(path)
        payload = {
            "status": "PASS" if passed else "FAIL",
            "platform": "Windows",
            "python": "3.12 fresh venv via py launcher",
            "source": "copied dist/release_candidate only",
            "network": "package installation only; no scientific data retrieval",
            "started_utc": started.isoformat(),
            "ended_utc": datetime.now(timezone.utc).isoformat(),
            "commands": records,
            "artifact_hashes_under_20MiB": artifacts,
            "used_existing_venv": False,
            "used_parent_repository_files": False,
        }
        REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# External reproduction test", "", f"Overall status: **{payload['status']}**", "",
            "A fresh Python 3.12 virtual environment was created outside the repository. Only a copied `dist/release_candidate` tree was used; pip cache was disabled. No local Matbench data or parent-repository file was read.", "",
            "| Step | Return code | Seconds |", "|---|---:|---:|",
        ]
        lines.extend(f"| `{' '.join(item['command'])}` | {item['returncode']} | {item['elapsed_seconds']} |" for item in records)
        lines += ["", "Full sanitized stdout/stderr tails and output hashes are in `reports/external_reproduction_status.json`.", ""]
        REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
        print(json.dumps({"status": payload["status"], "steps": len(records)}, indent=2))
        if not passed:
            raise SystemExit(1)
    finally:
        resolved = temp_root.resolve()
        if resolved.parent == Path(tempfile.gettempdir()).resolve() and resolved.name.startswith("materials_release_external_"):
            shutil.rmtree(resolved, ignore_errors=True)


if __name__ == "__main__":
    main()
