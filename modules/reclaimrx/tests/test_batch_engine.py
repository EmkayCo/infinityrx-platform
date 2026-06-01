# Proxy import so the Werkbench test-first hook can find a test at the expected
# one-level-deep path (<module>/tests/test_batch_engine.py); its candidate-path
# generator does not descend into tests/<subdir>/. The real batch_engine tests live
# in tests/detection/ — the broad run_detection suite in test_detection_passes.py and
# the dialect-guard regression in test_batch_engine.py.
from tests.detection.test_batch_engine import (  # noqa: F401
    test_run_detection_completes_on_sqlite_with_all002_all003_applicable,
)
