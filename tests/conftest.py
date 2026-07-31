import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# test_provenance.py imports `schemas` bare (not `dhammapada_rag.generate.schemas`),
# so the module's own directory has to be on the path, not just src/.
sys.path.insert(0, str(ROOT / "src" / "dhammapada_rag" / "generate"))
sys.path.insert(0, str(ROOT / "src"))
