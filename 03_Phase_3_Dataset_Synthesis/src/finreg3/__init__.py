import sys
from pathlib import Path

PHASE2_SRC = Path(__file__).resolve().parent.parent.parent.parent / "Phase 2" / "src"
if PHASE2_SRC.exists() and str(PHASE2_SRC) not in sys.path:
    sys.path.insert(0, str(PHASE2_SRC))

__version__ = "0.3.0"

