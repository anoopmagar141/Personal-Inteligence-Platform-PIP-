"""pytest plugin: swap evidence_gate._topic_raising_text for the candidate named by TOPIC_IMPL."""
import importlib.util, os


def pytest_configure(config):
    path = os.environ.get("TOPIC_IMPL")
    if not path:
        return
    spec = importlib.util.spec_from_file_location("topic_impl", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from backend.core import evidence_gate
    evidence_gate._topic_raising_text = mod.topic_raising_text
