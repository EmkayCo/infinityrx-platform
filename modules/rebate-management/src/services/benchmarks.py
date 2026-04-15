"""Program performance benchmarking service.

Compares program metrics against industry benchmarks (configurable table).
Per-program, per-drug-class, per-period.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from src.models.tables import IndustryBenchmark, ProgramPerformanceMetric
from src.utils.money import money

PLACEHOLDER_BENCHMARKS = [
    # metric_name, drug_class, p25, p50, p75, source
    ("enrollment_rate", None, "0.3200", "0.3800", "0.4500", "PLACEHOLDER — update with actual data"),
    ("first_fill_rate", None, "0.6800", "0.7400", "0.8200", "PLACEHOLDER — update with actual data"),
    ("pdc_6month", None, "0.5800", "0.6500", "0.7400", "PLACEHOLDER — update with actual data"),
    ("abandonment_rate", None, "0.1500", "0.1200", "0.0800", "PLACEHOLDER — update with actual data"),
    ("avg_copay", None, "3200.00", "2800.00", "2200.00", "PLACEHOLDER — update with actual data"),
    ("gtn_ratio", None, "0.6600", "0.6200", "0.5600", "PLACEHOLDER — update with actual data"),
    ("misuse_rate", None, "0.0650", "0.0480", "0.0250", "PLACEHOLDER — update with actual data"),
]


class BenchmarkService:
    """Manages industry benchmarks and program performance metrics."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def seed_benchmarks(
        self, tenant_id: uuid.UUID, benchmark_year: int = 2026
    ) -> list[IndustryBenchmark]:
        """Seed placeholder benchmark values for a tenant."""
        now = datetime.now(UTC)
        seeded = []
        for metric_name, drug_class, p25, p50, p75, source in PLACEHOLDER_BENCHMARKS:
            existing = (
                self._db.query(IndustryBenchmark)
                .filter(
                    IndustryBenchmark.tenant_id == tenant_id,
                    IndustryBenchmark.metric_name == metric_name,
                    IndustryBenchmark.drug_class == drug_class,
                    IndustryBenchmark.benchmark_year == benchmark_year,
                )
                .first()
            )
            if existing:
                seeded.append(existing)
                continue
            bm = IndustryBenchmark(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                metric_name=metric_name,
                drug_class=drug_class,
                benchmark_year=benchmark_year,
                p25_value=Decimal(p25),
                p50_value=Decimal(p50),
                p75_value=Decimal(p75),
                source=source,
                created_at=now,
                updated_at=now,
            )
            self._db.add(bm)
            seeded.append(bm)
        self._db.flush()
        return seeded

    def upsert_benchmark(
        self,
        tenant_id: uuid.UUID,
        metric_name: str,
        benchmark_year: int,
        p25_value: Decimal,
        p50_value: Decimal,
        p75_value: Decimal,
        drug_class: str | None = None,
        source: str | None = None,
    ) -> IndustryBenchmark:
        now = datetime.now(UTC)
        existing = (
            self._db.query(IndustryBenchmark)
            .filter(
                IndustryBenchmark.tenant_id == tenant_id,
                IndustryBenchmark.metric_name == metric_name,
                IndustryBenchmark.drug_class == drug_class,
                IndustryBenchmark.benchmark_year == benchmark_year,
            )
            .first()
        )
        if existing:
            existing.p25_value = p25_value
            existing.p50_value = p50_value
            existing.p75_value = p75_value
            existing.source = source
            existing.updated_at = now
            self._db.flush()
            return existing

        bm = IndustryBenchmark(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            metric_name=metric_name,
            drug_class=drug_class,
            benchmark_year=benchmark_year,
            p25_value=p25_value,
            p50_value=p50_value,
            p75_value=p75_value,
            source=source,
            created_at=now,
            updated_at=now,
        )
        self._db.add(bm)
        self._db.flush()
        return bm

    def record_program_metrics(
        self,
        tenant_id: uuid.UUID,
        program_id: uuid.UUID,
        period_start: date,
        period_end: date,
        metrics: dict[str, Any],
        drug_class: str | None = None,
    ) -> ProgramPerformanceMetric:
        """Upsert performance metrics for a program/period."""
        def _d(val: Any) -> Decimal | None:
            return Decimal(str(val)) if val is not None else None

        now = datetime.now(UTC)
        record = ProgramPerformanceMetric(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            program_id=program_id,
            drug_class=drug_class,
            period_start=period_start,
            period_end=period_end,
            enrollment_rate=_d(metrics.get("enrollment_rate")),
            first_fill_rate=_d(metrics.get("first_fill_rate")),
            pdc_6month=_d(metrics.get("pdc_6month")),
            abandonment_rate=_d(metrics.get("abandonment_rate")),
            avg_copay=money(metrics["avg_copay"]) if metrics.get("avg_copay") else None,
            gtn_ratio=_d(metrics.get("gtn_ratio")),
            misuse_rate=_d(metrics.get("misuse_rate")),
            accumulator_patients_pct=_d(metrics.get("accumulator_patients_pct")),
            maximizer_patients_pct=_d(metrics.get("maximizer_patients_pct")),
            created_at=now,
        )
        self._db.add(record)
        self._db.flush()
        return record

    def compare_to_benchmarks(
        self,
        tenant_id: uuid.UUID,
        program_id: uuid.UUID,
        period_start: date,
        period_end: date,
        benchmark_year: int = 2026,
    ) -> list[dict[str, Any]]:
        """Compare program metrics against industry benchmarks.

        Returns a list of comparison rows.
        """
        metrics_rows = (
            self._db.query(ProgramPerformanceMetric)
            .filter(
                ProgramPerformanceMetric.tenant_id == tenant_id,
                ProgramPerformanceMetric.program_id == program_id,
                ProgramPerformanceMetric.period_start == period_start,
                ProgramPerformanceMetric.period_end == period_end,
            )
            .all()
        )
        if not metrics_rows:
            return []

        metrics_row = metrics_rows[0]
        benchmarks = (
            self._db.query(IndustryBenchmark)
            .filter(
                IndustryBenchmark.tenant_id == tenant_id,
                IndustryBenchmark.benchmark_year == benchmark_year,
                IndustryBenchmark.drug_class == metrics_row.drug_class,
            )
            .all()
        )
        bm_map = {b.metric_name: b for b in benchmarks}

        metric_fields = [
            ("enrollment_rate", "enrollment_rate"),
            ("first_fill_rate", "first_fill_rate"),
            ("pdc_6month", "pdc_6month"),
            ("abandonment_rate", "abandonment_rate"),
            ("avg_copay", "avg_copay"),
            ("gtn_ratio", "gtn_ratio"),
            ("misuse_rate", "misuse_rate"),
        ]

        result = []
        for field_name, bm_key in metric_fields:
            program_value = getattr(metrics_row, field_name, None)
            bm = bm_map.get(bm_key)
            industry_avg = bm.p50_value if bm else None
            delta = None
            if program_value is not None and industry_avg is not None:
                delta = Decimal(str(program_value)) - Decimal(str(industry_avg))
            result.append(
                {
                    "metric": field_name,
                    "program_value": str(program_value) if program_value is not None else None,
                    "industry_avg": str(industry_avg) if industry_avg is not None else None,
                    "delta": str(delta) if delta is not None else None,
                }
            )
        return result
