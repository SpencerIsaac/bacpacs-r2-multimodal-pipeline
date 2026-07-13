import importlib.util
from pathlib import Path


def test_docs_freshness():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_docs_freshness.py"
    spec = importlib.util.spec_from_file_location("check_docs_freshness", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.main() == 0
