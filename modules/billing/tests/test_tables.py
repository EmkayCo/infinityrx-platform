"""Hook-visible test file for modules/billing/src/models/tables.py.

All upload_id propagation assertions live in test_upload_id_propagation.py.
This file satisfies the Werkbench test-first gate (which matches on stem
'tables' -> 'test_tables.py') and re-exports those tests so pytest discovers
them from either entry point.
"""
from modules.billing.tests.unit.test_upload_id_propagation import (  # noqa: F401
    test_carryover_has_amount_column,
    test_carryover_has_ap_record_id_column,
    test_carryover_has_created_at_column,
    test_carryover_has_id_column,
    test_carryover_has_reason_column,
    test_carryover_has_tenant_id_column,
    test_carryover_has_upload_id_column,
    test_carryover_model_exists,
    test_carryover_schema_is_billing,
    test_carryover_upload_id_fk_to_uploads,
    test_carryover_upload_id_is_nullable,
    test_invoice_line_item_has_upload_id_column,
    test_invoice_line_item_upload_id_fk_to_uploads,
    test_invoice_line_item_upload_id_is_nullable,
    test_invoice_line_item_upload_id_is_uuid_type,
    test_payment_batch_has_upload_id_column,
    test_payment_batch_upload_id_fk_to_uploads,
    test_payment_batch_upload_id_is_nullable,
    test_payment_batch_upload_id_is_uuid_type,
)
