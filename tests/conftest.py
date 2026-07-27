from __future__ import annotations

import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
V5_SRC = WORKSPACE / "revision_v5" / "experiments_v4" / "src"
if str(V5_SRC) not in sys.path:
    sys.path.insert(0, str(V5_SRC))
