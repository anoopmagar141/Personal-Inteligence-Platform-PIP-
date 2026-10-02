# Probe harness: reuse the suite's own isolation so no probe can reach data/.
from backend.tests.conftest import isolated_data_dir, db_key  # noqa: F401
