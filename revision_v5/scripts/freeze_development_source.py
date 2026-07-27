from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INCLUDE = [
    ROOT / "03_frozen_v4_protocol.md",
    ROOT / "pyproject.toml",
    ROOT / "manifests_v4" / "DEVELOPMENT_JOB_MANIFEST_V5.csv",
    ROOT / "manifests_v4" / "DEVELOPMENT_SPEC_LOCK_V5.json",
    ROOT / "manifests_v4" / "DEVELOPMENT_SPEC_AMENDMENT_001.md",
]
for folder in ("experiments_v4/src", "scripts", "tests"):
    INCLUDE.extend(
        path
        for path in (ROOT / folder).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


records = [
    {
        "relative_path": path.relative_to(ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }
    for path in sorted(set(INCLUDE))
]
payload = {
    "status": "DEVELOPMENT_SOURCE_FROZEN",
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "scope": "Development only; does not release the V5-RC1 confirmation manifest.",
    "file_count": len(records),
    "files": records,
}
output = ROOT / "manifests_v4" / "DEVELOPMENT_SOURCE_FREEZE_V5.json"
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"output": str(output), "file_count": len(records), "sha256": sha256(output)}))
