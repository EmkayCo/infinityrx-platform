"""RED tests for CSV/Excel enrollment parser with configurable field mapping."""
from __future__ import annotations

import io


from src.services.csv_parser import (
    CsvEnrollmentParser,
    FieldMapping,
    EnrollmentAction,
)


SAMPLE_CSV = """member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action
MEM100,Alice,Johnson,1990-05-10,F,2026-01-01,999999,ABC,GRP1,ADD
MEM101,Bob,Williams,1975-08-22,M,2026-01-01,999999,ABC,GRP1,ADD
MEM102,Carol,Brown,1968-12-01,F,2025-12-01,999999,ABC,GRP1,TRM
"""


class TestCsvEnrollmentParser:
    def _default_mapping(self) -> FieldMapping:
        return FieldMapping(
            member_id="member_id",
            first_name="first_name",
            last_name="last_name",
            date_of_birth="dob",
            gender="gender",
            effective_date="effective_date",
            rx_bin="bin",
            rx_pcn="pcn",
            rx_group="group",
            action="action",
        )

    def test_parse_returns_all_records(self):
        parser = CsvEnrollmentParser(mapping=self._default_mapping())
        records = parser.parse(io.StringIO(SAMPLE_CSV))
        assert len(records) == 3

    def test_add_action_parsed(self):
        parser = CsvEnrollmentParser(mapping=self._default_mapping())
        records = parser.parse(io.StringIO(SAMPLE_CSV))
        assert records[0].action == EnrollmentAction.ADD

    def test_terminate_action_parsed(self):
        parser = CsvEnrollmentParser(mapping=self._default_mapping())
        records = parser.parse(io.StringIO(SAMPLE_CSV))
        assert records[2].action == EnrollmentAction.TERMINATE

    def test_demographics_mapped_correctly(self):
        parser = CsvEnrollmentParser(mapping=self._default_mapping())
        records = parser.parse(io.StringIO(SAMPLE_CSV))
        r = records[0]
        assert r.member_id == "MEM100"
        assert r.first_name == "Alice"
        assert r.last_name == "Johnson"
        assert r.gender == "F"
        from datetime import date
        assert r.date_of_birth == date(1990, 5, 10)
        assert r.effective_date == date(2026, 1, 1)

    def test_rx_id_card_fields_mapped(self):
        parser = CsvEnrollmentParser(mapping=self._default_mapping())
        records = parser.parse(io.StringIO(SAMPLE_CSV))
        r = records[0]
        assert r.rx_bin == "999999"
        assert r.rx_pcn == "ABC"
        assert r.rx_group == "GRP1"

    def test_missing_required_field_returns_validation_error(self):
        csv_missing_bin = """member_id,first_name,last_name,dob,gender,effective_date,pcn,group,action
MEM200,Dave,Lee,1980-01-01,M,2026-01-01,ABC,GRP2,ADD
"""
        mapping = FieldMapping(
            member_id="member_id",
            first_name="first_name",
            last_name="last_name",
            date_of_birth="dob",
            gender="gender",
            effective_date="effective_date",
            rx_bin="bin",  # "bin" column not present
            rx_pcn="pcn",
            rx_group="group",
            action="action",
        )
        parser = CsvEnrollmentParser(mapping=mapping)
        result = parser.parse_with_errors(io.StringIO(csv_missing_bin))
        assert len(result.errors) > 0
        assert result.errors[0].field == "rx_bin"

    def test_invalid_date_format_returns_validation_error(self):
        csv_bad_date = """member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action
MEM300,Eve,Adams,not-a-date,F,2026-01-01,999999,ABC,GRP1,ADD
"""
        parser = CsvEnrollmentParser(mapping=self._default_mapping())
        result = parser.parse_with_errors(io.StringIO(csv_bad_date))
        assert any(e.field == "date_of_birth" for e in result.errors)

    def test_valid_records_still_returned_when_some_invalid(self):
        csv_mixed = """member_id,first_name,last_name,dob,gender,effective_date,bin,pcn,group,action
MEM400,Frank,Garcia,1995-03-15,M,2026-01-01,999999,ABC,GRP1,ADD
MEM401,Grace,Hall,bad-date,F,2026-01-01,999999,ABC,GRP1,ADD
MEM402,Henry,Imai,1988-07-22,M,2026-01-01,999999,ABC,GRP1,ADD
"""
        parser = CsvEnrollmentParser(mapping=self._default_mapping())
        result = parser.parse_with_errors(io.StringIO(csv_mixed))
        assert len(result.valid_records) == 2
        assert len(result.errors) == 1

    def test_custom_field_mapping_alternative_column_names(self):
        """Configurable mapping handles any column name layout."""
        alt_csv = """id,fname,lname,birthdate,sex,eff_dt,BIN,PCN,GRP,act
X001,Tom,Jones,1970-01-01,M,2026-01-01,111111,XYZ,G1,ADD
"""
        mapping = FieldMapping(
            member_id="id",
            first_name="fname",
            last_name="lname",
            date_of_birth="birthdate",
            gender="sex",
            effective_date="eff_dt",
            rx_bin="BIN",
            rx_pcn="PCN",
            rx_group="GRP",
            action="act",
        )
        parser = CsvEnrollmentParser(mapping=mapping)
        records = parser.parse(io.StringIO(alt_csv))
        assert records[0].member_id == "X001"
        assert records[0].first_name == "Tom"
