"""Run a small synthetic, explicitly non-scientific smoke campaign."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from release_common import assert_authorities, repository_root


def main() -> None:
    parser = argparse.ArgumentParser(description="Tiny synthetic smoke test; expected <2 min and <100 MiB.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = repository_root(Path(__file__).resolve().parent)
    sys.path.insert(0, str(root / "src"))
    assert_authorities(root)
    output = args.output_dir.resolve()
    result = output / "smoke_result_manifest.json"
    print("Expected: <2 minutes, CPU only, <100 MiB; no confirmatory job is run.")
    if args.verify_only:
        if not result.is_file():
            raise RuntimeError(f"smoke result missing: {result}")
        payload = json.loads(result.read_text(encoding="utf-8"))
        from transportability_v6.smoke_only import SMOKE_LABEL
        if payload.get("failed") or payload.get("validation_label") != SMOKE_LABEL:
            raise RuntimeError("invalid smoke result")
        print("smoke output verified")
        return
    from transportability_v6.cli import run_smoke
    from transportability_v6.smoke_only import SMOKE_LABEL
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1, "validation_label": SMOKE_LABEL,
        "output_root": str(output),
        "jobs": [{
            "job_id": "synthetic_release_smoke", "task": "synthetic_fixture", "dataset_kind": "synthetic",
            "sample_count": 80, "data_seed": 901, "campaign_seed": 902, "initial_count": 16,
            "batch_size": 2, "max_queries": 8, "n_estimators": 16,
            "strategies": ["RAW", "GG_CALIBRATION_ONLY", "GG_NORMALIZED_ACQUISITION", "CS_CALIBRATION_ONLY"],
        }],
    }
    manifest_path = output / "smoke_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    run_smoke(manifest_path)
    assert_authorities(root)


if __name__ == "__main__":
    main()
