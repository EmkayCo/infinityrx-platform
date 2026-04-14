"""NUCC Health Care Provider Taxonomy Code reference service.

Contains a curated subset of the NUCC taxonomy set covering the most
common prescriber, pharmacy, and hospital taxonomy codes.

In production the full NUCC taxonomy CSV (updated twice yearly) is loaded
into the taxonomy_codes table; this service provides an in-memory cache
of the reference data for validation and classification.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaxonomyEntry:
    code: str
    display_name: str
    classification: str
    specialization: str | None
    simplified_specialty: str | None
    is_prescriber: bool
    is_pharmacy: bool
    is_hospital: bool


# Representative NUCC taxonomy code set.
# Full production set has ~900 codes; this covers the most common prescribers,
# NPs, PAs, pharmacies, hospitals, and other key providers.
_TAXONOMY_DATA: list[tuple] = [
    # (code, display_name, classification, specialization, simplified_specialty, is_prescriber, is_pharmacy, is_hospital)
    # --- Allopathic & Osteopathic Physicians ---
    ("207K00000X", "Allergy & Immunology", "Allopathic & Osteopathic Physicians", "Allergy & Immunology", "allergy and immunology", True, False, False),
    ("207L00000X", "Anesthesiology", "Allopathic & Osteopathic Physicians", None, "anesthesiology", True, False, False),
    ("207P00000X", "Emergency Medicine", "Allopathic & Osteopathic Physicians", None, "emergency medicine", True, False, False),
    ("207Q00000X", "Family Medicine", "Allopathic & Osteopathic Physicians", None, "family medicine", True, False, False),
    ("207R00000X", "Internal Medicine", "Allopathic & Osteopathic Physicians", None, "internal medicine", True, False, False),
    ("207T00000X", "Neurological Surgery", "Allopathic & Osteopathic Physicians", None, "neurological surgery", True, False, False),
    ("207U00000X", "Nuclear Medicine", "Allopathic & Osteopathic Physicians", None, "nuclear medicine", True, False, False),
    ("207V00000X", "Obstetrics & Gynecology", "Allopathic & Osteopathic Physicians", None, "obstetrics and gynecology", True, False, False),
    ("207W00000X", "Ophthalmology", "Allopathic & Osteopathic Physicians", None, "ophthalmology", True, False, False),
    ("207X00000X", "Orthopedic Surgery", "Allopathic & Osteopathic Physicians", None, "orthopedic surgery", True, False, False),
    ("207Y00000X", "Otolaryngology", "Allopathic & Osteopathic Physicians", None, "otolaryngology", True, False, False),
    ("207ZP0102X", "Pathology", "Allopathic & Osteopathic Physicians", "Anatomic & Clinical Pathology", "pathology", True, False, False),
    ("208000000X", "Pediatrics", "Allopathic & Osteopathic Physicians", None, "pediatrics", True, False, False),
    ("208100000X", "Physical Medicine & Rehabilitation", "Allopathic & Osteopathic Physicians", None, "physical medicine and rehabilitation", True, False, False),
    ("208600000X", "Surgery", "Allopathic & Osteopathic Physicians", None, "surgery", True, False, False),
    ("208800000X", "Urology", "Allopathic & Osteopathic Physicians", None, "urology", True, False, False),
    ("208C00000X", "Colon & Rectal Surgery", "Allopathic & Osteopathic Physicians", None, "colon and rectal surgery", True, False, False),
    ("208D00000X", "General Practice", "Allopathic & Osteopathic Physicians", None, "general practice", True, False, False),
    ("208G00000X", "Thoracic Surgery", "Allopathic & Osteopathic Physicians", None, "thoracic surgery", True, False, False),
    ("208M00000X", "Hospitalist", "Allopathic & Osteopathic Physicians", None, "hospitalist", True, False, False),
    ("208VP0014X", "Psychiatry & Neurology", "Allopathic & Osteopathic Physicians", "Psychiatry", "psychiatry", True, False, False),
    ("2084P0800X", "Psychiatry & Neurology", "Allopathic & Osteopathic Physicians", "Psychiatry", "psychiatry", True, False, False),
    ("2084N0400X", "Neurology", "Allopathic & Osteopathic Physicians", "Neurology", "neurology", True, False, False),
    ("207N00000X", "Dermatology", "Allopathic & Osteopathic Physicians", None, "dermatology", True, False, False),
    ("207RC0000X", "Cardiovascular Disease", "Allopathic & Osteopathic Physicians", "Cardiovascular Disease", "cardiology", True, False, False),
    ("207RG0100X", "Gastroenterology", "Allopathic & Osteopathic Physicians", "Gastroenterology", "gastroenterology", True, False, False),
    ("207RH0000X", "Hematology", "Allopathic & Osteopathic Physicians", "Hematology", "hematology", True, False, False),
    ("207RI0200X", "Infectious Disease", "Allopathic & Osteopathic Physicians", "Infectious Disease", "infectious disease", True, False, False),
    ("207RN0300X", "Nephrology", "Allopathic & Osteopathic Physicians", "Nephrology", "nephrology", True, False, False),
    ("207RP1001X", "Pulmonary Disease", "Allopathic & Osteopathic Physicians", "Pulmonary Disease", "pulmonology", True, False, False),
    ("207RR0500X", "Rheumatology", "Allopathic & Osteopathic Physicians", "Rheumatology", "rheumatology", True, False, False),
    ("207RE0101X", "Endocrinology", "Allopathic & Osteopathic Physicians", "Endocrinology, Diabetes & Metabolism", "endocrinology", True, False, False),
    ("207RO0200X", "Oncology", "Allopathic & Osteopathic Physicians", "Medical Oncology", "oncology", True, False, False),
    # --- Osteopathic ---
    ("204D00000X", "Osteopathic - General Practice", "Allopathic & Osteopathic Physicians", None, "general practice", True, False, False),
    # --- Advanced Practice Nursing ---
    ("363L00000X", "Nurse Practitioner", "Advanced Practice Nursing Providers", None, "nurse practitioner", True, False, False),
    ("363LA2200X", "Nurse Practitioner - Adult Health", "Advanced Practice Nursing Providers", "Adult Health", "nurse practitioner", True, False, False),
    ("363LF0000X", "Nurse Practitioner - Family", "Advanced Practice Nursing Providers", "Family", "nurse practitioner", True, False, False),
    ("363LG0600X", "Nurse Practitioner - Gerontology", "Advanced Practice Nursing Providers", "Gerontology", "nurse practitioner", True, False, False),
    ("363LN0000X", "Nurse Practitioner - Neonatal", "Advanced Practice Nursing Providers", "Neonatal", "nurse practitioner", True, False, False),
    ("363LP0200X", "Nurse Practitioner - Pediatrics", "Advanced Practice Nursing Providers", "Pediatrics", "nurse practitioner", True, False, False),
    ("363LP2300X", "Nurse Practitioner - Primary Care", "Advanced Practice Nursing Providers", "Primary Care", "nurse practitioner", True, False, False),
    ("363LS0200X", "Nurse Practitioner - School", "Advanced Practice Nursing Providers", "School", "nurse practitioner", True, False, False),
    ("363LW0102X", "Nurse Practitioner - Women's Health", "Advanced Practice Nursing Providers", "Women's Health", "nurse practitioner", True, False, False),
    ("363LX0001X", "Nurse Practitioner - Obstetrics & Gynecology", "Advanced Practice Nursing Providers", "Obstetrics & Gynecology", "nurse practitioner", True, False, False),
    # --- Physician Assistant ---
    ("363A00000X", "Physician Assistant", "Physician Assistants & Advanced Practice Nursing Providers", None, "physician assistant", True, False, False),
    # --- Certified Registered Nurse Anesthetist ---
    ("367500000X", "CRNA", "Nursing Service Providers", None, "nurse anesthetist", True, False, False),
    # --- Dentists ---
    ("122300000X", "Dentist", "Dental Providers", None, "dentist", True, False, False),
    ("1223G0001X", "Dentist - General Practice", "Dental Providers", "General Practice", "dentist", True, False, False),
    # --- Optometry ---
    ("152W00000X", "Optometrist", "Eye and Vision Services Providers", None, "optometrist", True, False, False),
    # --- Podiatry ---
    ("213E00000X", "Podiatrist", "Podiatric Medicine & Surgery Service Providers", None, "podiatrist", True, False, False),
    # --- Pharmacy ---
    ("3336C0003X", "Community/Retail Pharmacy", "Pharmacy Service Providers", "Community/Retail Pharmacy", "community pharmacy", False, True, False),
    ("3336C0004X", "Community/Retail Pharmacy", "Pharmacy Service Providers", "Community/Retail Pharmacy", "community pharmacy", False, True, False),
    ("3336I0012X", "Institutional Pharmacy", "Pharmacy Service Providers", "Institutional Pharmacy", "institutional pharmacy", False, True, False),
    ("3336L0003X", "Long Term Care Pharmacy", "Pharmacy Service Providers", "Long Term Care Pharmacy", "long term care pharmacy", False, True, False),
    ("3336M0002X", "Mail Order Pharmacy", "Pharmacy Service Providers", "Mail Order Pharmacy", "mail order pharmacy", False, True, False),
    ("3336S0011X", "Specialty Pharmacy", "Pharmacy Service Providers", "Specialty Pharmacy", "specialty pharmacy", False, True, False),
    ("3336H0001X", "Home Infusion Therapy Pharmacy", "Pharmacy Service Providers", "Home Infusion Therapy Pharmacy", "home infusion pharmacy", False, True, False),
    # --- Hospitals ---
    ("282N00000X", "General Acute Care Hospital", "Hospitals", None, "hospital", False, False, True),
    ("282NR1301X", "Rural Acute Care Hospital", "Hospitals", "Rural", "hospital", False, False, True),
    ("282NC2000X", "Critical Access Hospital", "Hospitals", "Critical Access", "hospital", False, False, True),
    ("2865M2000X", "Military Hospital", "Hospitals", "Military", "hospital", False, False, True),
    ("283Q00000X", "Psychiatric Hospital", "Hospitals", None, "psychiatric hospital", False, False, True),
    ("286500000X", "Military Hospital", "Hospitals", None, "hospital", False, False, True),
    # --- Other Providers ---
    ("261QR0200X", "Ambulatory Health Care Facilities - Clinic/Center, Rehab", "Ambulatory Health Care Facilities", "Rehab", "rehabilitation clinic", False, False, False),
    ("261QM0801X", "Clinic/Center - Mental Health", "Ambulatory Health Care Facilities", "Mental Health", "mental health clinic", False, False, False),
]

_TAXONOMY_MAP: dict[str, TaxonomyEntry] = {
    row[0]: TaxonomyEntry(
        code=row[0],
        display_name=row[1],
        classification=row[2],
        specialization=row[3],
        simplified_specialty=row[4],
        is_prescriber=row[5],
        is_pharmacy=row[6],
        is_hospital=row[7],
    )
    for row in _TAXONOMY_DATA
}


class TaxonomyService:
    """In-memory taxonomy reference for validation and classification.

    Backed by the NUCC code set seeded at startup. For production, the
    full taxonomy CSV is loaded into the taxonomy_codes table; this service
    wraps that in-memory cache.
    """

    def is_prescriber(self, code: str) -> bool:
        entry = _TAXONOMY_MAP.get(code)
        return entry.is_prescriber if entry else False

    def is_pharmacy(self, code: str) -> bool:
        entry = _TAXONOMY_MAP.get(code)
        return entry.is_pharmacy if entry else False

    def is_hospital(self, code: str) -> bool:
        entry = _TAXONOMY_MAP.get(code)
        return entry.is_hospital if entry else False

    def get_simplified_specialty(self, code: str) -> str | None:
        entry = _TAXONOMY_MAP.get(code)
        return entry.simplified_specialty if entry else None

    def get_display_name(self, code: str) -> str | None:
        entry = _TAXONOMY_MAP.get(code)
        return entry.display_name if entry else None

    def get_entry(self, code: str) -> TaxonomyEntry | None:
        return _TAXONOMY_MAP.get(code)

    def list_prescriber_taxonomy_codes(self) -> list[str]:
        return [code for code, entry in _TAXONOMY_MAP.items() if entry.is_prescriber]

    def list_pharmacy_taxonomy_codes(self) -> list[str]:
        return [code for code, entry in _TAXONOMY_MAP.items() if entry.is_pharmacy]

    def all_entries(self) -> list[TaxonomyEntry]:
        return list(_TAXONOMY_MAP.values())
