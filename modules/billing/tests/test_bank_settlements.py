# Re-export all integration tests for the bank-settlements router.
# The hook-visible test file -- actual tests live in integration/test_bank_settlements_router.py.
from modules.billing.tests.integration.test_bank_settlements_router import *  # noqa: F401, F403
