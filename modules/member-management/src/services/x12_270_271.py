"""HIPAA X12 270/271 eligibility transaction parser and builder.

270 = eligibility inquiry (inbound from trading partner)
271 = eligibility response (outbound from us)

Supports 005010X279A1 implementation guide.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any


class X12ParseError(ValueError):
    pass


@dataclass
class X12EligibilityResponse:
    """Parsed/built 271 response (for testing and programmatic use)."""
    is_eligible: bool
    member_id: str
    plan_name: str | None = None
    rejection_reason: str | None = None
    raw_271: str | None = None


class X12ServiceTypeCode(str, Enum):
    MEDICAL = "30"
    PRESCRIPTION_DRUG = "96"
    DENTAL = "35"
    VISION = "AL"
    MENTAL_HEALTH = "MH"


_SERVICE_TYPE_MAP = {code.value: code for code in X12ServiceTypeCode}


@dataclass
class X12EligibilityInquiry:
    member_id: str
    date_of_service: date
    payer_id: str
    service_type_codes: list[X12ServiceTypeCode] = field(default_factory=list)
    date_of_birth: date | None = None
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    trace_number: str | None = None
    cardholder_id: str | None = None
    person_code: str | None = None


def _parse_x12_date(value: str) -> date:
    """Parse 8-digit CCYYMMDD X12 date."""
    if len(value) != 8 or not value.isdigit():
        raise X12ParseError(f"invalid X12 date: {value!r}")
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def _split_x12(raw: str) -> list[list[str]]:
    """Split X12 transaction into list of element lists."""
    raw = raw.strip()
    if not raw.startswith("ISA"):
        raise X12ParseError("missing ISA envelope")

    # ISA is exactly 106 chars; segment terminator is the last char of ISA
    if len(raw) < 106:
        raise X12ParseError("ISA segment too short")
    seg_term = raw[105]
    elem_sep = raw[3]

    segments = []
    for seg_raw in raw.split(seg_term):
        seg_raw = seg_raw.strip()
        if seg_raw:
            segments.append(seg_raw.split(elem_sep))
    return segments


class X12Parser:
    """Parse inbound HIPAA 270 transaction into X12EligibilityInquiry."""

    def parse_270(self, raw: str) -> X12EligibilityInquiry:
        try:
            segments = _split_x12(raw)
        except X12ParseError:
            raise

        st_found = False
        for seg in segments:
            if seg[0] == "ST":
                st_found = True
                if len(seg) < 2 or seg[1] != "270":
                    raise X12ParseError(f"expected 270 transaction, got {seg[1]!r}")
                break

        if not st_found:
            raise X12ParseError("missing ST transaction segment")

        member_id: str | None = None
        date_of_service: date | None = None
        date_of_birth: date | None = None
        first_name: str | None = None
        last_name: str | None = None
        gender: str | None = None
        payer_id: str | None = None
        trace_number: str | None = None
        service_codes: list[X12ServiceTypeCode] = []

        in_member_hl = False

        for seg in segments:
            tag = seg[0]

            if tag == "HL":
                # HL*3*2*22*0 → level 22 = subscriber/member
                if len(seg) > 3 and seg[3] == "22":
                    in_member_hl = True
                elif len(seg) > 3 and seg[3] in ("20", "21"):
                    in_member_hl = False

            elif tag == "NM1" and len(seg) > 1:
                if seg[1] == "PR" and len(seg) > 9:
                    payer_id = seg[9]
                elif seg[1] == "IL" and in_member_hl:
                    last_name = seg[3] if len(seg) > 3 else None
                    first_name = seg[4] if len(seg) > 4 else None
                    if len(seg) > 9:
                        member_id = seg[9]

            elif tag == "DMG" and in_member_hl and len(seg) > 2:
                if len(seg) > 2 and seg[2]:
                    date_of_birth = _parse_x12_date(seg[2])
                if len(seg) > 3 and seg[3]:
                    gender = seg[3]

            elif tag == "DTP" and len(seg) > 3:
                if seg[1] == "291":
                    date_of_service = _parse_x12_date(seg[3])

            elif tag == "TRN" and len(seg) > 2:
                trace_number = seg[2]

            elif tag == "EQ" and len(seg) > 1:
                for code_val in seg[1:]:
                    if code_val in _SERVICE_TYPE_MAP:
                        service_codes.append(_SERVICE_TYPE_MAP[code_val])

        if member_id is None:
            raise X12ParseError("missing member NM1*IL segment with member ID")
        if date_of_service is None:
            raise X12ParseError("missing DTP*291 date of service")
        if payer_id is None:
            raise X12ParseError("missing payer NM1*PR segment")

        return X12EligibilityInquiry(
            member_id=member_id,
            date_of_service=date_of_service,
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            payer_id=payer_id,
            trace_number=trace_number,
            service_type_codes=service_codes if service_codes else [X12ServiceTypeCode.PRESCRIPTION_DRUG],
        )


class X12ResponseBuilder:
    """Build outbound HIPAA 271 eligibility response."""

    _SENDER_ID = "INFINITYRX     "
    _RECEIVER_ID = "TRADINGPARTNER "

    def _isa(self, control_number: int, today: str, now: str) -> str:
        ctrl = str(control_number).zfill(9)
        return (
            f"ISA*00*          *00*          *ZZ*{self._SENDER_ID}*ZZ*{self._RECEIVER_ID}"
            f"*{today}*{now}*^*00501*{ctrl}*0*T*:~"
        )

    def _gs(self, control_number: int, today: str, now: str) -> str:
        ctrl = str(control_number)
        return f"GS*HB*INFINITYRX*TRADINGPARTNER*{today}*{now}*{ctrl}*X*005010X279A1~"

    def _iea(self, control_number: int) -> str:
        return f"IEA*1*{str(control_number).zfill(9)}~"

    def _ge(self, control_number: int) -> str:
        return f"GE*1*{str(control_number)}~"

    def _today_str(self) -> tuple[str, str]:
        now = datetime.now(UTC)
        return now.strftime("%y%m%d"), now.strftime("%H%M")

    def build_eligible_271(
        self,
        inquiry: X12EligibilityInquiry,
        plan_name: str,
        coverage_type: str,
        benefit_year_start: date,
        benefit_year_end: date,
        cob_records: list[Any],
        control_number: int,
    ) -> str:
        today_str, now_str = self._today_str()
        ctrl = str(control_number).zfill(9)
        last = inquiry.last_name or ""
        first = inquiry.first_name or ""
        dob_str = inquiry.date_of_birth.strftime("%Y%m%d") if inquiry.date_of_birth else ""
        dos_str = inquiry.date_of_service.strftime("%Y%m%d")
        by_start = benefit_year_start.strftime("%Y%m%d")
        by_end = benefit_year_end.strftime("%Y%m%d")
        trace = inquiry.trace_number or ""
        member_id = inquiry.member_id
        payer_id = inquiry.payer_id

        segments: list[str] = [
            self._isa(control_number, today_str, now_str),
            self._gs(control_number, today_str, now_str),
            f"ST*271*0001*005010X279A1~",
            f"BHT*0022*11*{ctrl}*{today_str}*{now_str}~",
            # Payer HL
            "HL*1**20*1~",
            f"NM1*PR*2*INFINITYRX*****PI*{payer_id}~",
            # Provider HL
            "HL*2*1*21*1~",
            "NM1*1P*2*INFINITYRX PHARMACY*****XX*1234567893~",
            # Subscriber HL
            "HL*3*2*22*0~",
            f"TRN*2*{trace}*9INFINITYRX~",
            f"NM1*IL*1*{last}*{first}****MI*{member_id}~",
        ]

        if dob_str:
            gender = inquiry.gender or "U"
            segments.append(f"DMG*D8*{dob_str}*{gender}~")

        segments.append(f"DTP*291*D8*{dos_str}~")

        # Eligibility/benefit info
        segments.append("EB*1**96*" + plan_name[:50] + "~")
        segments.append(f"DTP*346*RD8*{by_start}-{by_end}~")

        # COB info
        for cob in cob_records:
            cob_name = getattr(cob, "other_payer_name", None) or ""
            cob_bin = getattr(cob, "other_payer_bin", None) or ""
            if cob_name or cob_bin:
                segments.append(f"OI***Y*P**Y~")
                segments.append(f"MOA**{cob_bin}*{cob_name}~")

        segment_count = len([s for s in segments if not s.startswith("ISA") and not s.startswith("GS")])
        segments.append(f"SE*{segment_count}*0001~")
        segments.append(self._ge(control_number))
        segments.append(self._iea(control_number))

        return "".join(segments)

    def build_ineligible_271(
        self,
        inquiry: X12EligibilityInquiry,
        rejection_reason: str,
        control_number: int,
    ) -> str:
        today_str, now_str = self._today_str()
        ctrl = str(control_number).zfill(9)
        last = inquiry.last_name or ""
        first = inquiry.first_name or ""
        dos_str = inquiry.date_of_service.strftime("%Y%m%d")
        trace = inquiry.trace_number or ""
        member_id = inquiry.member_id
        payer_id = inquiry.payer_id

        segments: list[str] = [
            self._isa(control_number, today_str, now_str),
            self._gs(control_number, today_str, now_str),
            "ST*271*0001*005010X279A1~",
            f"BHT*0022*11*{ctrl}*{today_str}*{now_str}~",
            "HL*1**20*1~",
            f"NM1*PR*2*INFINITYRX*****PI*{payer_id}~",
            "HL*2*1*21*1~",
            "NM1*1P*2*INFINITYRX PHARMACY*****XX*1234567893~",
            "HL*3*2*22*0~",
            f"TRN*2*{trace}*9INFINITYRX~",
            f"NM1*IL*1*{last}*{first}****MI*{member_id}~",
            f"DTP*291*D8*{dos_str}~",
            "EB*6~~30~",
        ]

        segment_count = len([s for s in segments if not s.startswith("ISA") and not s.startswith("GS")])
        segments.append(f"SE*{segment_count}*0001~")
        segments.append(self._ge(control_number))
        segments.append(self._iea(control_number))

        return "".join(segments)
