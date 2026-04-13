"""Tests for letter generation service — TDD first."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session
from src.models.tables import LetterTemplate
from src.services.letter_service import LetterService


def seed_template(db: Session, letter_type: str = "demand_letter") -> LetterTemplate:
    tmpl = LetterTemplate(
        tenant_id=None,
        name=f"Default {letter_type}",
        letter_type=letter_type,
        template_content=(
            "Dear {{subject_name}},\n\n"
            "Investigation: {{investigation_number}}\n"
            "Recovery Amount: ${{recovery_amount}}\n"
            "Due Date: {{due_date}}\n\n"
            "Sincerely,\n{{sender_name}}"
        ),
        merge_fields={"subject_name": "", "investigation_number": "", "recovery_amount": ""},
        is_active=True,
    )
    db.add(tmpl)
    db.flush()
    return tmpl


class TestLetterGeneration:
    def test_generates_letter_with_merge_fields_filled(self, db: Session) -> None:
        tmpl = seed_template(db)
        svc = LetterService(db)
        letter_text = svc.generate_letter(
            template_id=tmpl.id,
            merge_data={
                "subject_name": "Test Pharmacy Inc.",
                "investigation_number": "INV-2026-001",
                "recovery_amount": "15,000.00",
                "due_date": "2026-05-13",
                "sender_name": "InfinityRx Compliance Team",
            },
        )
        assert "Test Pharmacy Inc." in letter_text
        assert "INV-2026-001" in letter_text
        assert "15,000.00" in letter_text
        assert "{{subject_name}}" not in letter_text

    def test_missing_merge_field_raises(self, db: Session) -> None:
        tmpl = seed_template(db)
        svc = LetterService(db)
        with pytest.raises(ValueError, match="Missing merge field"):
            svc.generate_letter(
                template_id=tmpl.id,
                merge_data={
                    "investigation_number": "INV-2026-001",
                    # missing subject_name, recovery_amount, due_date, sender_name
                },
            )

    def test_inactive_template_raises(self, db: Session) -> None:
        tmpl = LetterTemplate(
            tenant_id=None,
            name="Inactive Template",
            letter_type="demand_letter",
            template_content="Content here",
            is_active=False,
        )
        db.add(tmpl)
        db.flush()
        svc = LetterService(db)
        with pytest.raises(ValueError, match="not found or inactive"):
            svc.generate_letter(template_id=tmpl.id, merge_data={})

    def test_nonexistent_template_raises(self, db: Session) -> None:
        svc = LetterService(db)
        with pytest.raises(ValueError, match="not found or inactive"):
            svc.generate_letter(
                template_id=str(uuid.uuid4()),
                merge_data={"subject_name": "X"},
            )

    def test_list_templates_by_type(self, db: Session) -> None:
        seed_template(db, "initial_notification")
        seed_template(db, "audit_notification")
        svc = LetterService(db)
        templates = svc.list_templates(letter_type="initial_notification")
        assert all(t.letter_type == "initial_notification" for t in templates)

    def test_list_templates_with_tenant_id_filter(self, db: Session) -> None:
        seed_template(db, "demand_letter")
        svc = LetterService(db)
        # System templates have tenant_id=None, so they appear for any tenant
        templates = svc.list_templates(tenant_id="test-tenant-id")
        # System template with tenant_id=None should show for any tenant
        assert any(t.letter_type == "demand_letter" for t in templates)

    def test_get_template_by_id(self, db: Session) -> None:
        tmpl = seed_template(db, "demand_letter")
        svc = LetterService(db)
        result = svc.get_template(tmpl.id)
        assert result is not None
        assert result.id == tmpl.id

    def test_get_template_nonexistent_returns_none(self, db: Session) -> None:
        import uuid
        svc = LetterService(db)
        result = svc.get_template(str(uuid.uuid4()))
        assert result is None


class TestPreBuiltTemplates:
    def test_system_templates_exist_after_seed(self, db: Session) -> None:
        from src.services.letter_service import seed_system_templates
        seed_system_templates(db)
        db.flush()
        svc = LetterService(db)
        templates = svc.list_templates()
        template_types = {t.letter_type for t in templates}
        expected = {
            "initial_notification",
            "demand_letter",
            "audit_notification",
            "audit_findings",
            "appeal_response",
            "final_demand",
            "network_termination",
        }
        assert expected.issubset(template_types)

    def test_seed_system_templates_is_idempotent(self, db: Session) -> None:
        from sqlalchemy import select as sa_select
        from src.models.tables import LetterTemplate as LT
        from src.services.letter_service import seed_system_templates

        seed_system_templates(db)
        db.flush()
        count_before = len(db.execute(
            sa_select(LT).where(LT.tenant_id.is_(None))
        ).scalars().all())

        # Seed again — should not create duplicates
        seed_system_templates(db)
        db.flush()
        count_after = len(db.execute(
            sa_select(LT).where(LT.tenant_id.is_(None))
        ).scalars().all())
        assert count_before == count_after
