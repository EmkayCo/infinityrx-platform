"""Session 4 — AS2/SFTP transport and clearinghouse adapter tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.transport.as2 import (
    AS2DispositionType,
    AS2MDN,
    AS2Message,
    build_as2_message,
    build_mdn,
    compute_mic,
    parse_mdn,
)
from src.transport.sftp import (
    SftpConfig,
    SftpTransferDirection,
    SftpTransferStatus,
    build_sftp_filename,
    simulate_sftp_transfer,
    validate_sftp_config,
)
from src.services.clearinghouse import (
    ClearinghouseProvider,
    SubmissionStatus,
    build_submission_result,
    parse_availity_response,
    parse_change_healthcare_response,
    parse_stedi_response,
    parse_waystar_response,
    route_clearinghouse_response,
)

_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# AS2 tests
# ---------------------------------------------------------------------------

class TestBuildAS2Message:
    def test_basic_message_fields(self):
        payload = b"ISA*00*..."
        msg = build_as2_message("SENDER", "PAYER001", payload)
        assert msg.from_id == "SENDER"
        assert msg.to_id == "PAYER001"
        assert msg.payload_bytes == payload
        assert msg.signed is True
        assert msg.encrypted is True
        assert msg.request_mdn is True

    def test_message_id_format(self):
        msg = build_as2_message("A", "B", b"data")
        assert msg.message_id.startswith("<")
        assert "@infinityrx>" in msg.message_id

    def test_headers_include_as2_version(self):
        msg = build_as2_message("A", "B", b"data")
        assert msg.headers["AS2-Version"] == "1.2"
        assert msg.headers["AS2-From"] == "A"
        assert msg.headers["AS2-To"] == "B"

    def test_mdn_headers_added_when_requested(self):
        msg = build_as2_message("A", "B", b"data", request_mdn=True, mdn_url="https://example.com/mdn")
        assert "Disposition-Notification-To" in msg.headers
        assert msg.headers["Disposition-Notification-To"] == "https://example.com/mdn"

    def test_mdn_headers_use_default_url_when_none(self):
        msg = build_as2_message("A", "B", b"data", request_mdn=True, mdn_url=None)
        assert "as2.infinityrx.com/mdn" in msg.headers["Disposition-Notification-To"]

    def test_no_mdn_headers_when_not_requested(self):
        msg = build_as2_message("A", "B", b"data", request_mdn=False)
        assert "Disposition-Notification-To" not in msg.headers

    def test_custom_subject(self):
        msg = build_as2_message("A", "B", b"data", subject="Custom Subject")
        assert msg.subject == "Custom Subject"
        assert msg.headers["Subject"] == "Custom Subject"

    def test_unsigned_unencrypted(self):
        msg = build_as2_message("A", "B", b"data", signed=False, encrypted=False)
        assert msg.signed is False
        assert msg.encrypted is False


class TestComputeMIC:
    def test_sha256_mic_is_base64(self):
        import base64
        mic = compute_mic(b"hello world")
        decoded = base64.b64decode(mic)
        assert len(decoded) == 32   # SHA-256 = 32 bytes

    def test_sha1_mic_is_base64(self):
        import base64
        mic = compute_mic(b"hello world", algorithm="sha-1")
        decoded = base64.b64decode(mic)
        assert len(decoded) == 20   # SHA-1 = 20 bytes

    def test_sha256_alias(self):
        mic1 = compute_mic(b"data", algorithm="sha-256")
        mic2 = compute_mic(b"data", algorithm="sha256")
        assert mic1 == mic2

    def test_unknown_algorithm_defaults_to_sha256(self):
        import base64
        mic = compute_mic(b"data", algorithm="md5-unknown")
        decoded = base64.b64decode(mic)
        assert len(decoded) == 32

    def test_deterministic(self):
        assert compute_mic(b"test") == compute_mic(b"test")

    def test_different_payloads_differ(self):
        assert compute_mic(b"aaa") != compute_mic(b"bbb")


class TestBuildMDN:
    def _make_msg(self) -> AS2Message:
        return build_as2_message("SENDER", "PAYER", b"payload data")

    def test_success_mdn_is_processed(self):
        msg = self._make_msg()
        mdn = build_mdn(msg, success=True)
        assert mdn.disposition_type == AS2DispositionType.PROCESSED
        assert mdn.disposition_modifier == ""

    def test_success_mdn_from_to_swapped(self):
        msg = self._make_msg()
        mdn = build_mdn(msg, success=True)
        assert mdn.from_id == msg.to_id
        assert mdn.to_id == msg.from_id

    def test_success_mdn_has_mic(self):
        msg = self._make_msg()
        mdn = build_mdn(msg, success=True)
        assert len(mdn.mic) > 0
        assert mdn.mic_algorithm == "sha-256"

    def test_failure_mdn_is_failed(self):
        msg = self._make_msg()
        mdn = build_mdn(msg, success=False)
        assert mdn.disposition_type == AS2DispositionType.FAILED

    def test_failure_mdn_decryption_modifier(self):
        msg = self._make_msg()
        mdn = build_mdn(msg, success=False, error_description="")
        assert mdn.disposition_modifier == "decryption-failed"

    def test_failure_mdn_processing_error_modifier(self):
        msg = self._make_msg()
        mdn = build_mdn(msg, success=False, error_description="segment error")
        assert mdn.disposition_modifier == "processing-error"
        assert mdn.error_description == "segment error"

    def test_mdn_original_message_id_set(self):
        msg = self._make_msg()
        mdn = build_mdn(msg)
        assert mdn.original_message_id == msg.message_id

    def test_empty_payload_mic_is_empty(self):
        msg = build_as2_message("A", "B", b"")
        mdn = build_mdn(msg, success=True)
        assert mdn.mic == ""


class TestParseMDN:
    def _mdn_body(self, disposition: str, mic: str = "abc123, sha-256") -> str:
        return f"Disposition: {disposition}\nReceived-Content-MIC: {mic}\n"

    def test_processed_disposition(self):
        headers = {"AS2-From": "PAYER", "AS2-To": "SENDER", "Original-Message-ID": "<abc>", "Date": "Thu, 01 Jan 2026 12:00:00 +0000"}
        mdn = parse_mdn(headers, self._mdn_body("automatic-action/MDN-sent-automatically; processed"))
        assert mdn.disposition_type == AS2DispositionType.PROCESSED

    def test_failed_disposition(self):
        headers = {"AS2-From": "PAYER", "AS2-To": "SENDER", "Original-Message-ID": "<abc>", "Date": ""}
        mdn = parse_mdn(headers, self._mdn_body("automatic-action/MDN-sent-automatically; failed/decryption-failed"))
        assert mdn.disposition_type == AS2DispositionType.FAILED

    def test_error_disposition_fallback(self):
        headers = {"AS2-From": "A", "AS2-To": "B", "Original-Message-ID": "", "Date": ""}
        mdn = parse_mdn(headers, "Disposition: automatic-action; unknown-state\n")
        assert mdn.disposition_type == AS2DispositionType.ERROR

    def test_mic_parsed(self):
        headers = {"AS2-From": "A", "AS2-To": "B", "Original-Message-ID": "", "Date": ""}
        mdn = parse_mdn(headers, self._mdn_body("processed", "BASE64VALUE, sha-256"))
        assert mdn.mic == "BASE64VALUE"
        assert mdn.mic_algorithm == "sha-256"

    def test_mic_single_part_no_algorithm(self):
        headers = {"AS2-From": "A", "AS2-To": "B", "Original-Message-ID": "", "Date": ""}
        mdn = parse_mdn(headers, "Received-Content-MIC: ONLYMIC\n")
        assert mdn.mic == "ONLYMIC"

    def test_modifier_extracted_from_slash(self):
        headers = {"AS2-From": "A", "AS2-To": "B", "Original-Message-ID": "", "Date": ""}
        mdn = parse_mdn(headers, "Disposition: automatic-action; failed/my-modifier\n")
        assert mdn.disposition_modifier == "my-modifier"

    def test_from_to_ids_from_headers(self):
        headers = {"AS2-From": "PAYER001", "AS2-To": "MYRX", "Original-Message-ID": "<id1>", "Date": "date-val"}
        mdn = parse_mdn(headers, "Disposition: processed\n")
        assert mdn.from_id == "PAYER001"
        assert mdn.to_id == "MYRX"
        assert mdn.original_message_id == "<id1>"

    def test_message_id_fallback(self):
        headers = {"AS2-From": "A", "AS2-To": "B", "Message-ID": "<fallback>"}
        mdn = parse_mdn(headers, "")
        assert mdn.original_message_id == "<fallback>"


# ---------------------------------------------------------------------------
# SFTP tests
# ---------------------------------------------------------------------------

class TestBuildSftpFilename:
    def test_basic_format(self):
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        fn = build_sftp_filename("837P", "SENDER01", 42, now=now)
        assert fn == "837P_SENDER01_000000042_20260101120000.edi"

    def test_control_number_zero_padded_9(self):
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        fn = build_sftp_filename("835", "RX", 1, now=now)
        assert "000000001" in fn

    def test_spaces_in_sender_replaced(self):
        now = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        fn = build_sftp_filename("270", "SENDER ID", 1, now=now)
        assert " " not in fn
        assert "SENDER_ID" in fn

    def test_default_now_produces_filename(self):
        fn = build_sftp_filename("278", "NPI1234", 999)
        assert fn.endswith(".edi")
        assert "278_NPI1234_000000999_" in fn


class TestSimulateSftpTransfer:
    def test_success_status(self):
        cfg = SftpConfig(host="sftp.example.com", username="user", password="pass")
        record = simulate_sftp_transfer(cfg, SftpTransferDirection.OUTBOUND, "file.edi", b"data", "TP001")
        assert record.status == SftpTransferStatus.SUCCESS

    def test_byte_count_correct(self):
        cfg = SftpConfig(host="sftp.example.com", username="user", password="pass")
        payload = b"hello world"
        record = simulate_sftp_transfer(cfg, SftpTransferDirection.INBOUND, "in.edi", payload, "TP002")
        assert record.byte_count == len(payload)

    def test_transfer_id_is_uuid(self):
        cfg = SftpConfig(host="sftp.example.com", username="user", password="pass")
        record = simulate_sftp_transfer(cfg, SftpTransferDirection.OUTBOUND, "out.edi", b"x", "TP003")
        uuid.UUID(record.transfer_id)   # raises if not valid UUID

    def test_trading_partner_id_preserved(self):
        cfg = SftpConfig(host="h", username="u", password="p")
        record = simulate_sftp_transfer(cfg, SftpTransferDirection.OUTBOUND, "f.edi", b"", "PARTNER99")
        assert record.trading_partner_id == "PARTNER99"

    def test_direction_preserved(self):
        cfg = SftpConfig(host="h", username="u", password="p")
        record = simulate_sftp_transfer(cfg, SftpTransferDirection.INBOUND, "f.edi", b"", "TP")
        assert record.direction == SftpTransferDirection.INBOUND


class TestValidateSftpConfig:
    def test_valid_config_key(self, tmp_path):
        key_file = tmp_path / "key.pem"
        key_file.write_text("KEY")
        cfg = SftpConfig(host="sftp.example.com", username="user", key_path=str(key_file))
        errors = validate_sftp_config(cfg)
        assert errors == []

    def test_valid_config_password(self):
        cfg = SftpConfig(host="sftp.example.com", username="user", password="secret")
        errors = validate_sftp_config(cfg)
        assert errors == []

    def test_missing_host(self):
        cfg = SftpConfig(host="", username="user", password="p")
        errors = validate_sftp_config(cfg)
        assert any("host" in e for e in errors)

    def test_missing_username(self):
        cfg = SftpConfig(host="h", username="", password="p")
        errors = validate_sftp_config(cfg)
        assert any("username" in e for e in errors)

    def test_missing_auth(self):
        cfg = SftpConfig(host="h", username="u")
        errors = validate_sftp_config(cfg)
        assert any("key_path" in e or "password" in e for e in errors)

    def test_invalid_port_low(self):
        cfg = SftpConfig(host="h", username="u", password="p", port=0)
        errors = validate_sftp_config(cfg)
        assert any("port" in e for e in errors)

    def test_invalid_port_high(self):
        cfg = SftpConfig(host="h", username="u", password="p", port=99999)
        errors = validate_sftp_config(cfg)
        assert any("port" in e for e in errors)

    def test_key_path_nonexistent(self):
        cfg = SftpConfig(host="h", username="u", key_path="/nonexistent/path/key.pem")
        errors = validate_sftp_config(cfg)
        assert any("key_path" in e for e in errors)


# ---------------------------------------------------------------------------
# Clearinghouse tests
# ---------------------------------------------------------------------------

class TestBuildSubmissionResult:
    def test_basic_result(self):
        r = build_submission_result("SUB001", SubmissionStatus.ACCEPTED, control_number="CN123")
        assert r.submission_id == "SUB001"
        assert r.status == SubmissionStatus.ACCEPTED
        assert r.clearinghouse_control_number == "CN123"
        assert r.acknowledgment_type == "999"

    def test_errors_default_empty(self):
        r = build_submission_result("SUB002", SubmissionStatus.PENDING)
        assert r.error_messages == []

    def test_errors_passed_through(self):
        r = build_submission_result("SUB003", SubmissionStatus.REJECTED, errors=["ERR1", "ERR2"])
        assert r.error_messages == ["ERR1", "ERR2"]

    def test_timestamp_set(self):
        r = build_submission_result("SUB004", SubmissionStatus.ACCEPTED)
        assert len(r.timestamp) > 0


class TestParseStediResponse:
    def test_accepted(self):
        r = parse_stedi_response({"status": "accepted", "controlNumber": "CN1", "submissionId": "S1"})
        assert r.status == SubmissionStatus.ACCEPTED
        assert r.submission_id == "S1"
        assert r.clearinghouse_control_number == "CN1"

    def test_rejected(self):
        r = parse_stedi_response({"status": "rejected", "errors": ["BAD_SEG"]})
        assert r.status == SubmissionStatus.REJECTED
        assert "BAD_SEG" in r.error_messages

    def test_unknown_status_is_pending(self):
        r = parse_stedi_response({"status": "processing"})
        assert r.status == SubmissionStatus.PENDING

    def test_missing_submission_id_generates_uuid(self):
        r = parse_stedi_response({})
        uuid.UUID(r.submission_id)

    def test_errors_not_list_coerced(self):
        r = parse_stedi_response({"errors": "single error"})
        assert r.error_messages == ["single error"]

    def test_empty_errors_string(self):
        r = parse_stedi_response({"errors": ""})
        assert r.error_messages == []

    def test_timestamp_is_set(self):
        r = parse_stedi_response({"status": "accepted"})
        assert r.timestamp != ""


class TestParseAvailityResponse:
    def test_accepted(self):
        r = parse_availity_response({"transactionStatus": "ACCEPTED", "transactionId": "T1"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_processed_maps_to_accepted(self):
        r = parse_availity_response({"transactionStatus": "PROCESSED"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_rejected(self):
        r = parse_availity_response({"transactionStatus": "REJECTED"})
        assert r.status == SubmissionStatus.REJECTED

    def test_denied_maps_to_rejected(self):
        r = parse_availity_response({"transactionStatus": "DENIED"})
        assert r.status == SubmissionStatus.REJECTED

    def test_acknowledged(self):
        r = parse_availity_response({"transactionStatus": "ACKNOWLEDGED"})
        assert r.status == SubmissionStatus.ACKNOWLEDGED

    def test_unknown_is_pending(self):
        r = parse_availity_response({"transactionStatus": "IN_PROGRESS"})
        assert r.status == SubmissionStatus.PENDING

    def test_error_messages_dict(self):
        r = parse_availity_response({"errorMessages": [{"message": "Invalid NPI"}]})
        assert "Invalid NPI" in r.error_messages

    def test_error_messages_plain(self):
        r = parse_availity_response({"errorMessages": ["plain error"]})
        assert "plain error" in r.error_messages

    def test_ack_type_from_response(self):
        r = parse_availity_response({"ackType": "TA1"})
        assert r.acknowledgment_type == "TA1"

    def test_missing_transaction_id_generates_uuid(self):
        r = parse_availity_response({})
        uuid.UUID(r.submission_id)


class TestParseChangeHealthcareResponse:
    def test_accepted(self):
        r = parse_change_healthcare_response({"editStatus": "accepted", "submissionId": "S1"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_forwarded_maps_to_accepted(self):
        r = parse_change_healthcare_response({"editStatus": "forwarded"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_rejected(self):
        r = parse_change_healthcare_response({"editStatus": "rejected"})
        assert r.status == SubmissionStatus.REJECTED

    def test_denied_maps_to_rejected(self):
        r = parse_change_healthcare_response({"editStatus": "denied"})
        assert r.status == SubmissionStatus.REJECTED

    def test_unknown_is_pending(self):
        r = parse_change_healthcare_response({"editStatus": "queued"})
        assert r.status == SubmissionStatus.PENDING

    def test_claim_errors_extracted(self):
        r = parse_change_healthcare_response({
            "claimStatus": [{"errors": [{"message": "bad claim"}]}]
        })
        assert "bad claim" in r.error_messages

    def test_claim_errors_plain_string(self):
        r = parse_change_healthcare_response({
            "claimStatus": [{"errors": ["raw error"]}]
        })
        assert "raw error" in r.error_messages

    def test_missing_submission_id_generates_uuid(self):
        r = parse_change_healthcare_response({})
        uuid.UUID(r.submission_id)


class TestParseWaystarResponse:
    def test_accepted_full(self):
        r = parse_waystar_response({"statusCode": "ACCEPTED", "transactionId": "W1"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_accepted_short_code(self):
        r = parse_waystar_response({"statusCode": "A"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_rejected_full(self):
        r = parse_waystar_response({"statusCode": "REJECTED"})
        assert r.status == SubmissionStatus.REJECTED

    def test_rejected_short_code(self):
        r = parse_waystar_response({"statusCode": "R"})
        assert r.status == SubmissionStatus.REJECTED

    def test_acknowledged(self):
        r = parse_waystar_response({"statusCode": "ACKNOWLEDGED"})
        assert r.status == SubmissionStatus.ACKNOWLEDGED

    def test_unknown_is_pending(self):
        r = parse_waystar_response({"statusCode": "PROCESSING"})
        assert r.status == SubmissionStatus.PENDING

    def test_errors_extracted(self):
        r = parse_waystar_response({"errors": ["err1", "err2"]})
        assert r.error_messages == ["err1", "err2"]

    def test_control_number_from_controlNum(self):
        r = parse_waystar_response({"controlNum": "WCN999"})
        assert r.clearinghouse_control_number == "WCN999"

    def test_missing_transaction_id_generates_uuid(self):
        r = parse_waystar_response({})
        uuid.UUID(r.submission_id)


class TestRouteClearinghouseResponse:
    def test_routes_stedi(self):
        r = route_clearinghouse_response(ClearinghouseProvider.STEDI, {"status": "accepted"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_routes_availity(self):
        r = route_clearinghouse_response(ClearinghouseProvider.AVAILITY, {"transactionStatus": "REJECTED"})
        assert r.status == SubmissionStatus.REJECTED

    def test_routes_change_healthcare(self):
        r = route_clearinghouse_response(ClearinghouseProvider.CHANGE_HEALTHCARE, {"editStatus": "forwarded"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_routes_waystar(self):
        r = route_clearinghouse_response(ClearinghouseProvider.WAYSTAR, {"statusCode": "A"})
        assert r.status == SubmissionStatus.ACCEPTED

    def test_routes_generic_as_stedi(self):
        r = route_clearinghouse_response(ClearinghouseProvider.GENERIC, {"status": "accepted"})
        assert r.status == SubmissionStatus.ACCEPTED
