#!/usr/bin/env python3
"""
Verify a scrambled IFX claims output contains NO real PHI / client identifiers.

Reads the original raw input(s) and the scrambled output, then asserts:

  * No real Group Number from the input set survives in the scrambled output.
  * No real Cardholder ID survives.
  * No real Bank Routing Number survives.
  * No real Bank Account Number survives.
  * No real Client Provided Unique ID (claim ID) survives.
  * No real Rx Number survives.
  * Output row count == input row count (minus the 1 header in file 1).
  * NDCs ARE preserved (public reference data).

Exit code is non-zero on any leak. Prints a summary report.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Match scramble_claims.py — keep in sync if columns ever change.
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


def collect_set(paths: list[Path], col_name: str) -> set[str]:
    """Collect distinct non-empty values for one column across files."""
    idx = COL[col_name]
    seen: set[str] = set()
    rows = 0
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as src:
            for lineno, line in enumerate(src, start=1):
                fields = line.rstrip("\n").rstrip("\r").split("|")
                if lineno == 1 and fields[0].strip() == "Client Provided Unique ID":
                    continue
                if len(fields) == 53:
                    fields = fields + [""] * (len(COLUMNS) - 53)
                if len(fields) != len(COLUMNS):
                    continue
                rows += 1
                v = fields[idx].strip()
                if v:
                    seen.add(v)
    return seen


def count_rows(paths: list[Path]) -> int:
    n = 0
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as src:
            for lineno, line in enumerate(src, start=1):
                fields = line.rstrip("\n").rstrip("\r").split("|")
                if lineno == 1 and fields[0].strip() == "Client Provided Unique ID":
                    continue
                if not line.strip():
                    continue
                if len(fields) == 53:
                    fields = fields + [""] * (len(COLUMNS) - 53)
                if len(fields) != len(COLUMNS):
                    continue
                n += 1
    return n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", action="append", required=True, type=Path)
    p.add_argument("--scrambled", required=True, type=Path)
    args = p.parse_args()

    for path in args.input + [args.scrambled]:
        if not path.exists():
            print(f"ERROR: not found: {path}", file=sys.stderr)
            return 2

    print(f"[verify] originals: {[str(p) for p in args.input]}")
    print(f"[verify] scrambled: {args.scrambled}")

    fields_to_check = [
        "Group Number",
        "Cardholder ID",
        "Bank Routing Number",
        "Bank Account Number",
        "Client Provided Unique ID",
        "Rx Number",
    ]

    leaks: dict[str, list[str]] = {}
    for col_name in fields_to_check:
        original = collect_set(args.input, col_name)
        scrambled = collect_set([args.scrambled], col_name)
        overlap = original & scrambled
        if overlap:
            leaks[col_name] = sorted(overlap)[:10]
        print(f"  {col_name:30s} originals={len(original):6d} scrambled={len(scrambled):6d} leak={len(overlap)}")

    # NDC SHOULD overlap (public reference data — preserved by design).
    orig_ndcs = collect_set(args.input, "NDC")
    scr_ndcs = collect_set([args.scrambled], "NDC")
    ndc_preserved = len(orig_ndcs & scr_ndcs)
    print(f"  NDC (public, expected to overlap)  originals={len(orig_ndcs)}  scrambled={len(scr_ndcs)}  preserved={ndc_preserved}")

    in_rows = count_rows(args.input)
    out_rows = count_rows([args.scrambled])
    print(f"  Row count: input={in_rows}, scrambled={out_rows}")

    print()
    if leaks:
        print("FAIL — PHI / identifier leaks detected:")
        for col_name, samples in leaks.items():
            print(f"  {col_name}: {len(samples)} sample leaks: {samples}")
        return 1
    if ndc_preserved == 0:
        print("FAIL — NDCs not preserved (should be public reference data)")
        return 1
    if out_rows != in_rows:
        print(f"FAIL — row count mismatch (in={in_rows}, out={out_rows})")
        return 1
    print("PASS — no PHI leaks, NDCs preserved, row counts match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
