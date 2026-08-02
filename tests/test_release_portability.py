from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def test_release_common_discovers_root_from_nonroot_directory(tmp_path: Path) -> None:
    script = (
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); "
        "from release_common import repository_root; "
        f"assert repository_root(Path({str(tmp_path)!r})) == Path({str(ROOT)!r})"
    )
    # Discovery falls back to the installed script location when invoked from
    # an unrelated working directory.
    subprocess.run([sys.executable, "-c", script], cwd=tmp_path, check=True)


def test_tiny_fixture_is_explicitly_synthetic() -> None:
    fixture = pd.read_csv(ROOT / "tests/fixtures/tiny_materials.csv")
    assert len(fixture) == 10
    assert fixture.material_id.str.startswith("SYN-").all()


def test_release_entry_scripts_contain_no_user_absolute_path() -> None:
    windows_user_prefix = "C:" + "\\" + "Users" + "\\"
    posix_home_prefix = "/" + "home" + "/"
    for name in ["verify_release.py", "reproduce_smoke.py", "reproduce_tables.py", "reproduce_figures.py", "reproduce_manuscript.py", "fetch_matbench_data.py"]:
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert windows_user_prefix not in text
        assert posix_home_prefix not in text


def test_authority_hashes_remain_bound() -> None:
    import json
    lock = json.loads((ROOT / "locks/p1_confirmation_inference_result_lock.json").read_text(encoding="utf-8"))
    for group in ("v6_files_verified_unchanged", "files"):
        for relative, expected in lock[group].items():
            assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
