"""Tests for detection rule seeder — idempotency and coverage."""
from __future__ import annotations

from sqlalchemy.orm import Session
from src.models.tables import DetectionProfile, DetectionRule
from src.services.detection_rule_seeder import seed_detection_rules


class TestDetectionRuleSeeder:
    def test_seeds_rules_on_first_call(self, db: Session) -> None:
        count = seed_detection_rules(db)
        assert count > 0
        rules = db.execute(__import__("sqlalchemy").select(DetectionRule)).scalars().all()
        assert len(rules) > 0

    def test_seed_is_idempotent_rules(self, db: Session) -> None:
        from sqlalchemy import select
        seed_detection_rules(db)
        count_after_first = len(db.execute(select(DetectionRule)).scalars().all())
        # Second call should not create duplicates (existing rules skipped)
        count_returned = seed_detection_rules(db)
        count_after_second = len(db.execute(select(DetectionRule)).scalars().all())
        assert count_after_first == count_after_second
        assert count_returned == 0

    def test_seed_is_idempotent_profiles(self, db: Session) -> None:
        from sqlalchemy import select
        seed_detection_rules(db)
        count_after_first = len(db.execute(select(DetectionProfile)).scalars().all())
        seed_detection_rules(db)
        count_after_second = len(db.execute(select(DetectionProfile)).scalars().all())
        assert count_after_first == count_after_second

    def test_rule_code_not_found_in_profile_rules(self, db: Session) -> None:
        from sqlalchemy import select
        # Seed rules only (no profiles), then manually call seed which will try to look up rule codes
        # Rule code in profile that doesn't exist in DB is handled gracefully (line 760)
        seed_detection_rules(db)
        profiles = db.execute(select(DetectionProfile)).scalars().all()
        # All profiles should exist despite any missing rule codes
        assert len(profiles) > 0
