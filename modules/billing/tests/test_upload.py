"""Hook-visible test file for modules/billing/src/services/upload.py.

Stage 1: positional parser additions.
Full test suite lives in tests/unit/test_positional_parser.py — imported
here so the Werkbench test-first gate finds a matching test for upload.py.
"""

# Re-export fixture-free parser tests. DB-fixture tests (requiring 'db' session)
# are NOT re-exported here because they depend on the module-scoped engine fixture
# defined in test_positional_parser.py -- pytest cannot satisfy 'db' across files.
# DB tests run directly from tests/unit/test_positional_parser.py.
from modules.billing.tests.unit.test_positional_parser import (  # noqa: F401
    test_detect_format_pipe_headerless,
    test_detect_format_csv_with_header,
    test_detect_format_pipe_detected_over_csv,
    test_detect_format_txt_extension_with_pipe_content,
    test_parse_positional_bytes_captures_all_fields,
    test_parse_positional_bytes_variable_field_count,
    test_parse_positional_bytes_preserves_trailing_empties,
    test_parse_positional_bytes_skips_blank_lines,
    test_parse_positional_bytes_real_sample,
    test_parse_upload_positional_ciphertext_not_plaintext,
)

# Sentinel: this file covers src/services/upload.py additions in Stage 1.
# Stage 1 parser functions: detect_format, parse_positional_bytes.
# UploadParseResult updated with raw_rows_written field (0 for CSV path).
# parse_upload routes to positional path when detect_format returns "positional".
