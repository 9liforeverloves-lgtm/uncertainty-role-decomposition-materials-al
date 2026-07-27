from __future__ import annotations

import importlib.metadata
from pathlib import Path


EXCLUDE = {"materials-transportability-v6"}
ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    rows = sorted(
        {
            f"{distribution.metadata['Name']}=={distribution.version}"
            for distribution in importlib.metadata.distributions()
            if distribution.metadata.get("Name")
            and distribution.metadata["Name"].lower() not in EXCLUDE
        },
        key=str.lower,
    )
    (ROOT / "requirements-lock.txt").write_text(
        "# Generated from the clean Stage-2.5 production-validation environment.\n"
        "# Python 3.12; canonical V5 adapter dependencies included.\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
