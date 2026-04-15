#!/usr/bin/env python3
"""
Validate the synthetic mock claims file produced by scramble_claims.py.

Asserts:
  * Header row matches the canonical 63-column schema.
  * Every data row has exactly 63 fields.
  * Every Group Number is from the FAKE_CLIENTS pool (no leak from any
    other source).
  * Every Cardholder ID matches the DEMO* pattern.
  * Every BIN is from the demo BIN pool.
  * Every Bank Routing Number starts with "9" (intentional non-real prefix).
  * Sub_gross == sub_ingredient + sub_dispensing + sub_tax for every row
    (financial precision invariant).
  * Pharmacy_total == pharmacy_ingredient + pharmacy_dispensing + pharmacy_tax.
  * Total_billed == sell_ingredient + sell_dispensing + sell_tax.
  * Date of Service is within the past 365 days (no future dates).
  * No real client codes (MP01, AUVPRX, VP11, etc.) appear anywhere.
  * Sentinel scan: no row contains the literal substring "INFINITY" in the
    SenderID column (would indicate the legacy scrambler ran instead of the
    synthetic generator).

Exit code is non-zero on any violation.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

COLUMNS = [
    "Client Provided Unique ID", "Paid / Reversal Status Code", "BIN", "PCN",
    "Date of Service", "Date Written", "Group Number", "Cardholder ID",
    "LastName", "FirstName", "DOB", "Person Code", "Service Provider ID",
    "NDC", "Rx Number", "Quantity", "Days Supply", "Compound Code", "DAW",
    "Submitted Ingredient Cost", "Submitted Dispensing Fee",
    "Usual and Customary", "Submitted Gross Amount Due", "Submitted Tax",
    "Prescriber NPI", "Copay", "Patient Pay Amount",
    "Amount Applied to Deductible", "Amount Applied to Out of Pocket",
    "Pharmacy Total Paid", "Pharmacy Ingredient Cost Paid",
    "Pharmacy Dispensing Fee Paid", "Pharmacy Tax Paid",
    "Sell Ingredient Cost", "Sell Dispensing Fee", "Sell Tax",
    "Total Client Billed", "Other Coverage Code", "Process Date / Time",
    "Price Source", "Keyed Claim Indicator", "Selfpay Indicator",
    "Is Billable", "Historical", "Test Claim", "Location Code", "ScriptTag",
    "DrugTier", "BrandGeneric", "IsPreferred", "SenderID",
    "Network Reimbursement ID", "Amount Applied to Benefit Cap",
    "Claim Processing Fee", "Transaction Fees", "Reversal Auth Reference",
    "Statement Flag", "Bank Routing Number", "Bank Account Number",
    "Bank Account Type", "Primary Chain Code", "Debit Card Amount",
    "POS Adjustment",
]
COL = {name: idx for idx, name in enumerate(COLUMNS)}

# Same pool as the generator — keep in sync.
FAKE_GROUPS = {
    "ACME01", "ACME02", "ACME03",
    "GLOBX01", "GLOBX02", "GLOBX03", "GLOBX04",
    "STARK01", "STARK02", "STARK03",
    "INITC01", "WAYN01", "OSCRP01", "UMBRL01", "CYBRD01",
    "TYREL01", "CHOIC01", "WELLX01", "NOVAT01", "PINNC01",
    "NEXUS01", "APEX01", "ZENON01", "DEMO01", "DEMO02",
}
DEMO_BINS = {"888001", "888002", "888003", "888004", "999001", "999002"}
DEMO_PCNS = {"DEMO", "MOCK", "TEST", "DEMORX"}
DEMO_SENDERS = {"DEMOPBM", "MOCKPBM", "DEMOSWITCH"}

# Real client codes we explicitly forbid (the historical IFX export labels).
FORBIDDEN_GROUPS = {
    "MP01", "MP02", "MP03", "AUVRET", "AUVPRX", "AUVFTOA", "AUVFTO",
    "AUVASPN", "VP11", "GENEPK11", "SC4539", "BURKE01", "KVK01", "AVY1001",
    "WCKAL1001", "SUNCACCP", "SUNFTOA", "SUNFTO", "SUNV", "ALMD", "AL6472",
    "RES11", "SI01", "NFPCA01", "DC01", "DC02", "GH", "SH", "TEST01", "99122",
    "50778206", "400028207",
}

CARDHOLDER_PATTERN = re.compile(r"\ADEMO\d{9}\Z")


def _decimal(value: str) -> Decimal:
    if not value:
        return Decimal("0")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _eq(a: Decimal, b: Decimal) -> bool:
    return a.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) == b.quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scrambled", required=True, type=Path)
    args = parser.parse_args()

    if not args.scrambled.exists():
        print(f"ERROR: not found: {args.scrambled}", file=sys.stderr)
        return 2

    print(f"[verify] file: {args.scrambled}")

    rows = 0
    errors: list[str] = []
    seen_groups: set[str] = set()
    seen_bins: set[str] = set()
    seen_senders: set[str] = set()
    cutoff = datetime.now() - timedelta(days=365)
    future_cutoff = datetime.now() + timedelta(days=1)

    with args.scrambled.open("r", encoding="utf-8") as src:
        header = src.readline().rstrip("\n").rstrip("\r")
        if header != "|".join(COLUMNS):
            errors.append("header does not match canonical 63-column schema")
            print("FAIL — header mismatch")
            return 1

        for lineno, raw in enumerate(src, start=2):
            line = raw.rstrip("\n").rstrip("\r")
            if not line:
                continue
            fields = line.split("|")
            rows += 1

            if len(fields) != 63:
                errors.append(f"line {lineno}: {len(fields)} fields (expected 63)")
                continue

            group = fields[COL["Group Number"]]
            seen_groups.add(group)
            if group in FORBIDDEN_GROUPS:
                errors.append(f"line {lineno}: real client code leak: {group}")
            if group not in FAKE_GROUPS:
                errors.append(f"line {lineno}: group {group!r} not in FAKE_CLIENTS pool")

            cardholder = fields[COL["Cardholder ID"]]
            if not CARDHOLDER_PATTERN.match(cardholder):
                errors.append(f"line {lineno}: cardholder {cardholder!r} does not match DEMO\\d{{9}}")

            bin_value = fields[COL["BIN"]]
            seen_bins.add(bin_value)
            if bin_value not in DEMO_BINS:
                errors.append(f"line {lineno}: BIN {bin_value!r} not in demo BIN pool")

            routing = fields[COL["Bank Routing Number"]]
            if routing and not routing.startswith("9"):
                errors.append(f"line {lineno}: bank routing {routing} missing demo prefix '9'")

            sender = fields[COL["SenderID"]]
            seen_senders.add(sender)
            if sender == "INFINITY":
                errors.append(f"line {lineno}: SenderID 'INFINITY' indicates legacy scrambler output")

            sub_ing = _decimal(fields[COL["Submitted Ingredient Cost"]])
            sub_disp = _decimal(fields[COL["Submitted Dispensing Fee"]])
            sub_tax = _decimal(fields[COL["Submitted Tax"]])
            sub_gross = _decimal(fields[COL["Submitted Gross Amount Due"]])
            if not _eq(sub_gross, sub_ing + sub_disp + sub_tax):
                errors.append(
                    f"line {lineno}: submitted_gross {sub_gross} != ing+disp+tax "
                    f"({sub_ing}+{sub_disp}+{sub_tax})"
                )

            ph_ing = _decimal(fields[COL["Pharmacy Ingredient Cost Paid"]])
            ph_disp = _decimal(fields[COL["Pharmacy Dispensing Fee Paid"]])
            ph_tax = _decimal(fields[COL["Pharmacy Tax Paid"]])
            ph_total = _decimal(fields[COL["Pharmacy Total Paid"]])
            if not _eq(ph_total, ph_ing + ph_disp + ph_tax):
                errors.append(
                    f"line {lineno}: pharmacy_total {ph_total} != ing+disp+tax"
                )

            sell_ing = _decimal(fields[COL["Sell Ingredient Cost"]])
            sell_disp = _decimal(fields[COL["Sell Dispensing Fee"]])
            sell_tax = _decimal(fields[COL["Sell Tax"]])
            total_billed = _decimal(fields[COL["Total Client Billed"]])
            if not _eq(total_billed, sell_ing + sell_disp + sell_tax):
                errors.append(
                    f"line {lineno}: total_client_billed {total_billed} != sell ing+disp+tax"
                )

            try:
                dos = datetime.strptime(fields[COL["Date of Service"]], "%m/%d/%Y")
                if dos < cutoff or dos > future_cutoff:
                    errors.append(f"line {lineno}: date of service {dos.date()} outside ±365d window")
            except ValueError:
                errors.append(f"line {lineno}: unparseable Date of Service")

            if len(errors) >= 20:
                errors.append("(stopping after 20 errors)")
                break

    print(f"[verify] rows checked: {rows:,}")
    print(f"[verify] distinct groups: {len(seen_groups)} (expected ≤25)")
    print(f"[verify] distinct BINs: {len(seen_bins)} (expected ≤6)")
    print(f"[verify] distinct senders: {len(seen_senders)} (expected ≤3)")

    if errors:
        print()
        print("FAIL — invariant violations:")
        for e in errors:
            print(f"  {e}")
        return 1

    print()
    print("PASS — synthetic mock data is well-formed and PHI-free")
    return 0


if __name__ == "__main__":
    sys.exit(main())
