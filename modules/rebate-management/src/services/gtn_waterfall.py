"""GTN (Gross-to-Net) Waterfall service.

Calculates and stores daily snapshots of the GTN waterfall per drug.
Each step is Decimal with ROUND_HALF_UP.

WAC → wholesaler discount → prompt pay → rebates → chargebacks
    → copay assistance → copay misuse/leakage (ReclaimRx) → admin fees
    → net price

GTN ratio = net_price / wac
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from src.models.tables import GTNWaterfallSnapshot
from src.utils.money import ZERO, money

FOUR_PLACES = Decimal("0.0001")


class GTNWaterfallService:
    """Manages GTN waterfall snapshots."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def compute_net_price(
        self,
        wac: Decimal,
        wholesaler_discount: Decimal = ZERO,
        prompt_pay_discount: Decimal = ZERO,
        rebates: Decimal = ZERO,
        chargebacks: Decimal = ZERO,
        copay_assistance: Decimal = ZERO,
        copay_misuse_leakage: Decimal = ZERO,
        admin_fees: Decimal = ZERO,
    ) -> tuple[Decimal, Decimal]:
        """Compute net price and GTN ratio from waterfall components.

        All deductions are subtracted from WAC. Returns (net_price, gtn_ratio).
        gtn_ratio = net_price / wac (as a fraction, e.g. Decimal("0.6400") = 64%).
        """
        total_deductions = money(
            wholesaler_discount
            + prompt_pay_discount
            + rebates
            + chargebacks
            + copay_assistance
            + copay_misuse_leakage
            + admin_fees
        )
        net_price = money(wac - total_deductions)
        if wac > ZERO:
            gtn_ratio = (net_price / wac).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        else:
            gtn_ratio = ZERO.quantize(FOUR_PLACES)
        return net_price, gtn_ratio

    def upsert_snapshot(
        self,
        tenant_id: uuid.UUID,
        ndc11: str,
        snapshot_date: date,
        wac: Decimal,
        wholesaler_discount: Decimal = ZERO,
        prompt_pay_discount: Decimal = ZERO,
        rebates: Decimal = ZERO,
        chargebacks: Decimal = ZERO,
        copay_assistance: Decimal = ZERO,
        copay_misuse_leakage: Decimal = ZERO,
        admin_fees: Decimal = ZERO,
        drug_name: str | None = None,
        program_id: uuid.UUID | None = None,
        fwa_data_available: bool = False,
    ) -> GTNWaterfallSnapshot:
        """Create or update a GTN waterfall snapshot."""
        wac_d = money(wac)
        wd_d = money(wholesaler_discount)
        pp_d = money(prompt_pay_discount)
        rb_d = money(rebates)
        cb_d = money(chargebacks)
        ca_d = money(copay_assistance)
        cm_d = money(copay_misuse_leakage)
        af_d = money(admin_fees)

        net_price, gtn_ratio = self.compute_net_price(
            wac_d, wd_d, pp_d, rb_d, cb_d, ca_d, cm_d, af_d
        )

        existing = (
            self._db.query(GTNWaterfallSnapshot)
            .filter(
                GTNWaterfallSnapshot.tenant_id == tenant_id,
                GTNWaterfallSnapshot.ndc11 == ndc11,
                GTNWaterfallSnapshot.snapshot_date == snapshot_date,
                GTNWaterfallSnapshot.program_id == program_id,
            )
            .first()
        )

        now = datetime.now(UTC)
        if existing:
            existing.wac = wac_d
            existing.wholesaler_discount = wd_d
            existing.prompt_pay_discount = pp_d
            existing.rebates = rb_d
            existing.chargebacks = cb_d
            existing.copay_assistance = ca_d
            existing.copay_misuse_leakage = cm_d
            existing.admin_fees = af_d
            existing.net_price = net_price
            existing.gtn_ratio = gtn_ratio
            existing.fwa_data_available = fwa_data_available
            if drug_name:
                existing.drug_name = drug_name
            self._db.flush()
            return existing

        snapshot = GTNWaterfallSnapshot(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            ndc11=ndc11,
            drug_name=drug_name,
            program_id=program_id,
            snapshot_date=snapshot_date,
            wac=wac_d,
            wholesaler_discount=wd_d,
            prompt_pay_discount=pp_d,
            rebates=rb_d,
            chargebacks=cb_d,
            copay_assistance=ca_d,
            copay_misuse_leakage=cm_d,
            admin_fees=af_d,
            net_price=net_price,
            gtn_ratio=gtn_ratio,
            fwa_data_available=fwa_data_available,
            created_at=now,
        )
        self._db.add(snapshot)
        self._db.flush()
        return snapshot

    def get_waterfall(
        self,
        tenant_id: uuid.UUID,
        ndc11: str,
        snapshot_date: date,
        program_id: uuid.UUID | None = None,
    ) -> GTNWaterfallSnapshot | None:
        q = self._db.query(GTNWaterfallSnapshot).filter(
            GTNWaterfallSnapshot.tenant_id == tenant_id,
            GTNWaterfallSnapshot.ndc11 == ndc11,
            GTNWaterfallSnapshot.snapshot_date == snapshot_date,
        )
        if program_id is not None:
            q = q.filter(GTNWaterfallSnapshot.program_id == program_id)
        return q.first()

    def get_waterfall_detail(
        self, snapshot: GTNWaterfallSnapshot
    ) -> dict:
        """Return structured waterfall detail dict for API response.

        Integrates with ReclaimRx: if fwa_data_available is False,
        the copay_misuse_leakage line is shown as $0.00 with a note.
        """
        fwa_note = (
            None
            if snapshot.fwa_data_available
            else "no FWA data available"
        )
        return {
            "ndc11": snapshot.ndc11,
            "drug_name": snapshot.drug_name,
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "wac": str(snapshot.wac),
            "deductions": {
                "wholesaler_discount": str(snapshot.wholesaler_discount),
                "prompt_pay_discount": str(snapshot.prompt_pay_discount),
                "rebates": str(snapshot.rebates),
                "chargebacks": str(snapshot.chargebacks),
                "copay_assistance": str(snapshot.copay_assistance),
                "copay_misuse_leakage": str(snapshot.copay_misuse_leakage),
                "copay_misuse_leakage_note": fwa_note,
                "admin_fees": str(snapshot.admin_fees),
            },
            "net_price": str(snapshot.net_price),
            "gtn_ratio": str(snapshot.gtn_ratio),
            "gtn_ratio_pct": str(
                (snapshot.gtn_ratio * Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            ),
        }
