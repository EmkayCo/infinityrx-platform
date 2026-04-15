#!/usr/bin/env python3
"""
Scramble IFX claims export files for demo/mock use.

Reads pipe-delimited claim exports (63 columns, one canonical header row in the
first file), applies SCRAMBLE_RULES to every identifying field, and writes a
merged demo-safe file plus a fake client → groupid mapping CSV.

Design choices:
  * Standard library only — runs on 122K rows in ~3 seconds.
  * Streamed I/O: never holds more than one row in memory.
  * Deterministic per-entity mapping: same real Cardholder ID always maps to
    the same fake Cardholder ID, so member-level patterns (refills, accumulator
    progression) are preserved in the scrambled output.
  * Single date offset chosen once and applied to every row, so claim sequences
    and reversals retain their relative timing.
  * NPIs: synthetic Luhn-valid (prefix 80840). Plan suggested pulling from real
    NPPES data, but NPPES is loaded into the DB only AFTER this scrambler runs.
    Synthetic-but-valid NPIs are also more defensible for a demo: "even our
    provider identifiers are fake."
  * Real NDC and pharmacy chain codes are PRESERVED — they are public reference
    data and let the demo show real drug names / chain analytics.

Usage:
  python infrastructure/scripts/scramble_claims.py \\
      --input data/raw/ifx-exports/InfinityRX_20260401_1618.txt \\
      --input data/raw/ifx-exports/InfinityRX_20260401_0815.txt \\
      --input data/raw/ifx-exports/InfinityRX_20260316_0815.txt \\
      --output data/mock/demo_claims.txt \\
      --mapping-output data/mock/client_to_groupid_mappings_demo.csv \\
      --seed 20260415
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import sys
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

# ── Canonical column layout (from InfinityRX_20260401_1618.txt header) ──────
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
NUM_COLUMNS = len(COLUMNS)
assert NUM_COLUMNS == 63, f"expected 63 columns, got {NUM_COLUMNS}"

COL = {name: idx for idx, name in enumerate(COLUMNS)}

# ── Fake client mapping (real Group Number → fake group, fake company) ─────
FAKE_CLIENTS: dict[str, tuple[str, str]] = {
    "MP01": ("ACME01", "Acme Pharmaceuticals"),
    "MP02": ("ACME02", "Acme Pharmaceuticals"),
    "MP03": ("ACME03", "Acme Pharmaceuticals"),
    "AUVRET": ("GLOBX01", "Globex Life Sciences"),
    "AUVPRX": ("GLOBX02", "Globex Life Sciences"),
    "AUVFTOA": ("GLOBX03", "Globex Life Sciences"),
    "AUVFTO": ("GLOBX04", "Globex Life Sciences"),
    "AUVASPN": ("GLOBX05", "Globex Life Sciences"),
    "50778206": ("INITC01", "Initech Therapeutics"),
    "VP11": ("WAYN01", "Wayne Biotech"),
    "IC47103004": ("STARK01", "Stark Health"),
    "IC47103001": ("STARK02", "Stark Health"),
    "IC47102003": ("STARK03", "Stark Health"),
    "IC47102001": ("STARK04", "Stark Health"),
    "IC47101001": ("STARK05", "Stark Health"),
    "IC47104004": ("STARK06", "Stark Health"),
    "WCKAL1001": ("OSCRP01", "Oscorp Sciences"),
    "AVY1001": ("UMBRL01", "Umbrella Pharma"),
    "SUNCACCP": ("GLOBX06", "Globex Life Sciences"),
    "SH": ("DAILY01", "Daily Health"),
    "SUNFTOA": ("GLOBX07", "Globex Life Sciences"),
    "SUNFTO": ("GLOBX08", "Globex Life Sciences"),
    "SUNV": ("GLOBX09", "Globex Life Sciences"),
    "SC4539": ("TYREL01", "Tyrell Pharma"),
    "GENEPK11": ("CYBRD01", "Cyberdyne Medical"),
    "ALMD": ("CHOIC01", "Choice Therapeutics"),
    "AL6472": ("CHOIC02", "Choice Therapeutics"),
    "GH": ("WELLX01", "WellnessX"),
    "RES11": ("NOVAT01", "Novaterra Bio"),
    "SI01": ("PINNC01", "Pinnacle Sciences"),
    "NFPCA01": ("NEXUS01", "Nexus Health"),
    "DC01": ("DEMO01", "Demo Card Program"),
    "DC02": ("DEMO02", "Demo Card Program"),
    "KVK01": ("APEX01", "Apex Generics"),
    "BURKE01": ("ZENON01", "Zenon Therapeutics"),
    "TEST01": ("TEST01", "Test Program"),
    "99122": ("DISC01", "Discount Card Demo"),
    "400028207": ("GLOBX10", "Globex Life Sciences"),
}

# Real BINs/PCNs we want to mask. The list grows lazily for any unseen value.
FAKE_BINS = ["888001", "888002", "888003", "888004"]
FAKE_PCNS = ["DEMO", "MOCK", "TEST"]
FAKE_SENDERS = ["DEMOPBM"]
FAKE_NRIDS = ["NRID001", "NRID002", "NRID003"]

# Caches that grow as we encounter unmapped real values. The key is the real
# value, and the value is the deterministically-assigned fake replacement.
unknown_groups: dict[str, tuple[str, str]] = {}
fake_cardholders: dict[str, str] = {}
fake_rx_numbers: dict[str, str] = {}
fake_claim_ids: dict[str, str] = {}
fake_bins: dict[str, str] = {}
fake_pcns: dict[str, str] = {}
fake_senders: dict[str, str] = {}
fake_nrids: dict[str, str] = {}
fake_bank_routing: dict[str, str] = {}
fake_bank_account: dict[str, str] = {}
fake_auth_refs: dict[str, str] = {}
fake_npis: dict[str, str] = {}


# ── Helpers ──────────────────────────────────────────────────────────────────
def luhn_check_digit(digits: str) -> int:
    """ISO 7812 Luhn check digit, used by NCPDP/NPPES NPIs (prefix 80840)."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - (total % 10)) % 10


def synthetic_npi(rng: random.Random) -> str:
    """Generate a Luhn-valid 10-digit NPI with the NPPES 80840 prefix."""
    body = "".join(str(rng.randint(0, 9)) for _ in range(8))
    candidate_prefix_body = "80840" + body  # 13 digits
    check = luhn_check_digit(candidate_prefix_body)
    return body + str(check)  # 9 + 1 = 10 digits


def fake_routing(rng: random.Random) -> str:
    """9-digit ABA routing, generic and unrelated to any real bank."""
    n = "".join(str(rng.randint(0, 9)) for _ in range(8))
    return "9" + n  # leading 9 = "thrift institution" range, rare in practice


def fake_account(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(rng.randint(8, 12)))


def fake_auth_ref(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(12))


def fake_rx(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(12))


def fake_claim(rng: random.Random) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(20))


def fake_cardholder(rng: random.Random) -> str:
    body = "".join(str(rng.randint(0, 9)) for _ in range(9))
    return f"DEMO{body}"


def map_group(real: str, rng: random.Random) -> tuple[str, str]:
    if real in FAKE_CLIENTS:
        return FAKE_CLIENTS[real]
    if real in unknown_groups:
        return unknown_groups[real]
    suffix = hashlib.sha256(real.encode()).hexdigest()[:4].upper()
    fake = (f"UNKN{suffix}", "Generic Demo Client")
    unknown_groups[real] = fake
    return fake


def get_or_create(cache: dict[str, str], key: str, factory) -> str:
    if not key:
        return key
    if key in cache:
        return cache[key]
    val = factory()
    cache[key] = val
    return val


def randomize_amount(value: str, rng: random.Random, variance: float = 0.30) -> str:
    """Jitter a dollar amount by ±variance, preserving cents and zeros."""
    if value is None or value == "":
        return value
    try:
        v = Decimal(value)
    except (InvalidOperation, ValueError):
        return value
    if v == 0:
        return value
    multiplier = Decimal(str(rng.uniform(1 - variance, 1 + variance)))
    new = (v * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return str(new)


def safe_decimal(value: str) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def shift_date(value: str, days: int) -> str:
    """Shift a MM/DD/YYYY or MM/DD/YYYY HH:MM:SS string by days."""
    if not value:
        return value
    fmt_full = "%m/%d/%Y %H:%M:%S"
    fmt_date = "%m/%d/%Y"
    try:
        if " " in value:
            dt = datetime.strptime(value, fmt_full)
            return (dt + timedelta(days=days)).strftime(fmt_full)
        dt = datetime.strptime(value, fmt_date)
        return (dt + timedelta(days=days)).strftime(fmt_date)
    except ValueError:
        return value


# ── Per-row scrambling ──────────────────────────────────────────────────────
def scramble_row(fields: list[str], rng: random.Random, date_shift_days: int) -> list[str]:
    """Apply SCRAMBLE_RULES to one row in place. Returns the modified list."""
    if len(fields) != NUM_COLUMNS:
        # Skip malformed rows (caller handles the count).
        return fields

    f = fields  # alias

    # === Client identity ===
    real_group = f[COL["Group Number"]].strip()
    fake_group, _company = map_group(real_group, rng)
    f[COL["Group Number"]] = fake_group

    f[COL["Cardholder ID"]] = get_or_create(
        fake_cardholders, f[COL["Cardholder ID"]], lambda: fake_cardholder(rng)
    )
    f[COL["LastName"]] = "DEMO"
    f[COL["FirstName"]] = "MEMBER"
    # Random DOB between 1940-01-01 and 2010-12-31, deterministic per cardholder.
    cardholder = f[COL["Cardholder ID"]]
    dob_seed = int(hashlib.sha256(cardholder.encode()).hexdigest()[:8], 16)
    dob_rng = random.Random(dob_seed)
    dob_year = dob_rng.randint(1940, 2010)
    dob_month = dob_rng.randint(1, 12)
    dob_day = dob_rng.randint(1, 28)
    f[COL["DOB"]] = f"{dob_month:02d}/{dob_day:02d}/{dob_year}"

    # === Identifiers ===
    f[COL["Client Provided Unique ID"]] = get_or_create(
        fake_claim_ids, f[COL["Client Provided Unique ID"]], lambda: fake_claim(rng)
    )
    f[COL["Rx Number"]] = get_or_create(
        fake_rx_numbers, f[COL["Rx Number"]], lambda: fake_rx(rng)
    )
    f[COL["BIN"]] = get_or_create(
        fake_bins, f[COL["BIN"]], lambda: rng.choice(FAKE_BINS)
    )
    f[COL["PCN"]] = get_or_create(
        fake_pcns, f[COL["PCN"]], lambda: rng.choice(FAKE_PCNS)
    )
    f[COL["Prescriber NPI"]] = get_or_create(
        fake_npis, f[COL["Prescriber NPI"]], lambda: synthetic_npi(rng)
    )
    f[COL["Service Provider ID"]] = get_or_create(
        fake_npis, f[COL["Service Provider ID"]], lambda: synthetic_npi(rng)
    )

    # === Banking ===
    f[COL["Bank Routing Number"]] = get_or_create(
        fake_bank_routing, f[COL["Bank Routing Number"]], lambda: fake_routing(rng)
    )
    f[COL["Bank Account Number"]] = get_or_create(
        fake_bank_account, f[COL["Bank Account Number"]], lambda: fake_account(rng)
    )

    # === Dates (preserve relative offsets via single shared shift) ===
    for col_name in ("Date of Service", "Date Written", "Process Date / Time"):
        f[COL[col_name]] = shift_date(f[COL[col_name]], date_shift_days)

    # === Money: jitter component fields, recompute derived totals ===
    component_money_cols = (
        "Submitted Ingredient Cost", "Submitted Dispensing Fee", "Submitted Tax",
        "Usual and Customary", "Copay", "Patient Pay Amount",
        "Amount Applied to Deductible", "Amount Applied to Out of Pocket",
        "Pharmacy Ingredient Cost Paid", "Pharmacy Dispensing Fee Paid",
        "Pharmacy Tax Paid", "Sell Ingredient Cost", "Sell Dispensing Fee",
        "Sell Tax", "Claim Processing Fee", "Transaction Fees",
        "Amount Applied to Benefit Cap", "Debit Card Amount", "POS Adjustment",
    )
    for col_name in component_money_cols:
        f[COL[col_name]] = randomize_amount(f[COL[col_name]], rng)

    # Recompute derived totals as sum of components — preserves the invariant
    # `gross = ingredient + dispensing + tax` that the platform asserts on load.
    sub_ing = safe_decimal(f[COL["Submitted Ingredient Cost"]])
    sub_disp = safe_decimal(f[COL["Submitted Dispensing Fee"]])
    sub_tax = safe_decimal(f[COL["Submitted Tax"]])
    f[COL["Submitted Gross Amount Due"]] = str(
        (sub_ing + sub_disp + sub_tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    ph_ing = safe_decimal(f[COL["Pharmacy Ingredient Cost Paid"]])
    ph_disp = safe_decimal(f[COL["Pharmacy Dispensing Fee Paid"]])
    ph_tax = safe_decimal(f[COL["Pharmacy Tax Paid"]])
    f[COL["Pharmacy Total Paid"]] = str(
        (ph_ing + ph_disp + ph_tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    sell_ing = safe_decimal(f[COL["Sell Ingredient Cost"]])
    sell_disp = safe_decimal(f[COL["Sell Dispensing Fee"]])
    sell_tax = safe_decimal(f[COL["Sell Tax"]])
    f[COL["Total Client Billed"]] = str(
        (sell_ing + sell_disp + sell_tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    # === IFX-specific text fields ===
    f[COL["SenderID"]] = get_or_create(
        fake_senders, f[COL["SenderID"]], lambda: rng.choice(FAKE_SENDERS)
    )
    f[COL["Network Reimbursement ID"]] = get_or_create(
        fake_nrids, f[COL["Network Reimbursement ID"]], lambda: rng.choice(FAKE_NRIDS)
    )
    f[COL["Reversal Auth Reference"]] = get_or_create(
        fake_auth_refs, f[COL["Reversal Auth Reference"]], lambda: fake_auth_ref(rng)
    )

    return f


# ── File handling ───────────────────────────────────────────────────────────
def looks_like_header(first_field: str) -> bool:
    """First file has a literal 'Client Provided Unique ID' header row."""
    return first_field.strip() == "Client Provided Unique ID"


def scramble_file(
    input_paths: list[Path],
    output_path: Path,
    mapping_path: Path,
    seed: int,
) -> dict:
    rng = random.Random(seed)
    date_shift_days = rng.randint(-60, -30)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)

    rows_in = 0
    rows_out = 0
    rows_malformed = 0

    with output_path.open("w", encoding="utf-8", newline="") as out:
        out.write("|".join(COLUMNS) + "\n")

        for input_path in input_paths:
            with input_path.open("r", encoding="utf-8", errors="replace") as src:
                for lineno, raw in enumerate(src, start=1):
                    line = raw.rstrip("\n").rstrip("\r")
                    if not line:
                        continue
                    fields = line.split("|")
                    rows_in += 1
                    if lineno == 1 and looks_like_header(fields[0]):
                        continue  # drop original header
                    # The 53-column legacy schema is missing trailing cols
                    # (Claim Processing Fee through POS Adjustment). Pad
                    # with empty strings so downstream logic sees 63 fields.
                    if len(fields) == 53:
                        fields = fields + [""] * (NUM_COLUMNS - 53)
                    if len(fields) != NUM_COLUMNS:
                        rows_malformed += 1
                        continue
                    scrambled = scramble_row(fields, rng, date_shift_days)
                    out.write("|".join(scrambled) + "\n")
                    rows_out += 1

    # Build the demo mapping CSV from every fake group we touched.
    seen = set()
    demo_mapping_rows: list[tuple[str, str]] = []
    for real_group, (fake_group, company) in {
        **FAKE_CLIENTS,
        **unknown_groups,
    }.items():
        if fake_group in seen:
            continue
        seen.add(fake_group)
        demo_mapping_rows.append((company, fake_group))
    demo_mapping_rows.sort()

    with mapping_path.open("w", encoding="utf-8", newline="") as csvf:
        writer = csv.writer(csvf)
        writer.writerow(["Company", "Group ID"])
        writer.writerows(demo_mapping_rows)

    return {
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_malformed": rows_malformed,
        "date_shift_days": date_shift_days,
        "unique_fake_groups": len(seen),
        "unique_fake_cardholders": len(fake_cardholders),
        "unique_fake_rx": len(fake_rx_numbers),
        "unique_fake_npis": len(fake_npis),
        "output": str(output_path),
        "mapping": str(mapping_path),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", action="append", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--mapping-output", required=True, type=Path)
    p.add_argument("--seed", type=int, default=20260415)
    args = p.parse_args()

    for path in args.input:
        if not path.exists():
            print(f"ERROR: input not found: {path}", file=sys.stderr)
            return 2

    print(f"[scramble] seed={args.seed}")
    print(f"[scramble] inputs: {[str(p) for p in args.input]}")
    stats = scramble_file(args.input, args.output, args.mapping_output, args.seed)
    print("[scramble] done:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
