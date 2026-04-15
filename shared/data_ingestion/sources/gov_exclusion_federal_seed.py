"""Federal government program BIN/PCN seed data.

Seeds all known stable federal program BINs into shared.government_program_bins.
This is idempotent — running it twice produces the same row set.

Sources:
  - TRICARE: https://www.tricare.mil/FAQs/Pharmacy/PharmProg_Bin (Express Scripts)
  - Medicare Part D: CMS PDP landscape files, PBM provider manuals
  - VA: VA Pharmacy Benefits Management (PBM) formulary documentation
  - FEP: BCBS Federal Employee Program via CVS Caremark
  - IHS: Indian Health Service pharmacy program documentation
  - CHAMPVA: VA CHAMPVA pharmacy benefit via OptumRx

BINs marked MEDIUM confidence indicate the BIN is also used for commercial
plans; the PCN distinguishes government vs commercial. BIN-only rows with
confidence=MEDIUM must be treated as REVIEW by the copay eligibility gate.

LESSON-004: \\A...\\Z anchors on all regex.
LESSON-011: Global reference data — no tenant_id.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from shared.models.gov_exclusion_tables import GovernmentProgramBin

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Federal seed records
# Each record maps to GovernmentProgramBin columns.
# pcn=None means the row matches any PCN for that BIN (BIN-only).
# ---------------------------------------------------------------------------

_FEDERAL_SEEDS: list[dict[str, Any]] = [
    # ── TRICARE (Express Scripts / ESI) ────────────────────────────────────
    # Source: TRICARE Pharmacy Program, https://www.tricare.mil/FAQs/Pharmacy/PharmProg_Bin
    {
        "bin": "003858",
        "pcn": "A4",
        "group_number": "DODA",
        "plan_type": "TRICARE",
        "plan_subtype": "Standard/Select/Prime",
        "pbm_name": "Express Scripts",
        "plan_name": "TRICARE Pharmacy Program",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "TRICARE Pharmacy Program — tricare.mil/FAQs/Pharmacy/PharmProg_Bin",
        "notes": "Express Scripts manages TRICARE retail/mail pharmacy benefit",
    },
    {
        "bin": "003858",
        "pcn": "SC",
        "group_number": "DODA",
        "plan_type": "TRICARE",
        "plan_subtype": "TRICARE For Life (Medicare Part D wrap)",
        "pbm_name": "Express Scripts",
        "plan_name": "TRICARE For Life",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "TRICARE Pharmacy Program — tricare.mil/FAQs/Pharmacy/PharmProg_Bin",
        "notes": "TRICARE For Life: Medicare Part D supplemental; PCN=SC distinguishes from commercial ESI",
    },
    # BIN 003858 without PCN — MEDIUM because ESI also uses this BIN commercially
    {
        "bin": "003858",
        "pcn": None,
        "group_number": None,
        "plan_type": "TRICARE",
        "plan_subtype": None,
        "pbm_name": "Express Scripts",
        "plan_name": None,
        "mco_name": None,
        "state": None,
        "confidence": "MEDIUM",
        "source": "Express Scripts provider manual — BIN shared with commercial plans",
        "notes": "Also used for ESI commercial plans — PCN distinguishes (A4/SC=TRICARE; others=commercial). Requires REVIEW.",
    },

    # ── Medicare Part D — CVS Caremark / SilverScript ──────────────────────
    # CVS Caremark PDP / SilverScript
    # Source: CMS Medicare Part D landscape, CVS Caremark pharmacy manual
    {
        "bin": "004336",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "PDP / Medicare Advantage Part D",
        "pbm_name": "CVS Caremark",
        "plan_name": "CVS Caremark Medicare Part D / SilverScript",
        "mco_name": None,
        "state": None,
        "confidence": "MEDIUM",
        "source": "CVS Caremark pharmacy provider manual; CMS Part D landscape",
        "notes": "BIN 004336 shared with CVS commercial plans — PCN distinguishes. Medicare PCNs typically ADV, STD variants. Requires REVIEW without PCN.",
    },
    {
        "bin": "004336",
        "pcn": "ADV",
        "group_number": None,
        "plan_type": "MEDICARE_ADVANTAGE",
        "plan_subtype": "Medicare Advantage Part D (MA-PD)",
        "pbm_name": "CVS Caremark",
        "plan_name": "Aetna Medicare Advantage Part D via CVS Caremark",
        "mco_name": "Aetna",
        "state": None,
        "confidence": "HIGH",
        "source": "CVS Caremark pharmacy provider manual",
        "notes": "PCN=ADV identifies Aetna MA-PD plans processed by CVS Caremark",
    },
    # SilverScript standalone PDP BINs
    {
        "bin": "015581",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "SilverScript PDP",
        "pbm_name": "CVS Caremark",
        "plan_name": "SilverScript Insurance Company PDP",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "CMS Medicare Part D landscape file; SilverScript plan data",
        "notes": "SilverScript-specific BIN — dedicated Medicare Part D, no commercial overlap",
    },

    # ── Medicare Part D — OptumRx ───────────────────────────────────────────
    # Source: OptumRx pharmacy provider manual; CMS Part D landscape
    {
        "bin": "610494",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "PDP / Medicare Advantage Part D",
        "pbm_name": "OptumRx",
        "plan_name": "UnitedHealthcare/AARP Medicare Rx via OptumRx",
        "mco_name": "UnitedHealthcare",
        "state": None,
        "confidence": "HIGH",
        "source": "OptumRx pharmacy provider manual; CMS Part D landscape",
        "notes": "Primary Medicare Part D BIN for UHC/AARP plans via OptumRx",
    },
    {
        "bin": "610011",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "PDP / Medicare Advantage Part D",
        "pbm_name": "OptumRx",
        "plan_name": "OptumRx Medicare Plans",
        "mco_name": "UnitedHealthcare",
        "state": None,
        "confidence": "HIGH",
        "source": "OptumRx pharmacy provider manual; CMS Part D landscape",
        "notes": "Secondary Medicare Part D BIN for OptumRx-processed UHC plans",
    },

    # ── Medicare Part D — Aetna Medicare ───────────────────────────────────
    # Source: Aetna Medicare pharmacy manual; CMS Part D landscape
    {
        "bin": "610502",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_ADVANTAGE",
        "plan_subtype": "Medicare Advantage Part D (MA-PD)",
        "pbm_name": "CVS Caremark",
        "plan_name": "Aetna Medicare Advantage",
        "mco_name": "Aetna",
        "state": None,
        "confidence": "HIGH",
        "source": "Aetna Medicare pharmacy manual; CMS MA landscape",
        "notes": "Aetna Medicare Advantage Part D processed via CVS Caremark",
    },

    # ── Medicare Part D — Humana / CenterWell ──────────────────────────────
    # Source: Humana pharmacy provider manual; CMS Part D landscape
    {
        "bin": "015581",
        "pcn": "HU01",
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "Humana PDP",
        "pbm_name": "Humana Pharmacy",
        "plan_name": "Humana Medicare Part D PDP",
        "mco_name": "Humana",
        "state": None,
        "confidence": "HIGH",
        "source": "Humana pharmacy provider manual",
        "notes": "Humana PDP processed through CenterWell Pharmacy (formerly Humana Pharmacy)",
    },
    {
        "bin": "610262",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_ADVANTAGE",
        "plan_subtype": "Humana Medicare Advantage Part D",
        "pbm_name": "Humana Pharmacy",
        "plan_name": "Humana Medicare Advantage",
        "mco_name": "Humana",
        "state": None,
        "confidence": "HIGH",
        "source": "Humana pharmacy provider manual; CMS MA landscape",
        "notes": "Humana MA-PD BIN — dedicated Medicare Advantage Part D",
    },

    # ── Medicare Part D — Cigna Medicare ───────────────────────────────────
    # Source: Cigna pharmacy provider manual; CMS Part D landscape
    {
        "bin": "015581",
        "pcn": "CI01",
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "Cigna PDP",
        "pbm_name": "Express Scripts",
        "plan_name": "Cigna Medicare Part D PDP",
        "mco_name": "Cigna",
        "state": None,
        "confidence": "HIGH",
        "source": "Cigna pharmacy provider manual; ESI provider documentation",
        "notes": "Cigna PDP via Express Scripts — PCN CI01 distinguishes from other ESI plans",
    },

    # ── Medicare Part D — WellCare Medicare ────────────────────────────────
    # Source: WellCare pharmacy benefit manual; CMS Part D landscape
    {
        "bin": "610576",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "WellCare PDP",
        "pbm_name": "MedImpact",
        "plan_name": "WellCare Value Script / Classic / Extra PDP",
        "mco_name": "WellCare / Centene",
        "state": None,
        "confidence": "HIGH",
        "source": "WellCare Medicare pharmacy benefit manual; CMS Part D landscape",
        "notes": "WellCare Medicare PDPs processed through MedImpact",
    },

    # ── Medicare Part D — EnvisionRx ───────────────────────────────────────
    # Source: CMS Part D landscape; EnvisionRx provider documentation
    {
        "bin": "015342",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "EnvisionRx PDP",
        "pbm_name": "EnvisionRx",
        "plan_name": "EnvisionRx Options Medicare PDP",
        "mco_name": "Rite Aid / EnvisionRx",
        "state": None,
        "confidence": "HIGH",
        "source": "EnvisionRx provider documentation; CMS Part D landscape",
        "notes": "EnvisionRx Medicare Part D PDP (acquired by Rite Aid)",
    },
    {
        "bin": "016473",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "EnvisionRx PDP",
        "pbm_name": "EnvisionRx",
        "plan_name": "EnvisionRx Medicare PDP",
        "mco_name": "Rite Aid / EnvisionRx",
        "state": None,
        "confidence": "HIGH",
        "source": "EnvisionRx provider documentation; CMS Part D landscape",
        "notes": "EnvisionRx Medicare Part D BIN (secondary)",
    },
    {
        "bin": "017134",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "EnvisionRx PDP",
        "pbm_name": "EnvisionRx",
        "plan_name": "EnvisionRx Medicare PDP",
        "mco_name": "Rite Aid / EnvisionRx",
        "state": None,
        "confidence": "HIGH",
        "source": "EnvisionRx provider documentation; CMS Part D landscape",
        "notes": "EnvisionRx Medicare Part D BIN (tertiary)",
    },

    # ── Medicare Part D — Navitus Health Solutions ──────────────────────────
    # Source: Navitus pharmacy provider manual; CMS Part D landscape
    {
        "bin": "610602",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "Navitus Medicare PDP",
        "pbm_name": "Navitus Health Solutions",
        "plan_name": "Navitus MedicareRx PDP / Dean Health/SSM Medicare",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "Navitus pharmacy provider manual; CMS Part D landscape",
        "notes": "Navitus Medicare Part D dedicated BIN",
    },

    # ── Medicare Part D — Prime Therapeutics ───────────────────────────────
    # Source: Prime Therapeutics pharmacy provider manual; CMS Part D landscape
    {
        "bin": "610524",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "Prime Therapeutics Medicare PDP/MA-PD",
        "pbm_name": "Prime Therapeutics",
        "plan_name": "BCBS Medicare Part D via Prime Therapeutics",
        "mco_name": "Blue Cross Blue Shield Plans",
        "state": None,
        "confidence": "HIGH",
        "source": "Prime Therapeutics pharmacy provider manual; CMS Part D landscape",
        "notes": "Prime Therapeutics Medicare Part D — services various BCBS Medicare plans",
    },

    # ── Medicare Part D — MedImpact ────────────────────────────────────────
    # Source: MedImpact pharmacy provider manual; CMS Part D landscape
    {
        "bin": "610649",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "MedImpact Medicare PDP/MA-PD",
        "pbm_name": "MedImpact",
        "plan_name": "MedImpact Medicare Part D",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "MedImpact pharmacy provider manual; CMS Part D landscape",
        "notes": "MedImpact Medicare Part D dedicated BIN",
    },

    # ── Medicare Part D — Elixir / RxElite ────────────────────────────────
    # Source: Elixir pharmacy provider manual; CMS Part D landscape
    {
        "bin": "610660",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "Elixir PDP",
        "pbm_name": "Elixir Insurance / RxElite",
        "plan_name": "Elixir Medicare Part D PDP",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "Elixir pharmacy provider manual; CMS Part D landscape",
        "notes": "Elixir Insurance (formerly Universal American) Medicare Part D",
    },

    # ── Medicare Part D — Capital Rx ───────────────────────────────────────
    # Source: Capital Rx provider manual; CMS Part D landscape
    {
        "bin": "020099",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "Capital Rx Medicare PDP/MA-PD",
        "pbm_name": "Capital Rx",
        "plan_name": "Capital Rx Medicare Part D",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "Capital Rx pharmacy provider manual; CMS Part D landscape",
        "notes": "Capital Rx Medicare Part D BIN",
    },

    # ── Medicare Part D — Cigna-HealthSpring / Evernorth ───────────────────
    {
        "bin": "610783",
        "pcn": None,
        "group_number": None,
        "plan_type": "MEDICARE_ADVANTAGE",
        "plan_subtype": "Cigna Medicare Advantage Part D",
        "pbm_name": "Evernorth (Express Scripts subsidiary)",
        "plan_name": "Cigna-HealthSpring Medicare Advantage",
        "mco_name": "Cigna",
        "state": None,
        "confidence": "HIGH",
        "source": "Cigna Medicare pharmacy manual; Evernorth provider documentation",
        "notes": "Cigna MA-PD plans via Evernorth/ESI PBM",
    },

    # ── VA — Community Care / VA CMOP ──────────────────────────────────────
    # Source: VA Pharmacy Benefits Management documentation
    # VA Community Care Network via OptumRx (VISN regions)
    {
        "bin": "610494",
        "pcn": "VA",
        "group_number": None,
        "plan_type": "VA",
        "plan_subtype": "VA Community Care Network",
        "pbm_name": "OptumRx",
        "plan_name": "VA Community Care Network (CCN) Pharmacy",
        "mco_name": "Optum / UHC",
        "state": None,
        "confidence": "HIGH",
        "source": "VA Pharmacy Benefits Management; OptumRx VA CCN provider guide",
        "notes": "VA Community Care Network pharmacy benefit via OptumRx; PCN=VA distinguishes from commercial OptumRx",
    },
    {
        "bin": "610011",
        "pcn": "VA",
        "group_number": None,
        "plan_type": "VA",
        "plan_subtype": "VA Community Care Network",
        "pbm_name": "OptumRx",
        "plan_name": "VA Community Care Network (CCN) Pharmacy",
        "mco_name": "Optum / UHC",
        "state": None,
        "confidence": "HIGH",
        "source": "VA Pharmacy Benefits Management; OptumRx VA CCN provider guide",
        "notes": "VA Community Care Network — secondary OptumRx BIN; PCN=VA",
    },
    {
        "bin": "003858",
        "pcn": "VA",
        "group_number": None,
        "plan_type": "VA",
        "plan_subtype": "VA Community Care (legacy ESI)",
        "pbm_name": "Express Scripts",
        "plan_name": "VA Community Care Pharmacy (pre-CCN transition)",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "VA Pharmacy Benefits Management; ESI VA provider guide",
        "notes": "Legacy VA ESI BIN prior to CCN transition; may still appear on claims",
    },

    # ── FEP — BCBS Federal Employee Program ────────────────────────────────
    # Source: BCBS Federal Employee Program pharmacy benefit manual (CVS Caremark)
    {
        "bin": "004336",
        "pcn": "FEP",
        "group_number": None,
        "plan_type": "FEP",
        "plan_subtype": "BCBS Federal Employee Program",
        "pbm_name": "CVS Caremark",
        "plan_name": "BCBS Federal Employee Program (FEP) Blue Cross Blue Shield",
        "mco_name": "Blue Cross Blue Shield Association",
        "state": None,
        "confidence": "HIGH",
        "source": "BCBS FEP pharmacy benefit manual; CVS Caremark FEP provider guide",
        "notes": "FEP is a federal government health benefit under FEHB; PCN=FEP uniquely identifies",
    },
    {
        "bin": "610502",
        "pcn": "FEP",
        "group_number": None,
        "plan_type": "FEP",
        "plan_subtype": "BCBS FEP Basic Option",
        "pbm_name": "CVS Caremark",
        "plan_name": "BCBS FEP Basic Option (pharmacy via CVS Caremark)",
        "mco_name": "Blue Cross Blue Shield Association",
        "state": None,
        "confidence": "HIGH",
        "source": "BCBS FEP pharmacy benefit manual",
        "notes": "FEP Basic Option — separate BIN from Standard Option",
    },

    # ── IHS — Indian Health Service ────────────────────────────────────────
    # Source: IHS Pharmacy Program documentation; CMS IHS guidance
    {
        "bin": "610097",
        "pcn": None,
        "group_number": None,
        "plan_type": "IHS",
        "plan_subtype": "Indian Health Service",
        "pbm_name": "IHS / Tribal / Urban Indian Organization",
        "plan_name": "Indian Health Service Pharmacy Program",
        "mco_name": None,
        "state": None,
        "confidence": "HIGH",
        "source": "IHS Pharmacy Program documentation; CMS IHS guidance",
        "notes": "IHS pharmacy benefit for eligible American Indian/Alaska Native beneficiaries",
    },

    # ── CHAMPVA ─────────────────────────────────────────────────────────────
    # Source: VA CHAMPVA pharmacy benefit via OptumRx (HAC)
    {
        "bin": "610494",
        "pcn": "CHAMP",
        "group_number": None,
        "plan_type": "CHAMPVA",
        "plan_subtype": "CHAMPVA Pharmacy Benefit",
        "pbm_name": "OptumRx",
        "plan_name": "CHAMPVA In-house Treatment Initiative (CITI) / OptumRx",
        "mco_name": "Optum",
        "state": None,
        "confidence": "HIGH",
        "source": "VA CHAMPVA pharmacy benefit documentation; OptumRx CHAMPVA guide",
        "notes": "CHAMPVA = Civilian Health and Medical Program of the Department of Veterans Affairs; PCN=CHAMP",
    },

    # ── Medicare Low Income Subsidy (LIS/Extra Help) — generic OCC marker ──
    # OCC code 13 = Medicare Part D; handled as OCC fallback in service,
    # but also seed a reminder row so operators see it in the table
    {
        "bin": "999999",
        "pcn": "LIS",
        "group_number": None,
        "plan_type": "MEDICARE_PART_D",
        "plan_subtype": "Low Income Subsidy (LIS/Extra Help) — OCC fallback marker",
        "pbm_name": None,
        "plan_name": "Medicare Low Income Subsidy (Extra Help)",
        "mco_name": None,
        "state": None,
        "confidence": "LOW",
        "source": "CMS Medicare LIS documentation; OCC code 13 = Medicare Part D",
        "notes": (
            "Placeholder row: OCC=13 on a claim indicates Medicare Part D regardless of BIN. "
            "The GovernmentExclusionService OCC fallback covers this without BIN matching."
        ),
    },
]


def seed_federal_programs(db: Session) -> dict[str, int]:
    """Idempotent seed of federal government program BINs.

    Returns dict with 'inserted' and 'updated' counts.
    """
    inserted = 0
    updated = 0
    now = datetime.now(UTC)

    for record in _FEDERAL_SEEDS:
        try:
            existing = (
                db.query(GovernmentProgramBin)
                .filter(
                    GovernmentProgramBin.bin == record["bin"],
                    GovernmentProgramBin.pcn == record.get("pcn"),
                    GovernmentProgramBin.group_number == record.get("group_number"),
                )
                .first()
            )

            if existing:
                for k, v in record.items():
                    setattr(existing, k, v)
                existing.government_flag = True
                existing.updated_at = now
                updated += 1
            else:
                entry = GovernmentProgramBin(
                    id=uuid.uuid4(),
                    government_flag=True,
                    created_at=now,
                    updated_at=now,
                    **record,
                )
                db.add(entry)
                inserted += 1

        except Exception as exc:
            logger.error(
                "Federal seed row failed",
                extra={
                    "gov_excl_bin": record.get("bin"),
                    "gov_excl_pcn": record.get("pcn"),
                    "gov_excl_error": str(exc)[:300],
                },
            )
            raise

    db.commit()

    logger.info(
        "Federal government program BIN seed complete",
        extra={
            "gov_excl_inserted": inserted,
            "gov_excl_updated": updated,
            "gov_excl_total": inserted + updated,
        },
    )
    return {"inserted": inserted, "updated": updated}


__all__ = ["seed_federal_programs", "_FEDERAL_SEEDS"]
