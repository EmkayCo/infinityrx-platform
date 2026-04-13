"""Letter generation service — template-based demand/notification letter generation."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.tables import LetterTemplate

SYSTEM_TEMPLATES = [
    {
        "name": "Initial Notification",
        "letter_type": "initial_notification",
        "template_content": (
            "Dear {{subject_name}},\n\n"
            "This letter serves as official notification that {{company_name}} has initiated "
            "a review of claims submitted under your account for the period of {{date_range}}.\n\n"
            "Investigation Reference: {{investigation_number}}\n\n"
            "Please retain all records related to the above claim period.\n\n"
            "Sincerely,\n{{sender_name}}\n{{sender_title}}"
        ),
        "merge_fields": {
            "subject_name": "Name of pharmacy/prescriber",
            "company_name": "Payer company name",
            "date_range": "Date range under review",
            "investigation_number": "Investigation reference number",
            "sender_name": "Sender name",
            "sender_title": "Sender title",
        },
    },
    {
        "name": "Demand Letter",
        "letter_type": "demand_letter",
        "template_content": (
            "Dear {{subject_name}},\n\n"
            "Following our investigation (Ref: {{investigation_number}}), we have determined "
            "that an overpayment of ${{recovery_amount}} was made for the period ending {{date_range}}.\n\n"
            "Payment is due by {{due_date}}.\n\n"
            "Sincerely,\n{{sender_name}}"
        ),
        "merge_fields": {
            "subject_name": "",
            "investigation_number": "",
            "recovery_amount": "",
            "date_range": "",
            "due_date": "",
            "sender_name": "",
        },
    },
    {
        "name": "Audit Notification",
        "letter_type": "audit_notification",
        "template_content": (
            "Dear {{subject_name}},\n\n"
            "You are hereby notified that {{company_name}} will conduct a {{audit_type}} audit "
            "covering claims from {{audit_start_date}} to {{audit_end_date}}.\n\n"
            "Audit Reference: {{investigation_number}}\n"
            "Please have the following documents available by {{document_due_date}}:\n"
            "{{document_list}}\n\n"
            "Sincerely,\n{{sender_name}}"
        ),
        "merge_fields": {
            "subject_name": "",
            "company_name": "",
            "audit_type": "",
            "audit_start_date": "",
            "audit_end_date": "",
            "investigation_number": "",
            "document_due_date": "",
            "document_list": "",
            "sender_name": "",
        },
    },
    {
        "name": "Audit Findings",
        "letter_type": "audit_findings",
        "template_content": (
            "Dear {{subject_name}},\n\n"
            "We have completed our review. The following discrepancies were identified:\n\n"
            "{{findings_summary}}\n\n"
            "Total Discrepancy: ${{total_discrepancy}}\n"
            "Response Due: {{response_due_date}}\n\n"
            "Sincerely,\n{{sender_name}}"
        ),
        "merge_fields": {
            "subject_name": "",
            "findings_summary": "",
            "total_discrepancy": "",
            "response_due_date": "",
            "sender_name": "",
        },
    },
    {
        "name": "Appeal Response",
        "letter_type": "appeal_response",
        "template_content": (
            "Dear {{subject_name}},\n\n"
            "We have reviewed your appeal dated {{appeal_date}} regarding "
            "Investigation {{investigation_number}}.\n\n"
            "Our determination: {{determination}}\n\n"
            "{{determination_detail}}\n\n"
            "Sincerely,\n{{sender_name}}"
        ),
        "merge_fields": {
            "subject_name": "",
            "appeal_date": "",
            "investigation_number": "",
            "determination": "",
            "determination_detail": "",
            "sender_name": "",
        },
    },
    {
        "name": "Final Demand",
        "letter_type": "final_demand",
        "template_content": (
            "FINAL DEMAND\n\n"
            "Dear {{subject_name}},\n\n"
            "Despite our previous demand dated {{initial_demand_date}}, payment of "
            "${{recovery_amount}} remains outstanding. This is your final notice before "
            "this matter is referred to {{escalation_action}}.\n\n"
            "Final payment due: {{final_due_date}}\n\n"
            "Sincerely,\n{{sender_name}}"
        ),
        "merge_fields": {
            "subject_name": "",
            "initial_demand_date": "",
            "recovery_amount": "",
            "escalation_action": "",
            "final_due_date": "",
            "sender_name": "",
        },
    },
    {
        "name": "Network Termination Notice",
        "letter_type": "network_termination",
        "template_content": (
            "Dear {{subject_name}},\n\n"
            "This letter serves as official notice that your participation in the "
            "{{network_name}} network will be terminated effective {{termination_date}} "
            "due to {{termination_reason}}.\n\n"
            "Investigation Reference: {{investigation_number}}\n\n"
            "Sincerely,\n{{sender_name}}"
        ),
        "merge_fields": {
            "subject_name": "",
            "network_name": "",
            "termination_date": "",
            "termination_reason": "",
            "investigation_number": "",
            "sender_name": "",
        },
    },
]

_MERGE_FIELD_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class LetterService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def generate_letter(
        self,
        *,
        template_id: str,
        merge_data: dict[str, str],
        tenant_id: str | None = None,
    ) -> str:
        """Generate a letter from a template with merge fields filled in."""
        tmpl = self._session.execute(
            select(LetterTemplate).where(
                LetterTemplate.id == template_id,
                LetterTemplate.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if tmpl is None:
            raise ValueError(f"Letter template {template_id} not found or inactive")

        content = tmpl.template_content
        required_fields = set(_MERGE_FIELD_PATTERN.findall(content))
        missing = required_fields - set(merge_data.keys())
        if missing:
            raise ValueError(f"Missing merge field(s): {sorted(missing)}")

        for field_name, value in merge_data.items():
            content = content.replace("{{" + field_name + "}}", value)

        return content

    def list_templates(
        self,
        *,
        letter_type: str | None = None,
        tenant_id: str | None = None,
    ) -> list[LetterTemplate]:
        stmt = select(LetterTemplate).where(LetterTemplate.is_active.is_(True))
        if letter_type:
            stmt = stmt.where(LetterTemplate.letter_type == letter_type)
        if tenant_id:
            stmt = stmt.where(
                (LetterTemplate.tenant_id == tenant_id) | (LetterTemplate.tenant_id.is_(None))
            )
        return list(self._session.execute(stmt).scalars())

    def get_template(self, template_id: str) -> LetterTemplate | None:
        return self._session.execute(
            select(LetterTemplate).where(LetterTemplate.id == template_id)
        ).scalar_one_or_none()


def seed_system_templates(session: Session) -> None:
    """Seed system-wide letter templates if not already present."""
    for tmpl_data in SYSTEM_TEMPLATES:
        existing = session.execute(
            select(LetterTemplate).where(
                LetterTemplate.letter_type == tmpl_data["letter_type"],
                LetterTemplate.tenant_id.is_(None),
            )
        ).scalar_one_or_none()
        if existing is None:
            tmpl = LetterTemplate(
                tenant_id=None,
                name=tmpl_data["name"],
                letter_type=tmpl_data["letter_type"],
                template_content=tmpl_data["template_content"],
                merge_fields=tmpl_data.get("merge_fields"),
                is_active=True,
            )
            session.add(tmpl)
