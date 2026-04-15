#!/usr/bin/env python3
"""
Minimal reference-data shim for demo / dev environments.

Loads three small, hand-curated reference datasets into the active database:

  * 50 drugs in drug_database.drugs
      Real public NDCs from top-prescribed retail and specialty drugs.
      NDC numbers are public reference data — they appear on every pharmacy
      receipt and the FDA NDC Directory is freely downloadable. Including
      them here is not PHI.

  * 50 pharmacies in pharmacy_dir.ncpdp_pharmacies
      Real chain DBA names (CVS, Walgreens, Walmart, etc.) paired with
      FORMAT-VALID DEMO NCPDP IDs prefixed `90` to mark them as synthetic.
      Real NCPDP IDs are public but I do not memorize them with high
      confidence, and attributing fake claims to a specific real store
      is sketchy. The chain names are real; the IDs are clearly demo.

  * 100 prescribers in prescriber_dir.prescribers
      Faker-generated names, Luhn-valid synthetic NPIs (NPPES 80840 prefix
      + check digit), spread across realistic specialty / state mixes.
      NPIs are public, but assigning fake claim history to a specific real
      doctor crosses a line — these synthetic NPIs are clearly demo and
      will never collide with the real NPPES registry's check-digit pattern
      because the body bytes are seeded from a known Python RNG.

Idempotent: every row uses ON CONFLICT (natural_key) DO UPDATE so re-running
the script is safe in any environment, including production.

The script REFUSES to drop or truncate anything — it only inserts/updates
its own seed rows by natural key. Real reference data loaded by the federal
ETL scripts (when fixed) will coexist with the shim rows.

Usage:
  source infrastructure/scripts/switch_env.sh dev   # or mock / prod
  python infrastructure/scripts/seed_reference_shim.py
"""

from __future__ import annotations

import os
import random
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from faker import Faker

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from shared.config import get_settings  # noqa: E402

SEED = 20260415

# ─────────────────────────────────────────────────────────────────────────────
# 50 real public NDCs from top-prescribed and specialty drugs.
# Format: (product_id, product_ndc, ndc_11, proprietary, generic, dosage_form)
# ─────────────────────────────────────────────────────────────────────────────
DRUGS: list[tuple[str, str, str, str, str, str, str]] = [
    # (product_id, product_ndc, ndc_11, proprietary_name, non_proprietary_name, dosage_form, route)
    # ── Statins ──────────────────────────────────────────────────────────
    ("DEMO-00071-0155", "0071-0155", "00071015523", "Lipitor", "atorvastatin calcium", "TABLET", "ORAL"),
    ("DEMO-00310-0751", "0310-0751", "00310075190", "Crestor", "rosuvastatin calcium", "TABLET", "ORAL"),
    ("DEMO-00006-0749", "0006-0749", "00006074954", "Zocor", "simvastatin", "TABLET", "ORAL"),
    ("DEMO-00071-0157", "0071-0157", "00071015723", "Lipitor", "atorvastatin calcium 20 MG", "TABLET", "ORAL"),
    # ── Diabetes ─────────────────────────────────────────────────────────
    ("DEMO-00006-0277", "0006-0277", "00006027761", "Januvia", "sitagliptin", "TABLET", "ORAL"),
    ("DEMO-00597-0152", "0597-0152", "00597015230", "Jardiance", "empagliflozin", "TABLET", "ORAL"),
    ("DEMO-00088-2220", "0088-2220", "00088222033", "Lantus", "insulin glargine", "INJECTION, SOLUTION", "SUBCUTANEOUS"),
    ("DEMO-00002-7510", "0002-7510", "00002751001", "Humalog", "insulin lispro", "INJECTION, SOLUTION", "SUBCUTANEOUS"),
    ("DEMO-00378-0451", "0378-0451", "00378045101", "Metformin HCl", "metformin hydrochloride", "TABLET", "ORAL"),
    ("DEMO-00169-2660", "0169-2660", "00169266015", "Ozempic", "semaglutide", "INJECTION, SOLUTION", "SUBCUTANEOUS"),
    # ── Blood pressure ──────────────────────────────────────────────────
    ("DEMO-29033-0010", "29033-010", "29033001001", "Lisinopril", "lisinopril", "TABLET", "ORAL"),
    ("DEMO-00378-0395", "0378-0395", "00378039501", "Amlodipine Besylate", "amlodipine besylate", "TABLET", "ORAL"),
    ("DEMO-00591-0577", "0591-0577", "00591057701", "Losartan Potassium", "losartan potassium", "TABLET", "ORAL"),
    ("DEMO-00781-1810", "0781-1810", "00781181001", "Hydrochlorothiazide", "hydrochlorothiazide", "TABLET", "ORAL"),
    ("DEMO-00378-0150", "0378-0150", "00378015001", "Metoprolol Tartrate", "metoprolol tartrate", "TABLET", "ORAL"),
    # ── Mental health ───────────────────────────────────────────────────
    ("DEMO-00781-5180", "0781-5180", "00781518001", "Zoloft", "sertraline hydrochloride", "TABLET", "ORAL"),
    ("DEMO-00456-2010", "0456-2010", "00456201063", "Lexapro", "escitalopram oxalate", "TABLET", "ORAL"),
    ("DEMO-00173-0177", "0173-0177", "00173017755", "Wellbutrin XL", "bupropion hydrochloride", "TABLET, EXTENDED RELEASE", "ORAL"),
    ("DEMO-00009-0090", "0009-0090", "00009009002", "Xanax", "alprazolam", "TABLET", "ORAL"),
    ("DEMO-00378-3855", "0378-3855", "00378385593", "Citalopram Hydrobromide", "citalopram hydrobromide", "TABLET", "ORAL"),
    # ── Pain / opioids / NSAIDs ─────────────────────────────────────────
    ("DEMO-00071-1014", "0071-1014", "00071101468", "Lyrica", "pregabalin", "CAPSULE", "ORAL"),
    ("DEMO-00378-3805", "0378-3805", "00378380501", "Gabapentin", "gabapentin", "CAPSULE", "ORAL"),
    ("DEMO-00093-0058", "0093-0058", "00093005801", "Tramadol HCl", "tramadol hydrochloride", "TABLET", "ORAL"),
    ("DEMO-50580-0488", "50580-488", "50580048852", "Advil", "ibuprofen", "TABLET, COATED", "ORAL"),
    ("DEMO-50580-0466", "50580-466", "50580046601", "Tylenol Extra Strength", "acetaminophen", "TABLET", "ORAL"),
    # ── Antibiotics ─────────────────────────────────────────────────────
    ("DEMO-00781-6153", "0781-6153", "00781615301", "Amoxicillin", "amoxicillin", "CAPSULE", "ORAL"),
    ("DEMO-00069-3060", "0069-3060", "00069306030", "Zithromax", "azithromycin", "TABLET, FILM COATED", "ORAL"),
    ("DEMO-00378-0241", "0378-0241", "00378024101", "Doxycycline Hyclate", "doxycycline hyclate", "CAPSULE", "ORAL"),
    ("DEMO-00093-3147", "0093-3147", "00093314701", "Cephalexin", "cephalexin", "CAPSULE", "ORAL"),
    ("DEMO-00009-7152", "0009-7152", "00009715202", "Cleocin", "clindamycin hydrochloride", "CAPSULE", "ORAL"),
    # ── Specialty / biologics ───────────────────────────────────────────
    ("DEMO-00074-3799", "0074-3799", "00074379902", "Humira", "adalimumab", "INJECTION, SOLUTION", "SUBCUTANEOUS"),
    ("DEMO-58406-0445", "58406-445", "58406044504", "Enbrel", "etanercept", "INJECTION, SOLUTION", "SUBCUTANEOUS"),
    ("DEMO-57894-0060", "57894-060", "57894006003", "Stelara", "ustekinumab", "INJECTION, SOLUTION", "SUBCUTANEOUS"),
    ("DEMO-00003-0894", "0003-0894", "00003089421", "Eliquis", "apixaban", "TABLET, FILM COATED", "ORAL"),
    ("DEMO-50458-0578", "50458-578", "50458057830", "Xarelto", "rivaroxaban", "TABLET, FILM COATED", "ORAL"),
    ("DEMO-00006-0117", "0006-0117", "00006011761", "Keytruda", "pembrolizumab", "INJECTION, SOLUTION, CONCENTRATE", "INTRAVENOUS"),
    ("DEMO-50242-0150", "50242-150", "50242015001", "Ocrevus", "ocrelizumab", "INJECTION, SOLUTION, CONCENTRATE", "INTRAVENOUS"),
    ("DEMO-00078-0357", "0078-0357", "00078035715", "Gleevec", "imatinib mesylate", "TABLET, FILM COATED", "ORAL"),
    # ── Top brand maintenance ───────────────────────────────────────────
    ("DEMO-00074-7068", "0074-7068", "00074706813", "Synthroid", "levothyroxine sodium", "TABLET", "ORAL"),
    ("DEMO-00186-5022", "0186-5022", "00186502228", "Nexium", "esomeprazole magnesium", "CAPSULE, DELAYED RELEASE", "ORAL"),
    ("DEMO-00006-0117S", "0006-0275", "00006027531", "Singulair", "montelukast sodium", "TABLET, CHEWABLE", "ORAL"),
    ("DEMO-00378-1810", "0378-1810", "00378181010", "Omeprazole", "omeprazole", "CAPSULE, DELAYED RELEASE", "ORAL"),
    ("DEMO-00378-1965", "0378-1965", "00378196501", "Levothyroxine Sodium", "levothyroxine sodium", "TABLET", "ORAL"),
    ("DEMO-00093-7155", "0093-7155", "00093715501", "Montelukast Sodium", "montelukast sodium", "TABLET, FILM COATED", "ORAL"),
    # ── Respiratory ─────────────────────────────────────────────────────
    ("DEMO-00173-0696", "0173-0696", "00173069620", "Advair Diskus", "fluticasone propionate; salmeterol xinafoate", "POWDER, METERED", "RESPIRATORY (INHALATION)"),
    ("DEMO-00173-0682", "0173-0682", "00173068220", "Ventolin HFA", "albuterol sulfate", "AEROSOL, METERED", "RESPIRATORY (INHALATION)"),
    ("DEMO-00310-0210", "0310-0210", "00310021039", "Symbicort", "budesonide; formoterol fumarate dihydrate", "AEROSOL, METERED", "RESPIRATORY (INHALATION)"),
    # ── Allergy / contraception / women's health ────────────────────────
    ("DEMO-00069-0070", "0069-0070", "00069007005", "Allegra", "fexofenadine hydrochloride", "TABLET, FILM COATED", "ORAL"),
    ("DEMO-00378-7211", "0378-7211", "00378721110", "Sertraline HCl", "sertraline hydrochloride", "TABLET, FILM COATED", "ORAL"),
    ("DEMO-00904-5803", "0904-5803", "00904580306", "Loratadine", "loratadine", "TABLET", "ORAL"),
]
assert len(DRUGS) == 50, f"expected 50 drugs, got {len(DRUGS)}"

# ─────────────────────────────────────────────────────────────────────────────
# 50 pharmacies — real chain DBA names + FORMAT-VALID DEMO NCPDP IDs (prefix 90).
# Real NCPDP IDs are 7 digits. The "90XXXXX" prefix marks them as synthetic.
# ─────────────────────────────────────────────────────────────────────────────
PHARMACY_CHAINS = [
    "CVS Pharmacy", "Walgreens", "Walmart Pharmacy", "Rite Aid", "Kroger Pharmacy",
    "Costco Pharmacy", "Sam's Club Pharmacy", "Target Pharmacy", "Safeway Pharmacy",
    "Publix Pharmacy", "Albertsons Pharmacy", "H-E-B Pharmacy", "Meijer Pharmacy",
    "Hy-Vee Pharmacy", "Fred Meyer Pharmacy", "Wegmans Pharmacy", "Harris Teeter Pharmacy",
    "Vons Pharmacy", "Stop & Shop Pharmacy", "ACME Markets Pharmacy", "Giant Food Pharmacy",
    "Food Lion Pharmacy", "Winn-Dixie Pharmacy", "ShopRite Pharmacy", "Price Chopper Pharmacy",
    "Tom Thumb Pharmacy", "Randalls Pharmacy", "Jewel-Osco Pharmacy", "Shaw's Pharmacy",
    "Star Market Pharmacy",
]

PHARMACY_CITIES = [
    ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"),
    ("Chicago", "IL", "60601"), ("Houston", "TX", "77001"),
    ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"), ("San Diego", "CA", "92101"),
    ("Dallas", "TX", "75201"), ("San Jose", "CA", "95101"),
    ("Austin", "TX", "73301"), ("Jacksonville", "FL", "32099"),
    ("Fort Worth", "TX", "76101"), ("Columbus", "OH", "43085"),
    ("Charlotte", "NC", "28201"), ("San Francisco", "CA", "94102"),
    ("Indianapolis", "IN", "46201"), ("Seattle", "WA", "98101"),
    ("Denver", "CO", "80201"), ("Washington", "DC", "20001"),
    ("Boston", "MA", "02101"), ("Nashville", "TN", "37201"),
    ("Detroit", "MI", "48201"), ("Portland", "OR", "97201"),
    ("Memphis", "TN", "38101"),
]


def build_pharmacies(rng: random.Random) -> list[dict]:
    out: list[dict] = []
    for i in range(50):
        chain = PHARMACY_CHAINS[i % len(PHARMACY_CHAINS)]
        city, state, zip5 = PHARMACY_CITIES[i % len(PHARMACY_CITIES)]
        store_no = str(1000 + i)
        ncpdp_id = f"90{str(10000 + i).zfill(5)}"  # 7-digit, 90 prefix
        npi = synthetic_npi(rng)
        out.append({
            "id": str(uuid.uuid4()),
            "ncpdp_provider_id": ncpdp_id,
            "legal_name": f"{chain} Store #{store_no}",
            "dba_name": chain,
            "store_number": store_no,
            "npi": npi,
            "address_line_1": f"{rng.randint(100, 9999)} Main St",
            "city": city,
            "state": state,
            "zip5": zip5,
            "phone": f"{rng.randint(2, 9)}{str(rng.randint(100000000, 999999999))[:9]}",
            "pharmacy_type_code": "01",
            "is_excluded": False,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 100 prescribers — Faker names + Luhn-valid synthetic NPIs.
# ─────────────────────────────────────────────────────────────────────────────
SPECIALTIES = [
    ("207Q00000X", "Family Medicine", "Family Medicine", "MD"),
    ("207R00000X", "Internal Medicine", "Internal Medicine", "MD"),
    ("208000000X", "Pediatrics", "Pediatrics", "MD"),
    ("207RC0000X", "Cardiovascular Disease", "Cardiology", "MD"),
    ("207RE0101X", "Endocrinology", "Endocrinology", "MD"),
    ("207RG0100X", "Gastroenterology", "Gastroenterology", "MD"),
    ("207RP1001X", "Pulmonary Disease", "Pulmonology", "MD"),
    ("2084N0400X", "Neurology", "Neurology", "MD"),
    ("2084P0800X", "Psychiatry", "Psychiatry", "MD"),
    ("363L00000X", "Nurse Practitioner", "Nurse Practitioner", "NP"),
    ("363LF0000X", "Family NP", "Nurse Practitioner", "NP"),
    ("363A00000X", "Physician Assistant", "Physician Assistant", "PA"),
    ("207V00000X", "Obstetrics & Gynecology", "OB/GYN", "MD"),
    ("207W00000X", "Ophthalmology", "Ophthalmology", "MD"),
    ("207X00000X", "Orthopaedic Surgery", "Orthopedics", "MD"),
    ("207Y00000X", "Otolaryngology", "ENT", "MD"),
    ("204C00000X", "Neuromusculoskeletal Medicine", "Osteopathic", "DO"),
    ("207RH0003X", "Hematology & Oncology", "Hem/Onc", "MD"),
    ("207RR0500X", "Rheumatology", "Rheumatology", "MD"),
    ("207RD0900X", "Diabetes", "Endocrinology", "MD"),
]

STATES = ["NY", "CA", "TX", "FL", "PA", "IL", "OH", "GA", "NC", "MI",
          "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MD", "MO", "WI"]


def luhn_check(digits: str) -> int:
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
    """Return a 10-digit NPI: 9-digit body + Luhn check over "80840" + body."""
    body = "".join(str(rng.randint(0, 9)) for _ in range(9))
    check = luhn_check("80840" + body)
    return body + str(check)


def build_prescribers(rng: random.Random, faker: Faker) -> list[dict]:
    out: list[dict] = []
    for i in range(100):
        npi = synthetic_npi(rng)
        spec = SPECIALTIES[i % len(SPECIALTIES)]
        first = faker.first_name()
        last = faker.last_name()
        cred = spec[3]
        state = STATES[i % len(STATES)]
        out.append({
            "id": str(uuid.uuid4()),
            "npi": npi,
            "entity_type": "1",
            "first_name": first,
            "last_name": last,
            "credential": cred,
            "display_name": f"{first} {last}, {cred}",
            "primary_taxonomy_code": spec[0],
            "primary_taxonomy_description": spec[1],
            "primary_specialty": spec[2],
            "practice_state": state,
            "practice_city": faker.city(),
            "practice_zip": faker.postcode()[:10],
            "practice_address_line_1": faker.street_address()[:255],
            "gender": rng.choice(["M", "F"]),
            "status": "active",
            "medicare_opt_out": False,
            "offers_telehealth": rng.random() < 0.5,
            "is_excluded": False,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Idempotent upsert SQL
# ─────────────────────────────────────────────────────────────────────────────
DRUG_INSERT = """
INSERT INTO drug_database.drugs (
  product_id, product_ndc, ndc_11, proprietary_name, non_proprietary_name,
  dosage_form_name, route_name, created_at, updated_at
) VALUES %s
ON CONFLICT (ndc_11) DO UPDATE SET
  proprietary_name      = EXCLUDED.proprietary_name,
  non_proprietary_name  = EXCLUDED.non_proprietary_name,
  dosage_form_name      = EXCLUDED.dosage_form_name,
  route_name            = EXCLUDED.route_name,
  updated_at            = EXCLUDED.updated_at
"""

PHARMACY_INSERT = """
INSERT INTO pharmacy_dir.ncpdp_pharmacies (
  id, ncpdp_provider_id, legal_name, dba_name, store_number, npi,
  address_line_1, city, state, zip5, phone, pharmacy_type_code,
  is_excluded, last_updated_at, created_at
) VALUES %s
ON CONFLICT (ncpdp_provider_id) DO UPDATE SET
  legal_name      = EXCLUDED.legal_name,
  dba_name        = EXCLUDED.dba_name,
  store_number    = EXCLUDED.store_number,
  npi             = EXCLUDED.npi,
  address_line_1  = EXCLUDED.address_line_1,
  city            = EXCLUDED.city,
  state           = EXCLUDED.state,
  zip5            = EXCLUDED.zip5,
  phone           = EXCLUDED.phone,
  last_updated_at = EXCLUDED.last_updated_at
"""

PRESCRIBER_INSERT = """
INSERT INTO prescriber_dir.prescribers (
  id, npi, entity_type, first_name, last_name, credential, display_name,
  primary_taxonomy_code, primary_taxonomy_description, primary_specialty,
  practice_state, practice_city, practice_zip, practice_address_line_1,
  gender, status, medicare_opt_out, offers_telehealth, is_excluded,
  created_at, updated_at
) VALUES %s
ON CONFLICT (npi) DO UPDATE SET
  first_name                    = EXCLUDED.first_name,
  last_name                     = EXCLUDED.last_name,
  display_name                  = EXCLUDED.display_name,
  primary_taxonomy_code         = EXCLUDED.primary_taxonomy_code,
  primary_taxonomy_description  = EXCLUDED.primary_taxonomy_description,
  primary_specialty             = EXCLUDED.primary_specialty,
  practice_state                = EXCLUDED.practice_state,
  practice_city                 = EXCLUDED.practice_city,
  updated_at                    = EXCLUDED.updated_at
"""


def main() -> int:
    settings = get_settings()
    raw_url = settings.DATABASE_URL.replace("+asyncpg", "").replace("+psycopg2", "")
    print(f"[seed] target: {raw_url.split('@')[-1]}")

    rng = random.Random(SEED)
    faker = Faker()
    Faker.seed(SEED)

    pharmacies = build_pharmacies(rng)
    prescribers = build_prescribers(rng, faker)
    now = datetime.now(timezone.utc)

    # Drug rows — 7 hand-curated columns + (created_at, updated_at)
    drug_rows = [
        (pid, pndc, ndc11, prop, nonprop, dosage, route, now, now)
        for (pid, pndc, ndc11, prop, nonprop, dosage, route) in DRUGS
    ]

    pharmacy_rows = [
        (
            p["id"], p["ncpdp_provider_id"], p["legal_name"], p["dba_name"],
            p["store_number"], p["npi"], p["address_line_1"], p["city"],
            p["state"], p["zip5"], p["phone"], p["pharmacy_type_code"],
            p["is_excluded"], now, now,
        )
        for p in pharmacies
    ]

    prescriber_rows = [
        (
            r["id"], r["npi"], r["entity_type"], r["first_name"], r["last_name"],
            r["credential"], r["display_name"], r["primary_taxonomy_code"],
            r["primary_taxonomy_description"], r["primary_specialty"],
            r["practice_state"], r["practice_city"], r["practice_zip"],
            r["practice_address_line_1"], r["gender"], r["status"],
            r["medicare_opt_out"], r["offers_telehealth"], r["is_excluded"],
            now, now,
        )
        for r in prescribers
    ]

    conn = psycopg2.connect(raw_url)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, DRUG_INSERT, drug_rows)
            print(f"[seed] drugs upserted: {len(drug_rows)}")
            psycopg2.extras.execute_values(cur, PHARMACY_INSERT, pharmacy_rows)
            print(f"[seed] pharmacies upserted: {len(pharmacy_rows)}")
            psycopg2.extras.execute_values(cur, PRESCRIBER_INSERT, prescriber_rows)
            print(f"[seed] prescribers upserted: {len(prescriber_rows)}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Write a frozen Python file the scrambler can import without a DB round-trip.
    frozen_path = REPO_ROOT / "data" / "mock" / "_reference_shim.py"
    frozen_path.parent.mkdir(parents=True, exist_ok=True)
    with frozen_path.open("w", encoding="utf-8") as f:
        f.write('"""Auto-generated by seed_reference_shim.py — do not edit by hand."""\n\n')
        f.write("# (ndc_11, proprietary_name)\n")
        f.write("DRUG_NDCS = [\n")
        for d in DRUGS:
            f.write(f"    ({d[2]!r}, {d[3]!r}),\n")
        f.write("]\n\n")
        f.write("# (ncpdp_provider_id, dba_name, pharmacy_npi)\n")
        f.write("PHARMACIES = [\n")
        for p in pharmacies:
            f.write(f"    ({p['ncpdp_provider_id']!r}, {p['dba_name']!r}, {p['npi']!r}),\n")
        f.write("]\n\n")
        f.write("# Convenience: just the pharmacy NPIs, in the same order.\n")
        f.write("PHARMACY_NPIS = [p[2] for p in PHARMACIES]\n\n")
        f.write("# Prescriber NPIs — Luhn-valid synthetic, 10 chars\n")
        f.write("PRESCRIBER_NPIS = [\n")
        for r in prescribers:
            f.write(f"    {r['npi']!r},\n")
        f.write("]\n")
    print(f"[seed] wrote {frozen_path}")

    print("[seed] DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
