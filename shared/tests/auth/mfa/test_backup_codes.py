"""Tests for shared.auth.mfa.backup_codes."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from unittest.mock import MagicMock


from shared.auth.mfa.backup_codes import (
    generate_backup_codes,
    hash_code,
    verify_and_consume,
)


# ---------------------------------------------------------------------------
# generate_backup_codes
# ---------------------------------------------------------------------------

_CODE_RE = re.compile(r"^[0-9A-F]{5}-[0-9A-F]{5}$")


def test_generate_default_count() -> None:
    codes = generate_backup_codes()
    assert len(codes) == 10


def test_generate_custom_count() -> None:
    codes = generate_backup_codes(n=5)
    assert len(codes) == 5


def test_generate_format() -> None:
    for code in generate_backup_codes():
        assert _CODE_RE.match(code), f"Bad format: {code}"


def test_generate_unique() -> None:
    codes = generate_backup_codes(n=20)
    assert len(set(codes)) == 20


# ---------------------------------------------------------------------------
# hash_code
# ---------------------------------------------------------------------------


def test_hash_code_returns_sha256_hex() -> None:
    code = "ABCDE-12345"
    expected = hashlib.sha256(code.encode()).hexdigest()
    assert hash_code(code) == expected


def test_hash_code_deterministic() -> None:
    code = "00000-FFFFF"
    assert hash_code(code) == hash_code(code)


def test_hash_code_different_inputs() -> None:
    assert hash_code("AAAAA-BBBBB") != hash_code("BBBBB-AAAAA")


# ---------------------------------------------------------------------------
# verify_and_consume — helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeUser:
    id: str = "user-1"
    tenant_id: str = "tenant-1"
    mfa_backup_codes_encrypted: str | None = None


class _FakeSession:
    """Captures commit calls."""

    def __init__(self) -> None:
        self.committed = 0

    def commit(self) -> None:
        self.committed += 1


def _make_user_with_codes(codes: list[str]) -> _FakeUser:
    hashes = [hash_code(c) for c in codes]
    return _FakeUser(mfa_backup_codes_encrypted=json.dumps(hashes))


# ---------------------------------------------------------------------------
# verify_and_consume — success
# ---------------------------------------------------------------------------


def test_verify_valid_code_returns_true() -> None:
    codes = generate_backup_codes(n=3)
    user = _make_user_with_codes(codes)
    session = _FakeSession()
    assert verify_and_consume(user, codes[1], session) is True


def test_verify_removes_used_code() -> None:
    codes = generate_backup_codes(n=3)
    user = _make_user_with_codes(codes)
    session = _FakeSession()
    verify_and_consume(user, codes[0], session)
    remaining = json.loads(user.mfa_backup_codes_encrypted)  # type: ignore[arg-type]
    assert len(remaining) == 2
    assert hash_code(codes[0]) not in remaining


def test_verify_commits_session() -> None:
    codes = generate_backup_codes(n=1)
    user = _make_user_with_codes(codes)
    session = _FakeSession()
    verify_and_consume(user, codes[0], session)
    assert session.committed == 1


def test_verify_single_use_enforcement() -> None:
    codes = generate_backup_codes(n=2)
    user = _make_user_with_codes(codes)
    session = _FakeSession()
    assert verify_and_consume(user, codes[0], session) is True
    assert verify_and_consume(user, codes[0], session) is False


# ---------------------------------------------------------------------------
# verify_and_consume — failure
# ---------------------------------------------------------------------------


def test_verify_invalid_code_returns_false() -> None:
    codes = generate_backup_codes(n=3)
    user = _make_user_with_codes(codes)
    session = _FakeSession()
    assert verify_and_consume(user, "ZZZZZ-ZZZZZ", session) is False


def test_verify_no_codes_stored_returns_false() -> None:
    user = _FakeUser(mfa_backup_codes_encrypted=None)
    session = _FakeSession()
    assert verify_and_consume(user, "AAAAA-BBBBB", session) is False


def test_verify_empty_list_returns_false() -> None:
    user = _FakeUser(mfa_backup_codes_encrypted=json.dumps([]))
    session = _FakeSession()
    assert verify_and_consume(user, "AAAAA-BBBBB", session) is False


def test_verify_does_not_commit_on_failure() -> None:
    codes = generate_backup_codes(n=2)
    user = _make_user_with_codes(codes)
    session = _FakeSession()
    verify_and_consume(user, "WRONG-CODE0", session)
    assert session.committed == 0


# ---------------------------------------------------------------------------
# verify_and_consume — audit sink
# ---------------------------------------------------------------------------


def test_audit_emit_on_success() -> None:
    codes = generate_backup_codes(n=1)
    user = _make_user_with_codes(codes)
    user.id = "u1"
    user.tenant_id = "t1"
    session = _FakeSession()
    audit = MagicMock()
    verify_and_consume(user, codes[0], session, audit=audit)
    audit.emit_backup_code_used.assert_called_once_with("u1", "t1")
    audit.emit_backup_code_invalid.assert_not_called()


def test_audit_emit_on_failure() -> None:
    codes = generate_backup_codes(n=1)
    user = _make_user_with_codes(codes)
    user.id = "u1"
    user.tenant_id = "t1"
    session = _FakeSession()
    audit = MagicMock()
    verify_and_consume(user, "WRONG-CODE0", session, audit=audit)
    audit.emit_backup_code_invalid.assert_called_once_with("u1", "t1")
    audit.emit_backup_code_used.assert_not_called()


def test_audit_none_does_not_raise() -> None:
    codes = generate_backup_codes(n=1)
    user = _make_user_with_codes(codes)
    session = _FakeSession()
    # Should not raise when audit is None (default)
    verify_and_consume(user, codes[0], session, audit=None)
    verify_and_consume(user, "WRONG-CODE0", session, audit=None)
