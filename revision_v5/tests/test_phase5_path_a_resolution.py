import hashlib
import json
from pathlib import Path


PKG = Path(r"D:\贝叶斯优化\最终\_code_package")
ORIGINAL = "db8a62e658f6efd17b48430a8a61b578cfa1d40c16b82817bc57d9681678698b"
LF = "9cc5a55ca76b2999bda44537ab0df48ac3e24c6046c249b5bd813ab3830a40a1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_historical_phase5_object_matches_unchanged_manifest():
    manifest = json.loads(
        (PKG / "reports/corrected_v5/phase5_frozen_manifest.json").read_text()
    )
    entry = next(
        row for row in manifest["report_sha256"]
        if row["path"] == "reports/corrected_v5/phase5_full_benchmark.md"
    )
    target = PKG / entry["path"]
    assert entry["sha256"] == ORIGINAL
    assert entry["bytes"] == 4188
    assert digest(target) == ORIGINAL


def test_lf_documentation_copy_is_preserved_separately():
    amended = (
        PKG
        / "reports/corrected_v5/amendments/phase5_full_benchmark_amended_lf.md"
    )
    assert amended.stat().st_size == 4142
    assert digest(amended) == LF


def test_path_a_objects_differ_only_by_line_endings():
    historical = (
        PKG / "reports/corrected_v5/phase5_full_benchmark.md"
    ).read_bytes()
    amended = (
        PKG
        / "reports/corrected_v5/amendments/phase5_full_benchmark_amended_lf.md"
    ).read_bytes()
    assert historical.replace(b"\r\n", b"\n") == amended
