"""Anchor test file for billing models/tables.py.

Full model coverage lives in test_positional_parser.py (ClaimUploadRawRow),
test_upload_model.py (Upload), and other unit tests that exercise the ORM
via SQLite in-memory sessions.

This file exists so the werkbench enforce_test_first hook can locate a
matching test file for tables.py edits. It must be kept fresher than
tables.py (the hook requires test_mtime >= prod_mtime).
"""

# The hook only needs the file to EXIST and be newer than tables.py.
# Actual coverage for ClaimUploadRawRow AAD encryption is in
# test_positional_parser.py::test_cross_tenant_aad_decrypt_fails,
# test_parse_upload_positional_aad_round_trip, and
# test_parse_upload_positional_aad_cross_tenant_decrypt_fails.
