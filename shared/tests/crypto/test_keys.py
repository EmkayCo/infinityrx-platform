"""Tests for shared.crypto.keys — key provider implementations."""

import base64
import json
import os
import secrets
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from shared.crypto.keys import (
    EnvKeyProvider,
    FileKeyProvider,
    KeyError as CryptoKeyError,
    get_key_provider,
)


def _make_key_b64(n_bytes: int = 32) -> str:
    return base64.b64encode(secrets.token_bytes(n_bytes)).decode()


KEY_V1 = _make_key_b64()
KEY_V0 = _make_key_b64()


# ---------------------------------------------------------------------------
# EnvKeyProvider — happy path
# ---------------------------------------------------------------------------


class TestEnvKeyProviderHappyPath:
    def test_get_active_key_returns_32_bytes(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            provider = EnvKeyProvider()
            key = provider.get_active_key()
            assert isinstance(key, bytes)
            assert len(key) == 32

    def test_active_key_id_reflects_env_var(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            provider = EnvKeyProvider()
            assert provider.active_key_id == "v1"

    def test_get_key_by_id_returns_matching_key(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            provider = EnvKeyProvider()
            key = provider.get_key("v1")
            assert key == base64.b64decode(KEY_V1)

    def test_default_active_key_id_is_v1(self):
        env = {"ENCRYPTION_KEY_ACTIVE": KEY_V1}
        with mock.patch.dict(os.environ, env, clear=False):
            # Remove ENCRYPTION_KEY_ACTIVE_ID if present
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("ENCRYPTION_KEY_ACTIVE_ID", None)
                provider = EnvKeyProvider()
                assert provider.active_key_id == "v1"


# ---------------------------------------------------------------------------
# EnvKeyProvider — rotation (old + new keys both accessible)
# ---------------------------------------------------------------------------


class TestEnvKeyProviderRotation:
    def test_old_key_accessible_by_id(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
                "ENCRYPTION_KEY_v0": KEY_V0,
            },
        ):
            provider = EnvKeyProvider()
            assert provider.get_key("v0") == base64.b64decode(KEY_V0)
            assert provider.get_key("v1") == base64.b64decode(KEY_V1)

    def test_active_key_id_changed_after_rotation(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
                "ENCRYPTION_KEY_v0": KEY_V0,
            },
        ):
            provider = EnvKeyProvider()
            assert provider.active_key_id == "v1"
            assert provider.get_active_key() == base64.b64decode(KEY_V1)


# ---------------------------------------------------------------------------
# EnvKeyProvider — error cases
# ---------------------------------------------------------------------------


class TestEnvKeyProviderErrors:
    def test_missing_active_key_raises(self):
        env = {}
        # Ensure env vars are not present
        with mock.patch.dict(os.environ, env):
            keys_to_remove = ["ENCRYPTION_KEY_ACTIVE", "ENCRYPTION_KEY_ACTIVE_ID"]
            for k in keys_to_remove:
                os.environ.pop(k, None)
            with pytest.raises(CryptoKeyError, match="ENCRYPTION_KEY_ACTIVE"):
                EnvKeyProvider()

    def test_wrong_size_key_raises(self):
        bad_key = base64.b64encode(secrets.token_bytes(16)).decode()  # 16 bytes, not 32
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": bad_key,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            with pytest.raises(CryptoKeyError, match="32 bytes"):
                EnvKeyProvider()

    def test_missing_key_by_id_raises(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            provider = EnvKeyProvider()
            with pytest.raises(CryptoKeyError, match="v99"):
                provider.get_key("v99")

    def test_old_key_wrong_size_raises(self):
        bad_key = base64.b64encode(secrets.token_bytes(10)).decode()
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
                "ENCRYPTION_KEY_v0": bad_key,
            },
        ):
            with pytest.raises(CryptoKeyError, match="32 bytes"):
                EnvKeyProvider()

    def test_invalid_base64_active_key_raises(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": "not!!!valid@base64###",
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            with pytest.raises(CryptoKeyError, match="[Bb]ase64|[Ii]nvalid"):
                EnvKeyProvider()


# ---------------------------------------------------------------------------
# FileKeyProvider — happy path
# ---------------------------------------------------------------------------


class TestFileKeyProviderHappyPath:
    def test_round_trip_keys_from_file(self, tmp_path: Path):
        key_file = tmp_path / "keys.json"
        data = {
            "active": "v1",
            "keys": {
                "v1": KEY_V1,
                "v0": KEY_V0,
            },
        }
        key_file.write_text(json.dumps(data))
        provider = FileKeyProvider(str(key_file))
        assert provider.active_key_id == "v1"
        assert provider.get_active_key() == base64.b64decode(KEY_V1)
        assert provider.get_key("v0") == base64.b64decode(KEY_V0)

    def test_pathlib_path_accepted(self, tmp_path: Path):
        key_file = tmp_path / "keys.json"
        data = {"active": "v1", "keys": {"v1": KEY_V1}}
        key_file.write_text(json.dumps(data))
        provider = FileKeyProvider(key_file)  # Path object
        assert provider.get_active_key() == base64.b64decode(KEY_V1)


# ---------------------------------------------------------------------------
# FileKeyProvider — error cases
# ---------------------------------------------------------------------------


class TestFileKeyProviderErrors:
    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(CryptoKeyError, match="not found"):
            FileKeyProvider(str(tmp_path / "nonexistent.json"))

    def test_malformed_json_raises(self, tmp_path: Path):
        key_file = tmp_path / "bad.json"
        key_file.write_text("not json {{{")
        with pytest.raises(CryptoKeyError, match="[Ii]nvalid|[Mm]alformed|[Pp]arse"):
            FileKeyProvider(str(key_file))

    def test_missing_active_field_raises(self, tmp_path: Path):
        key_file = tmp_path / "keys.json"
        data = {"keys": {"v1": KEY_V1}}
        key_file.write_text(json.dumps(data))
        with pytest.raises(CryptoKeyError, match="active"):
            FileKeyProvider(str(key_file))

    def test_active_key_not_in_keys_dict_raises(self, tmp_path: Path):
        key_file = tmp_path / "keys.json"
        data = {"active": "v2", "keys": {"v1": KEY_V1}}
        key_file.write_text(json.dumps(data))
        with pytest.raises(CryptoKeyError, match="v2"):
            FileKeyProvider(str(key_file))

    def test_wrong_size_key_raises(self, tmp_path: Path):
        bad_key = base64.b64encode(secrets.token_bytes(16)).decode()
        key_file = tmp_path / "keys.json"
        data = {"active": "v1", "keys": {"v1": bad_key}}
        key_file.write_text(json.dumps(data))
        with pytest.raises(CryptoKeyError, match="32 bytes"):
            FileKeyProvider(str(key_file))

    def test_missing_key_by_id_raises(self, tmp_path: Path):
        key_file = tmp_path / "keys.json"
        data = {"active": "v1", "keys": {"v1": KEY_V1}}
        key_file.write_text(json.dumps(data))
        provider = FileKeyProvider(str(key_file))
        with pytest.raises(CryptoKeyError, match="v99"):
            provider.get_key("v99")

    def test_missing_keys_dict_raises(self, tmp_path: Path):
        key_file = tmp_path / "keys.json"
        data = {"active": "v1"}  # no "keys" field
        key_file.write_text(json.dumps(data))
        with pytest.raises(CryptoKeyError, match="[Kk]eys"):
            FileKeyProvider(str(key_file))


# ---------------------------------------------------------------------------
# get_key_provider factory
# ---------------------------------------------------------------------------


class TestGetKeyProviderFactory:
    def test_env_provider_selected_by_default(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            os.environ.pop("ENCRYPTION_PROVIDER", None)
            provider = get_key_provider(_reset=True)
            assert isinstance(provider, EnvKeyProvider)

    def test_env_provider_selected_explicitly(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_PROVIDER": "env",
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            provider = get_key_provider(_reset=True)
            assert isinstance(provider, EnvKeyProvider)

    def test_file_provider_selected_by_env_var(self, tmp_path: Path):
        key_file = tmp_path / "keys.json"
        data = {"active": "v1", "keys": {"v1": KEY_V1}}
        key_file.write_text(json.dumps(data))
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_PROVIDER": "file",
                "ENCRYPTION_KEY_FILE": str(key_file),
            },
        ):
            provider = get_key_provider(_reset=True)
            assert isinstance(provider, FileKeyProvider)

    def test_unknown_provider_raises(self):
        with mock.patch.dict(os.environ, {"ENCRYPTION_PROVIDER": "vault"}):
            with pytest.raises((CryptoKeyError, ValueError), match="[Uu]nknown|[Uu]nsupported|vault"):
                get_key_provider(_reset=True)

    def test_file_provider_missing_key_file_env_raises(self):
        with mock.patch.dict(os.environ, {"ENCRYPTION_PROVIDER": "file"}):
            os.environ.pop("ENCRYPTION_KEY_FILE", None)
            with pytest.raises(CryptoKeyError, match="ENCRYPTION_KEY_FILE"):
                get_key_provider(_reset=True)

    def test_singleton_returned_on_second_call(self):
        with mock.patch.dict(
            os.environ,
            {
                "ENCRYPTION_KEY_ACTIVE": KEY_V1,
                "ENCRYPTION_KEY_ACTIVE_ID": "v1",
            },
        ):
            os.environ.pop("ENCRYPTION_PROVIDER", None)
            p1 = get_key_provider(_reset=True)
            p2 = get_key_provider()
            assert p1 is p2
