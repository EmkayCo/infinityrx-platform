"""Unit tests for Jinja2 prompt templates — each template must have a test
asserting required markers render correctly.
"""

from __future__ import annotations

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pathlib import Path

PROMPTS_DIR = Path(__file__).parents[2] / "src" / "prompts"


@pytest.fixture(scope="session")
def jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(PROMPTS_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
    )


class TestDocumentExtractionTemplate:
    def test_renders_with_required_markers(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("document_extraction.jinja")
        rendered = tmpl.render(
            document_type="prior_auth_form",
            extracted_text="Patient needs lisinopril 10mg",
            fields_to_extract=["member_name", "drug_name", "diagnosis"],
            phi_access_level="redacted",
        )
        assert "extract" in rendered.lower()
        assert "JSON" in rendered or "json" in rendered
        assert "confidence" in rendered.lower()

    def test_hipaa_constraint_present(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("document_extraction.jinja")
        rendered = tmpl.render(
            document_type="eob",
            extracted_text="claim data",
            fields_to_extract=["amount"],
            phi_access_level="redacted",
        )
        assert "phi_access_level" in rendered or "PHI" in rendered or "HIPAA" in rendered

    def test_strict_undefined_raises_on_missing_var(self, jinja_env: Environment) -> None:
        from jinja2 import UndefinedError
        tmpl = jinja_env.get_template("document_extraction.jinja")
        with pytest.raises(UndefinedError):
            tmpl.render()  # missing required variables


class TestContentGenerationTemplate:
    def test_pa_request_renders_required_markers(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("content_generation.jinja")
        rendered = tmpl.render(
            template_name="PA Request Letter",
            member_name="[REDACTED]",
            drug_name="Humira 40mg",
            diagnosis="Rheumatoid Arthritis",
            clinical_criteria="Patient has failed 2 DMARDs",
            prescriber_name="Dr. Smith",
            phi_access_level="redacted",
        )
        assert "PA Request Letter" in rendered or "prior authorization" in rendered.lower()
        assert "human review" in rendered.lower() or "review" in rendered.lower()

    def test_prohibited_pattern_instruction_present(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("content_generation.jinja")
        rendered = tmpl.render(
            template_name="Audit Demand Letter",
            member_name="[REDACTED]",
            drug_name="metformin",
            diagnosis="T2DM",
            clinical_criteria="standard",
            prescriber_name="Dr. Jones",
            phi_access_level="redacted",
        )
        assert "required" in rendered.lower() or "must not" in rendered.lower() or "prohibited" in rendered.lower()


class TestAnomalyNarrativeTemplate:
    def test_renders_with_flag_data(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("anomaly_narrative.jinja")
        rendered = tmpl.render(
            entity_type="pharmacy",
            entity_id="NPI-1234567890",
            anomaly_type="nq_inflation",
            evidence={"nq_wac_ratio": 1.52, "baseline_ratio": 1.05},
            claim_count=47,
            phi_access_level="redacted",
        )
        assert "anomaly" in rendered.lower() or "flag" in rendered.lower() or "detect" in rendered.lower()
        assert "narrative" in rendered.lower() or "explain" in rendered.lower() or "summary" in rendered.lower()


class TestChatbotSystemTemplate:
    def test_renders_with_portal_type(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("chatbot_system.jinja")
        rendered = tmpl.render(
            portal_type="pharmacy",
            phi_access_level="redacted",
        )
        assert "pharmacy" in rendered.lower()
        assert "PHI" in rendered or "phi_access_level" in rendered

    def test_citation_instruction_present(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("chatbot_system.jinja")
        rendered = tmpl.render(
            portal_type="member",
            phi_access_level="redacted",
        )
        assert "source" in rendered.lower() or "citation" in rendered.lower() or "cite" in rendered.lower()

    def test_no_coverage_determination_instruction(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("chatbot_system.jinja")
        rendered = tmpl.render(
            portal_type="medical",
            phi_access_level="redacted",
        )
        assert "coverage determination" in rendered.lower() or "cannot determine" in rendered.lower() or "will not" in rendered.lower()


class TestSummarizationTemplate:
    def test_renders_with_source_text(self, jinja_env: Environment) -> None:
        tmpl = jinja_env.get_template("summarization.jinja")
        rendered = tmpl.render(
            source_text="Long medical record content here...",
            summary_type="clinical",
            max_length_words=200,
            phi_access_level="redacted",
        )
        assert "summarize" in rendered.lower() or "summary" in rendered.lower()
        assert "200" in rendered or "word" in rendered.lower()
