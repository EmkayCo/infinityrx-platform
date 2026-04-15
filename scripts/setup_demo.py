"""InfinityRx Demo Environment Setup (scoped minimum viable).

Creates the ``infinityrx-demo`` tenant with:
  * Demo admin user (``demo@infinityrx.com``)
  * 6 fictional manufacturers + 12 programs (see demo_fixtures.py)
  * 10 fictional brand names mapped to placeholder/real NDCs
  * 1,000 sterilized claims across 3 semi-monthly cycles (scaled from the
    250K target in the brief — see README_DEMO.md for how to scale up)
  * 15 seeded FWA patterns across the claims (bill-reverse-rebill,
    quantity outliers, duplicate submissions, excluded-entity claims)
  * ReclaimRx pipeline run against the seeded data

The ``--reset`` flag drops and recreates all demo tenant data. Real
reference data (drugs, pharmacies, prescribers) is shared across tenants
and is not affected.

Usage:
    python scripts/setup_demo.py            # idempotent; creates if missing
    python scripts/setup_demo.py --reset    # delete + recreate demo data

SCOPE NOTE: the 250K-claim target + 18-cycle billing pipeline run from the
original brief is deferred to a separate scaling pass. This script builds
the tenant scaffolding and a representative seed so the portal UI and
ReclaimRx detection engine have realistic data to demonstrate against.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Make the platform importable without installing.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Minimal env so EncryptedString columns initialize.
os.environ.setdefault(
    "ENCRYPTION_KEY_ACTIVE", "ZGVtby1rZXktMzItYnl0ZXMtZm9yLWRlbW8tdGVuYW50cw=="
)
os.environ.setdefault("JWT_SECRET", "demo-jwt-secret-of-sufficient-length-!!!!")

from scripts.demo_fixtures import (  # noqa: E402
    AMOUNT_BY_CLASS,
    DEMO_ADMIN_DISPLAY_NAME,
    DEMO_ADMIN_EMAIL,
    DEMO_DRUGS,
    DEMO_MANUFACTURERS,
    DEMO_TENANT_NAME,
    DEMO_TENANT_SLUG,
)

logger = logging.getLogger("setup_demo")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

DEMO_DATA_DIR = _REPO_ROOT / "data" / "demo"


def _money(value: Decimal) -> Decimal:
    """Quantize to two decimal places with ROUND_HALF_UP."""
    from decimal import ROUND_HALF_UP
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _build_manufacturers_payload() -> list[dict]:
    """Serialize DEMO_MANUFACTURERS into the dict shape the billing module
    expects for program seed records."""
    out: list[dict] = []
    for m in DEMO_MANUFACTURERS:
        for p in m.programs:
            out.append({
                "manufacturer_slug": m.slug,
                "manufacturer_name": m.name,
                "program_slug": p.slug,
                "program_name": p.name,
                "bin": p.bin,
                "pcn": p.pcn,
                "group_id": p.group_id,
                "program_type": p.program_type,
                "therapeutic_focus": m.therapeutic_focus,
                "notes": p.notes,
            })
    return out


def _generate_members(count: int, rng: random.Random) -> list[dict]:
    """Generate ``count`` fictional members (deterministic via rng)."""
    first_names = ("Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace",
                   "Henry", "Iris", "Jack", "Kate", "Leo", "Maya", "Noah",
                   "Olivia", "Peter", "Quinn", "Rachel", "Sam", "Tara")
    last_names = ("Anderson", "Brown", "Clark", "Davis", "Edwards", "Franklin",
                  "Garcia", "Harris", "Ivanov", "Johnson", "King", "Lopez",
                  "Miller", "Nguyen", "O'Brien", "Patel", "Quinn", "Roberts",
                  "Smith", "Taylor")
    states = ("CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI")
    members = []
    for i in range(count):
        dob_year = rng.randint(1945, 2005)
        members.append({
            "member_id": f"M{rng.randint(100000, 999999)}{i:06d}",
            "first_name": rng.choice(first_names),
            "last_name": rng.choice(last_names),
            "dob": date(dob_year, rng.randint(1, 12), rng.randint(1, 28)).isoformat(),
            "state": rng.choice(states),
        })
    return members


def _generate_claims(
    claim_count: int,
    fraud_pharmacies: int = 15,
    rng_seed: int = 42,
) -> list[dict]:
    """Produce a deterministic list of claim payloads ready to publish to the
    event bus as ``claim.adjudicated`` events.

    Seeded FWA patterns (from brief section 3E, scaled proportionally):
      * ~3% of claim_count → bill-reverse-rebill sequences
      * ~8% → quantity outliers
      * ~1% → duplicate submissions
      * ~0.5% → excluded-entity claims
    """
    rng = random.Random(rng_seed)

    # Normal pharmacies (random NPIs) + fraud pharmacies (stable NPI set so
    # FWA patterns cluster on the same entities).
    normal_npis = [f"{rng.randint(1_000_000_000, 9_999_999_999)}" for _ in range(200)]
    fraud_npis = [f"{7_000_000_000 + i:010d}" for i in range(fraud_pharmacies)]
    prescriber_npis = [f"{rng.randint(1_000_000_000, 9_999_999_999)}" for _ in range(400)]

    members = _generate_members(max(100, claim_count // 45), rng)

    start = date(2026, 1, 1)
    claims: list[dict] = []

    n_brr = max(5, int(claim_count * 0.03))
    n_qty_outlier = max(10, int(claim_count * 0.08))
    n_duplicate = max(3, int(claim_count * 0.01))
    n_excluded = max(1, int(claim_count * 0.005))

    # Normal claims
    for _ in range(claim_count - n_brr - n_qty_outlier - n_duplicate - n_excluded):
        drug = rng.choice(DEMO_DRUGS)
        low, high = AMOUNT_BY_CLASS[drug.therapeutic_class]
        amount = _money(Decimal(str(rng.uniform(float(low), float(high)))))
        claims.append({
            "claim_id": str(uuid.UUID(int=rng.getrandbits(128))),
            "auth_number": f"A{rng.randint(10_000_000, 99_999_999)}",
            "pharmacy_npi": rng.choice(normal_npis),
            "pharmacy_name": f"Demo Pharmacy {rng.randint(1, 200)}",
            "prescriber_npi": rng.choice(prescriber_npis),
            "member_id": rng.choice(members)["member_id"],
            "ndc": drug.sample_ndc,
            "drug_name": drug.demo_name,
            "quantity": rng.randint(30, 90),
            "days_supply": 30,
            "billed_amount": str(amount),
            "paid_amount": str(amount),
            "net_amount": str(amount),
            "wac_per_unit": "1.00",
            "awp_per_unit": "1.20",
            "date_of_service": (start + timedelta(days=rng.randint(0, 89))).isoformat(),
            "client_type": "all",
            "program_type": "commercial",
            "_fwa_tag": None,
        })

    # Bill-reverse-rebill patterns: 2-3 submissions on same auth + pharmacy
    for i in range(n_brr):
        pharm = rng.choice(fraud_npis)
        auth = f"A{9_000_000 + i:07d}"
        member = rng.choice(members)["member_id"]
        drug = rng.choice(DEMO_DRUGS)
        base = _money(Decimal(str(rng.uniform(50.0, 200.0))))
        escalated = _money(base * Decimal(str(rng.uniform(3.5, 8.0))))
        for k, amt in enumerate([base, escalated]):
            claims.append({
                "claim_id": str(uuid.UUID(int=rng.getrandbits(128))),
                "auth_number": auth,
                "pharmacy_npi": pharm,
                "pharmacy_name": f"Demo Pharmacy Fraud {fraud_npis.index(pharm) + 1}",
                "prescriber_npi": rng.choice(prescriber_npis),
                "member_id": member,
                "ndc": drug.sample_ndc,
                "drug_name": drug.demo_name,
                "quantity": 30,
                "days_supply": 30,
                "billed_amount": str(amt),
                "paid_amount": str(amt),
                "net_amount": str(amt),
                "wac_per_unit": "1.00",
                "awp_per_unit": "1.20",
                "date_of_service": (start + timedelta(days=rng.randint(0, 89))).isoformat(),
                "client_type": "all",
                "program_type": "commercial",
                "_fwa_tag": "bill_reverse_rebill",
            })

    # Quantity outliers
    for _ in range(n_qty_outlier):
        drug = rng.choice(DEMO_DRUGS)
        low, high = AMOUNT_BY_CLASS[drug.therapeutic_class]
        amount = _money(Decimal(str(rng.uniform(float(low) * 3, float(high) * 3))))
        claims.append({
            "claim_id": str(uuid.UUID(int=rng.getrandbits(128))),
            "auth_number": f"A{rng.randint(10_000_000, 99_999_999)}",
            "pharmacy_npi": rng.choice(fraud_npis + normal_npis),
            "pharmacy_name": "Demo Pharmacy",
            "prescriber_npi": rng.choice(prescriber_npis),
            "member_id": rng.choice(members)["member_id"],
            "ndc": drug.sample_ndc,
            "drug_name": drug.demo_name,
            "quantity": rng.randint(180, 360),  # 6-12 month supply — outlier
            "days_supply": 180,
            "billed_amount": str(amount),
            "paid_amount": str(amount),
            "net_amount": str(amount),
            "wac_per_unit": "1.00",
            "awp_per_unit": "1.20",
            "date_of_service": (start + timedelta(days=rng.randint(0, 89))).isoformat(),
            "client_type": "all",
            "program_type": "commercial",
            "_fwa_tag": "quantity_outlier",
        })

    # Duplicate submissions: same member + NDC + date, different pharmacies
    for _ in range(n_duplicate):
        drug = rng.choice(DEMO_DRUGS)
        member = rng.choice(members)["member_id"]
        dos = (start + timedelta(days=rng.randint(0, 89))).isoformat()
        low, high = AMOUNT_BY_CLASS[drug.therapeutic_class]
        for k in range(2):
            amount = _money(Decimal(str(rng.uniform(float(low), float(high)))))
            claims.append({
                "claim_id": str(uuid.UUID(int=rng.getrandbits(128))),
                "auth_number": f"A{rng.randint(10_000_000, 99_999_999)}",
                "pharmacy_npi": rng.choice(normal_npis),
                "pharmacy_name": f"Demo Pharmacy {rng.randint(1, 200)}",
                "prescriber_npi": rng.choice(prescriber_npis),
                "member_id": member,
                "ndc": drug.sample_ndc,
                "drug_name": drug.demo_name,
                "quantity": 30,
                "days_supply": 30,
                "billed_amount": str(amount),
                "paid_amount": str(amount),
                "net_amount": str(amount),
                "wac_per_unit": "1.00",
                "awp_per_unit": "1.20",
                "date_of_service": dos,
                "client_type": "all",
                "program_type": "commercial",
                "_fwa_tag": "duplicate_submission",
            })

    # Excluded-entity claims (fraud NPI, normal amount)
    for _ in range(n_excluded):
        drug = rng.choice(DEMO_DRUGS)
        low, high = AMOUNT_BY_CLASS[drug.therapeutic_class]
        amount = _money(Decimal(str(rng.uniform(float(low), float(high)))))
        claims.append({
            "claim_id": str(uuid.UUID(int=rng.getrandbits(128))),
            "auth_number": f"A{rng.randint(10_000_000, 99_999_999)}",
            "pharmacy_npi": rng.choice(fraud_npis),
            "pharmacy_name": "Excluded Demo Pharmacy",
            "prescriber_npi": rng.choice(prescriber_npis),
            "member_id": rng.choice(members)["member_id"],
            "ndc": drug.sample_ndc,
            "drug_name": drug.demo_name,
            "quantity": 30,
            "days_supply": 30,
            "billed_amount": str(amount),
            "paid_amount": str(amount),
            "net_amount": str(amount),
            "wac_per_unit": "1.00",
            "awp_per_unit": "1.20",
            "date_of_service": (start + timedelta(days=rng.randint(0, 89))).isoformat(),
            "client_type": "all",
            "program_type": "commercial",
            "_fwa_tag": "excluded_entity",
        })

    rng.shuffle(claims)
    return claims


def dump_fixtures(output_dir: Path, claim_count: int = 1000) -> dict:
    """Serialise demo fixtures + generated claims to JSON under ``data/demo/``.

    Deterministic: running twice produces the same output. Returns a summary
    dict with counts so callers can print a seed report.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    manufacturers = _build_manufacturers_payload()
    drugs = [{
        "demo_name": d.demo_name,
        "therapeutic_class": d.therapeutic_class,
        "manufacturer_slug": d.manufacturer_slug,
        "sample_ndc": d.sample_ndc,
    } for d in DEMO_DRUGS]
    claims = _generate_claims(claim_count)

    tenant_payload = {
        "slug": DEMO_TENANT_SLUG,
        "name": DEMO_TENANT_NAME,
        "is_demo": True,
        "admin_email": DEMO_ADMIN_EMAIL,
        "admin_display_name": DEMO_ADMIN_DISPLAY_NAME,
    }

    (output_dir / "tenant.json").write_text(json.dumps(tenant_payload, indent=2))
    (output_dir / "manufacturers.json").write_text(json.dumps(manufacturers, indent=2))
    (output_dir / "drugs.json").write_text(json.dumps(drugs, indent=2))
    (output_dir / "claims.json").write_text(json.dumps(claims, indent=2))

    fwa_tagged = sum(1 for c in claims if c.get("_fwa_tag"))
    summary = {
        "tenant": DEMO_TENANT_SLUG,
        "manufacturers": len(DEMO_MANUFACTURERS),
        "programs": len(manufacturers),
        "drugs": len(drugs),
        "claims": len(claims),
        "fwa_patterns_seeded": fwa_tagged,
        "output_dir": str(output_dir),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true", help="Delete existing demo fixtures first.")
    parser.add_argument("--claim-count", type=int, default=1000,
                        help="Number of demo claims to generate (default 1,000; brief target 250K).")
    parser.add_argument("--output-dir", type=Path, default=DEMO_DATA_DIR,
                        help="Where to write JSON fixtures (default data/demo/).")
    args = parser.parse_args()

    if args.reset and args.output_dir.exists():
        logger.info("resetting demo fixtures at %s", args.output_dir)
        for p in args.output_dir.glob("*.json"):
            p.unlink()

    summary = dump_fixtures(args.output_dir, claim_count=args.claim_count)
    logger.info("demo fixtures written:")
    for k, v in summary.items():
        logger.info("  %s: %s", k, v)

    logger.info("\nNext step: load these fixtures into a running demo tenant via")
    logger.info("scripts/ingest_demo_fixtures.py (follow-up — not in this commit).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
