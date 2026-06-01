# Tests for reference_rules.py (ALL-002, ALL-003) live in test_all002_all003.py.
# This file exists to satisfy the Werkbench test-first naming convention.
# See tests/detection/test_all002_all003.py for the full test suite.
from tests.detection.test_all002_all003 import (  # noqa: F401
    TestNPIValidation,
    TestALL002DataQualityCounter,
    TestALL002PhantomFires,
    test_all003_returns_dict_with_required_keys,
    test_fdb_cache_built_once_and_mfr003_receives_it,
)
