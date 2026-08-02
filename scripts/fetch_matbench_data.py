"""Retrieve official Matbench objects and rebuild composition-only snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import requests
import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "data_manifest/upstream_sources.yaml"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, expected: str) -> None:
    if destination.exists():
        if sha(destination) != expected:
            raise RuntimeError(f"existing file checksum mismatch: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        if sha(temporary) != expected:
            raise RuntimeError(f"download checksum mismatch for {url}")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def prepare(task: str, source: Path, output: Path, config: dict[str, object]) -> None:
    frame = pd.read_json(source, orient="split", compression="gzip", precise_float=True)
    if len(frame) != int(config["upstream_entries"]):
        raise RuntimeError(f"{task}: expected {config['upstream_entries']} rows, found {len(frame)}")
    input_column = str(config["input_column"])
    if input_column == "composition":
        formulas = frame[input_column].astype(str)
    else:
        try:
            from pymatgen.core import Structure
        except ImportError as exc:
            raise RuntimeError("pymatgen is required to convert structure tasks; install requirements-lock.txt") from exc
        formulas = frame[input_column].map(lambda value: Structure.from_dict(value).composition.reduced_formula)
    prepared = pd.DataFrame({
        "material_id": [f"MB-{index:06d}" for index in range(1, len(frame) + 1)],
        "formula": formulas,
        "target": frame[str(config["target_column"])].astype(float),
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    # The frozen local snapshots use CRLF independent of host; fixing the
    # terminator preserves byte-level hashes on Linux and Windows.
    prepared.to_csv(output, index=False, lineterminator="\r\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch checksum-verified Matbench data; users must accept applicable upstream terms.")
    parser.add_argument("--task", action="append", choices=["matbench_expt_gap", "matbench_mp_gap", "matbench_log_gvrh", "matbench_log_kvrh"])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["tasks"]
    tasks = args.task or list(config)
    for task in tasks:
        item = config[task]
        raw = args.output_dir.resolve() / "raw" / f"{task}.json.gz"
        prepared = args.output_dir.resolve() / "prepared" / task / "materials.csv"
        if args.verify_only:
            if not raw.exists() or sha(raw) != item["sha256"]:
                raise RuntimeError(f"missing or invalid upstream object: {raw}")
            print(f"verified {task}: {raw}")
            continue
        print(f"{task}: downloading official object; expected storage varies by task")
        download(item["url"], raw, item["sha256"])
        prepare(task, raw, prepared, item)
        print(json.dumps({"task": task, "raw_sha256": sha(raw), "prepared": str(prepared), "rows": item["upstream_entries"]}))


if __name__ == "__main__":
    main()
