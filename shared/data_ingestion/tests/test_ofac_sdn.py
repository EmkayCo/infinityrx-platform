"""Tests for shared.data_ingestion.sources.ofac_sdn.

Unit coverage of the CSV parser helpers (positional column mapping,
latin-1 decoding, "-0-" sentinel normalisation, column-count mismatch
skip, embedded-newline handling). Integration with DB upsert is covered
by the live dev run in Wave 9c — no SQLite fixture here because OFAC's
JSONB raw_payload column doesn't round-trip cleanly under SQLite without
the type decorator gymnastics the other ingester tests use, and the
pure-parser tests give us the coverage that matters before the live run.
"""

from __future__ import annotations

from shared.data_ingestion.sources.ofac_sdn import (
    _ADD_COLUMNS,
    _ALT_COLUMNS,
    _COMMENTS_COLUMNS,
    _SDN_COLUMNS,
    _normalise,
    _parse_addresses,
    _parse_aliases,
    _parse_comments,
    _parse_csv_positional,
    _parse_int,
    _parse_sdn,
)

# ---------------------------------------------------------------------------
# _normalise — "-0-" sentinel and whitespace handling
# ---------------------------------------------------------------------------


def test_normalise_returns_none_for_sentinel():
    assert _normalise("-0-") is None


def test_normalise_returns_none_for_sentinel_with_trailing_space():
    """OFAC frequently emits '-0- ' (trailing space) — must also become None."""
    assert _normalise("-0- ") is None


def test_normalise_returns_none_for_empty_string():
    assert _normalise("") is None


def test_normalise_returns_none_for_none():
    assert _normalise(None) is None


def test_normalise_strips_surrounding_whitespace():
    assert _normalise("  hello  ") == "hello"


def test_normalise_preserves_internal_whitespace():
    assert _normalise("Banco Nacional de Cuba") == "Banco Nacional de Cuba"


def test_normalise_preserves_embedded_hyphens():
    """'-0-' is the sentinel but 'foo-0-bar' should stay intact."""
    assert _normalise("foo-0-bar") == "foo-0-bar"


# ---------------------------------------------------------------------------
# _parse_int — int coercion with sentinel and bad-value handling
# ---------------------------------------------------------------------------


def test_parse_int_valid_number():
    assert _parse_int("36") == 36


def test_parse_int_sentinel_returns_none():
    assert _parse_int("-0-") is None


def test_parse_int_sentinel_with_space_returns_none():
    assert _parse_int("-0- ") is None


def test_parse_int_empty_returns_none():
    assert _parse_int("") is None


def test_parse_int_whitespace_returns_none():
    assert _parse_int("   ") is None


def test_parse_int_non_numeric_returns_none():
    assert _parse_int("abc") is None


# ---------------------------------------------------------------------------
# _parse_csv_positional — column-count mismatch and empty-file behaviour
# ---------------------------------------------------------------------------


def test_parse_csv_positional_happy_path(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(
        '36,"AEROCARIBBEAN AIRLINES",-0- ,"CUBA",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- \n',
        encoding="latin-1",
    )
    rows = list(_parse_csv_positional(p, _SDN_COLUMNS))
    assert len(rows) == 1
    assert rows[0]["ent_num"] == 36
    assert rows[0]["sdn_name"] == "AEROCARIBBEAN AIRLINES"
    assert rows[0]["sdn_type"] is None  # -0- → None
    assert rows[0]["program"] == "CUBA"
    # All trailing sentinels become None
    for col in ("title", "call_sign", "vess_type", "tonnage", "grt",
                "vess_flag", "vess_owner", "remarks"):
        assert rows[0][col] is None, f"{col} should be None"


def test_parse_csv_positional_wrong_column_count_skipped(tmp_path):
    """Short row → logged + skipped, not yielded."""
    p = tmp_path / "t.csv"
    # First row has 12 fields (correct), second has 3 (short).
    p.write_text(
        '36,"Name A",X,Y,Z,Z,Z,Z,Z,Z,Z,Z\n'
        '99,"ShortRow",X\n',
        encoding="latin-1",
    )
    rows = list(_parse_csv_positional(p, _SDN_COLUMNS))
    # Only the well-formed row survives.
    assert len(rows) == 1
    assert rows[0]["ent_num"] == 36


def test_parse_csv_positional_latin1_encoding(tmp_path):
    """OFAC files are latin-1 — names can contain non-ASCII characters."""
    p = tmp_path / "t.csv"
    # Write a name containing ñ encoded as latin-1 (0xF1).
    data = '1,"JOSE MARIA MU\xf1OZ",-0-,-0-,-0-,-0-,-0-,-0-,-0-,-0-,-0-,-0-\n'
    p.write_bytes(data.encode("latin-1"))
    rows = list(_parse_csv_positional(p, _SDN_COLUMNS))
    assert rows[0]["sdn_name"] == "JOSE MARIA MUñOZ"


def test_parse_csv_positional_embedded_newline(tmp_path):
    """csv.reader handles newlines inside quoted fields."""
    p = tmp_path / "t.csv"
    p.write_text(
        '1,"Line one\nLine two",A,B,C,D,E,F,G,H,I,J\n',
        encoding="latin-1",
    )
    rows = list(_parse_csv_positional(p, _SDN_COLUMNS))
    assert len(rows) == 1
    assert rows[0]["sdn_name"] == "Line one\nLine two"


def test_parse_csv_positional_empty_file(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("", encoding="latin-1")
    assert list(_parse_csv_positional(p, _SDN_COLUMNS)) == []


# ---------------------------------------------------------------------------
# Per-file parsers — table tagging + ent_num None skip
# ---------------------------------------------------------------------------


def test_parse_sdn_tags_table_and_skips_null_ent_num(tmp_path):
    p = tmp_path / "sdn.csv"
    p.write_text(
        '36,"A",B,C,D,E,F,G,H,I,J,K\n'
        '-0- ,"X",Y,Z,A,B,C,D,E,F,G,H\n',  # ent_num=None → skipped
        encoding="latin-1",
    )
    records = list(_parse_sdn(p))
    assert len(records) == 1
    assert records[0]["table"] == "ofac_sdn"
    assert records[0]["row"]["ent_num"] == 36
    assert "raw_payload" in records[0]["row"]


def test_parse_addresses_requires_both_keys(tmp_path):
    p = tmp_path / "add.csv"
    p.write_text(
        '36,25,"123 Main","Havana","Cuba",-0- \n'           # OK
        '99,-0- ,"No add_num","City","Country",-0- \n'     # add_num=None → skip
        '-0- ,10,"No ent_num","City","Country",-0- \n',    # ent_num=None → skip
        encoding="latin-1",
    )
    records = list(_parse_addresses(p))
    assert len(records) == 1
    assert records[0]["row"]["ent_num"] == 36
    assert records[0]["row"]["add_num"] == 25


def test_parse_aliases_sample_row(tmp_path):
    p = tmp_path / "alt.csv"
    p.write_text(
        '36,12,"aka","AERO-CARIBBEAN",-0- \n',
        encoding="latin-1",
    )
    records = list(_parse_aliases(p))
    assert len(records) == 1
    r = records[0]["row"]
    assert r["ent_num"] == 36 and r["alt_num"] == 12
    assert r["alt_type"] == "aka"
    assert r["alt_name"] == "AERO-CARIBBEAN"
    assert r["alt_remarks"] is None


def test_parse_comments_sample_row(tmp_path):
    p = tmp_path / "sdn_comments.csv"
    p.write_text(
        '17016,"Additional remarks continuation text here."\n',
        encoding="latin-1",
    )
    records = list(_parse_comments(p))
    assert len(records) == 1
    r = records[0]["row"]
    assert r["ent_num"] == 17016
    assert r["remarks3"] == "Additional remarks continuation text here."


# ---------------------------------------------------------------------------
# Column spec integrity
# ---------------------------------------------------------------------------


def test_sdn_columns_are_12():
    """OFAC data dictionary: sdn.csv has exactly 12 columns."""
    assert len(_SDN_COLUMNS) == 12


def test_add_columns_are_6():
    assert len(_ADD_COLUMNS) == 6


def test_alt_columns_are_5():
    assert len(_ALT_COLUMNS) == 5


def test_comments_columns_are_2():
    assert len(_COMMENTS_COLUMNS) == 2


def test_sdn_raw_payload_is_json_string(tmp_path):
    """raw_payload is stored as a JSON string so JSONB round-trips cleanly."""
    import json

    p = tmp_path / "sdn.csv"
    p.write_text('36,"Name",T,P,-0-,-0-,-0-,-0-,-0-,-0-,-0-,-0-\n', encoding="latin-1")
    records = list(_parse_sdn(p))
    payload = records[0]["row"]["raw_payload"]
    parsed = json.loads(payload)
    assert parsed["ent_num"] == 36
    assert parsed["sdn_name"] == "Name"
