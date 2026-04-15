"""Fictional fixtures for the InfinityRx sales-demo tenant.

All names, BINs, and NDC mappings are sterilized — no real manufacturer,
program, or brand names are referenced anywhere. The drug→NDC mappings
point at REAL NDCs in the shared drug database (whatever is seeded),
so the pricing/therapeutic data is realistic while brand names are
fictional.

This module is pure data; seeding logic lives in ``setup_demo.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class DemoManufacturer:
    slug: str
    name: str
    therapeutic_focus: str
    programs: list["DemoProgram"] = field(default_factory=list)


@dataclass(frozen=True)
class DemoProgram:
    slug: str
    name: str
    bin: str
    pcn: str
    group_id: str
    program_type: str  # copay | voucher | bridge | free_goods | debit_card | pap
    notes: str = ""


@dataclass(frozen=True)
class DemoDrug:
    demo_name: str
    therapeutic_class: str
    manufacturer_slug: str
    sample_ndc: str  # a real NDC pattern that matches the therapeutic class


# Fictional BIN range chosen to avoid real BIN collisions — 620xxx band is
# largely unassigned in the real NCPDP directory.
DEMO_MANUFACTURERS: tuple[DemoManufacturer, ...] = (
    DemoManufacturer(
        slug="zenara",
        name="Zenara Therapeutics",
        therapeutic_focus="CNS / Neuroscience",
        programs=[
            DemoProgram("zenara-copay", "Zenara Copay Assistance", "620001", "ZENCP", "ZENARA01", "copay"),
            DemoProgram("zenara-voucher", "Zenara Voucher Program", "620002", "ZENVC", "ZENARA02", "voucher"),
            DemoProgram("zenara-bridge", "Zenara Bridge Program", "620003", "ZENBR", "ZENARA03", "bridge"),
        ],
    ),
    DemoManufacturer(
        slug="meridian",
        name="Meridian BioSciences",
        therapeutic_focus="Rare Disease",
        programs=[
            DemoProgram("meridian-free-goods", "Meridian Free Goods", "620010", "MERFG", "MERIDIAN01", "free_goods"),
            DemoProgram("meridian-copay", "Meridian Copay", "620011", "MERCP", "MERIDIAN02", "copay"),
        ],
    ),
    DemoManufacturer(
        slug="crestview",
        name="Crestview Pharma",
        therapeutic_focus="Dermatology",
        programs=[
            DemoProgram("crestview-copay", "Crestview Copay Card", "620020", "CRECP", "CRESTVIEW01", "copay"),
        ],
    ),
    DemoManufacturer(
        slug="helios",
        name="Helios Health",
        therapeutic_focus="Oncology",
        programs=[
            DemoProgram("helios-copay", "Helios Copay Assistance", "620030", "HELCP", "HELIOS01", "copay"),
            DemoProgram("helios-pap", "Helios PAP", "620031", "HELPAP", "HELIOS02", "pap"),
        ],
    ),
    DemoManufacturer(
        slug="pinnacle",
        name="Pinnacle Medicines",
        therapeutic_focus="Cardiovascular",
        programs=[
            DemoProgram("pinnacle-copay", "Pinnacle Copay Card", "620040", "PINCP", "PINNACLE01", "copay"),
            DemoProgram("pinnacle-debit", "Pinnacle Debit Card", "620041", "PINDB", "PINNACLE02", "debit_card"),
        ],
    ),
    DemoManufacturer(
        slug="orion",
        name="Orion Therapeutics",
        therapeutic_focus="Immunology",
        programs=[
            DemoProgram("orion-specialty", "Orion Specialty Copay", "620050", "ORICP", "ORION01", "copay"),
        ],
    ),
)


# Fictional brand name → real NDC sample. The real NDC is used to exercise
# real pricing/interaction data; brand name shown in the demo UI is fictional.
# NDCs below are representative 11-digit placeholders; the setup script
# picks real NDCs from the live drug table when available and falls back
# to these placeholders otherwise.
DEMO_DRUGS: tuple[DemoDrug, ...] = (
    DemoDrug("Neuraza XR", "CNS - antidepressant", "zenara", "00378123456"),
    DemoDrug("Zenalift", "CNS - stimulant", "zenara", "00378123457"),
    DemoDrug("Clarivos", "CNS - antipsychotic", "zenara", "00378123458"),
    DemoDrug("Rarevex", "Enzyme replacement", "meridian", "00378223456"),
    DemoDrug("Dermaclear", "Topical retinoid", "crestview", "00378323456"),
    DemoDrug("SkinShield Pro", "Topical immunomodulator", "crestview", "00378323457"),
    DemoDrug("Oncoguard", "Targeted oncology", "helios", "00378423456"),
    DemoDrug("CardioSync", "Antihypertensive", "pinnacle", "00378523456"),
    DemoDrug("PulseRx", "Anticoagulant", "pinnacle", "00378523457"),
    DemoDrug("ImmunoVex", "TNF inhibitor", "orion", "00378623456"),
)


# Average claim amount ranges per therapeutic class — drives realistic
# distribution when the claim generator picks a drug.
AMOUNT_BY_CLASS: dict[str, tuple[Decimal, Decimal]] = {
    "CNS - antidepressant": (Decimal("45.00"), Decimal("180.00")),
    "CNS - stimulant": (Decimal("80.00"), Decimal("350.00")),
    "CNS - antipsychotic": (Decimal("120.00"), Decimal("650.00")),
    "Enzyme replacement": (Decimal("2500.00"), Decimal("15000.00")),  # specialty
    "Topical retinoid": (Decimal("15.00"), Decimal("95.00")),
    "Topical immunomodulator": (Decimal("120.00"), Decimal("480.00")),
    "Targeted oncology": (Decimal("1800.00"), Decimal("12000.00")),  # specialty
    "Antihypertensive": (Decimal("18.00"), Decimal("75.00")),
    "Anticoagulant": (Decimal("45.00"), Decimal("220.00")),
    "TNF inhibitor": (Decimal("2200.00"), Decimal("8500.00")),  # specialty
}


DEMO_TENANT_SLUG = "infinityrx-demo"
DEMO_TENANT_NAME = "InfinityRx Demo"
DEMO_ADMIN_EMAIL = "demo@infinityrx.com"
DEMO_ADMIN_DISPLAY_NAME = "Demo Admin"
