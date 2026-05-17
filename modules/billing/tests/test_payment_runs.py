# Re-export all integration tests for the payment-runs router.
# The hook-visible test file -- actual tests live in integration/test_payment_runs_router.py.
from modules.billing.tests.integration.test_payment_runs_router import *  # noqa: F401, F403
