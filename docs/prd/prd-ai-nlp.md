# PRD — Module 21: AI/NLP Layer — FINAL

**Module:** AI/NLP Layer  
**Folder:** `modules/ai-nlp/`  
**Priority:** Phase 2, Batch B  
**Dependencies:** Core Platform (Module 1), consumes data from Billing (11), ReclaimRx (16), Reporting (15)  

---

## 1. Purpose

The AI/NLP Layer provides intelligent automation services to every other module. It is NOT a standalone product — it's a service layer that other modules call when they need AI capabilities. It centralizes all LLM, NLP, and document intelligence functionality so no module implements its own AI logic.

**What it provides:**
1. **Document Intelligence** — OCR, extraction, classification for any uploaded document (medical records, EOBs, faxed PA forms, audit evidence, invoices)
2. **Text Understanding** — NLP for clinical notes, prior auth letters, audit responses, denial reasons, appeal letters
3. **Content Generation** — draft PA letters, audit demand letters, appeal responses, investigation summaries, member communications
4. **Conversational AI** — chatbot/virtual assistant for portals (pharmacy queries, member benefit questions, claim status)
5. **Intelligent Routing** — classify inbound documents and messages, route to correct queue/handler
6. **Data Extraction** — structured data from unstructured sources (extract claim data from paper forms, extract clinical criteria from medical records)
7. **Summarization** — condense long investigation timelines, audit findings, member claim histories into executive summaries
8. **Translation** — multi-language support for member communications
9. **Anomaly Narrative** — given a flagged claim or anomaly from ReclaimRx, generate a human-readable explanation of WHY it was flagged

**What it does NOT do:**
- Does not make financial decisions (Billing does that)
- Does not make FWA determinations (ReclaimRx does that)
- Does not adjudicate claims (Adjudication Engine does that)
- Does not generate reports (Reporting does that)
- AI suggests, humans decide. Every AI output has a confidence score and requires human confirmation for consequential actions.

---

## 2. Architecture

```
                     OTHER MODULES
                     ═════════════
                          │
            ┌─────────────┼─────────────┐
            │             │             │
       API Request   Event Trigger   Scheduled Job
            │             │             │
            └─────────────┼─────────────┘
                          │
                   AI/NLP SERVICE LAYER
                   ════════════════════
                          │
            ┌─────────────┼─────────────┐
            │             │             │
     Document        LLM Gateway      NLP Pipeline
     Intelligence         │                │
            │        ┌────┴────┐     ┌────┴────┐
     Azure Doc   Azure OpenAI  │   spaCy    Regex
     Intelligence  GPT-4.1     │   Pipeline  Extractors
            │        │         │       │
     Mistral Doc  Prompt       │   Entity    Classification
     AI (secondary) Templates  │   Recognition
            │        │         │       │
            └────────┼─────────┘       │
                     │                 │
              Response + Confidence Score
                     │
              Audit Log (every AI call logged)
```

---

## 3. Data Model

```sql
CREATE SCHEMA ai_nlp;

-- AI service requests (every AI call logged for audit and cost tracking)
CREATE TABLE ai_nlp.service_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- What was requested
    service_type VARCHAR(100) NOT NULL,
    -- document_extraction, text_classification, content_generation,
    -- summarization, translation, anomaly_narrative, conversational,
    -- document_routing, data_extraction
    
    -- Source
    requesting_module VARCHAR(100) NOT NULL,
    requesting_entity_type VARCHAR(100),
    requesting_entity_id UUID,
    correlation_id UUID,
    
    -- Input
    input_type VARCHAR(50) NOT NULL,                  -- text, document, image, structured_data
    input_size_tokens INTEGER,
    input_file_id UUID,
    
    -- Processing
    model_used VARCHAR(100) NOT NULL,                  -- gpt-4.1, azure-doc-intel, mistral-doc-ai, spacy
    prompt_template_id UUID,
    
    -- Output
    output_text TEXT,
    output_structured JSONB,
    confidence_score DECIMAL(5,4),                     -- 0.0000 to 1.0000
    
    -- Cost tracking
    input_tokens INTEGER,
    output_tokens INTEGER,
    estimated_cost_usd DECIMAL(10,6),
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    -- pending, processing, completed, failed, human_review_required
    
    processing_time_ms INTEGER,
    error_message TEXT,
    
    -- Human review (if confidence below threshold)
    requires_human_review BOOLEAN DEFAULT FALSE,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    review_outcome VARCHAR(50),                        -- accepted, modified, rejected
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_tenant_type ON ai_nlp.service_requests(tenant_id, service_type, created_at DESC);
CREATE INDEX idx_ai_module ON ai_nlp.service_requests(requesting_module, created_at DESC);

-- Prompt templates (versioned, configurable per tenant)
CREATE TABLE ai_nlp.prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,                                    -- null = system-wide
    
    name VARCHAR(255) NOT NULL,
    service_type VARCHAR(100) NOT NULL,
    version INTEGER DEFAULT 1,
    
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT NOT NULL,                 -- with {placeholders}
    output_format VARCHAR(50) DEFAULT 'text',          -- text, json, structured
    output_schema JSONB,                               -- if structured, define expected schema
    
    -- Quality
    temperature DECIMAL(3,2) DEFAULT 0.10,             -- low temperature for deterministic outputs
    max_tokens INTEGER DEFAULT 2000,
    
    -- Guardrails
    required_confidence DECIMAL(5,4) DEFAULT 0.8000,   -- below this → human review
    prohibited_patterns JSONB,                          -- regex patterns that must NOT appear in output
    required_patterns JSONB,                            -- regex patterns that MUST appear in output
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Document processing results
CREATE TABLE ai_nlp.document_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_request_id UUID NOT NULL REFERENCES ai_nlp.service_requests(id),
    tenant_id UUID NOT NULL,
    
    -- Source document
    source_file_id UUID NOT NULL,
    document_type VARCHAR(100),                         -- classified type (eob, medical_record, pa_form, invoice, audit_evidence)
    page_count INTEGER,
    
    -- Extraction results
    extracted_fields JSONB NOT NULL,                    -- {field_name: {value, confidence, page, bounding_box}}
    extracted_text TEXT,                                 -- full text extraction
    
    -- Dual-model consensus (if using both Azure Doc Intel + Mistral)
    primary_model_result JSONB,
    secondary_model_result JSONB,
    consensus_fields JSONB,                             -- fields where both models agree
    disagreement_fields JSONB,                          -- fields where models disagree → human review
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Conversation history (for chatbot/virtual assistant)
CREATE TABLE ai_nlp.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID,
    session_id VARCHAR(100) NOT NULL,
    
    portal_type VARCHAR(50) NOT NULL,                  -- pharmacy, member, client, medical
    
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    escalated_to_human BOOLEAN DEFAULT FALSE,
    escalation_reason TEXT,
    satisfaction_rating INTEGER                          -- 1-5 if collected
);

CREATE TABLE ai_nlp.conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES ai_nlp.conversations(id),
    
    role VARCHAR(20) NOT NULL,                          -- user, assistant, system
    content TEXT NOT NULL,
    
    -- If assistant message: which service request produced it
    service_request_id UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cost tracking aggregates
CREATE TABLE ai_nlp.cost_summary (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    service_type VARCHAR(100) NOT NULL,
    model_used VARCHAR(100) NOT NULL,
    
    request_count INTEGER NOT NULL,
    total_input_tokens BIGINT NOT NULL,
    total_output_tokens BIGINT NOT NULL,
    total_estimated_cost DECIMAL(12,4) NOT NULL,
    avg_confidence DECIMAL(5,4),
    human_review_count INTEGER DEFAULT 0,
    
    UNIQUE(tenant_id, period_start, service_type, model_used)
);
```

---

## 4. AI Services

### 4.1 Document Intelligence

**Dual-model consensus architecture:**
- Primary: Azure Document Intelligence (Form Recognizer) — excels at structured forms, tables, key-value extraction
- Secondary: Mistral Document AI 2512 — excels at understanding document context and narrative text
- For each document: both models process independently. Fields where both agree get HIGH confidence. Fields where they disagree get flagged for human review.
- Configurable: tenant can use single model (faster, cheaper) or dual model (higher accuracy).

**Pre-built document types:**
| Document Type | Extraction Fields | Primary Use |
|---|---|---|
| EOB (Explanation of Benefits) | payer, member, claim numbers, amounts, denial codes, allowed amounts | Medical claims processing |
| Prior Authorization Form | member, drug, diagnosis, prescriber, clinical criteria, prior therapies | PA automation |
| Medical Record / Clinical Note | diagnoses, medications, lab values, treatment history | PA support, clinical review |
| CMS-1500 | all 33 form fields | Medical claims ingestion |
| CMS-1450 (UB-04) | all form fields | Facility claims ingestion |
| Pharmacy Invoice | pharmacy, drug, NDC, quantity, amount, date | Billing reconciliation |
| Audit Evidence | prescription copy, signature log, inventory record | ReclaimRx investigation |
| Appeal Letter | member, claim reference, appeal reason, supporting evidence | Appeals processing |

**Custom document types:** tenants can define new document types with custom extraction fields. Train on 10+ examples.

### 4.2 Text Understanding / NLP Pipeline

**spaCy-based pipeline** for fast, local text processing (no API call needed):
- Named Entity Recognition (NER): drug names, diagnosis terms, procedure codes, pharmacy names, prescriber names
- Text classification: document type, sentiment, urgency level, topic
- Clinical NLP: extract medication list, dosage, frequency, duration from clinical text
- Denial reason extraction: parse denial letters to extract structured denial codes and reasons

**LLM-based understanding** for complex comprehension (via Azure OpenAI):
- Summarize a 50-page medical record into 1-page clinical summary
- Extract whether a PA letter meets specific clinical criteria
- Compare two documents and identify discrepancies
- Interpret complex regulatory language in plain English

### 4.3 Content Generation

All generated content requires human review before sending. No auto-send.

**Pre-built generation templates:**
| Template | Use Case | Requesting Module |
|---|---|---|
| PA Request Letter | Draft prior authorization request from clinical data | Prior Auth (Module 10) |
| PA Appeal Letter | Draft appeal from denial reason + clinical evidence | Prior Auth (Module 10) |
| Audit Demand Letter | Draft recovery demand from investigation findings | ReclaimRx (Module 16) |
| Investigation Summary | Summarize investigation timeline for review | ReclaimRx (Module 16) |
| Member Communication | Plain-language explanation of benefit determination | Portals (Module 20) |
| Client Report Narrative | Executive summary paragraph for financial reports | Reporting (Module 15) |
| Corrective Action Plan | Draft CAP from audit findings | ReclaimRx (Module 16) |

**Guardrails on generation:**
- Temperature: 0.1 default (deterministic, not creative)
- Prohibited patterns: no legal claims ("you are required to"), no medical advice ("you should take"), no financial guarantees
- Required patterns: configurable per template (e.g., demand letters must include recovery amount and deadline)
- PHI handling: generated content can INCLUDE PHI from the input data (it's responding about a specific member) but must never INVENT PHI
- Every generated document reviewed by human before delivery

### 4.4 Conversational AI (Portal Virtual Assistant)

**RAG-based chatbot** for each portal type:

- **Pharmacy portal:** answer questions about claim status, payment status, remittance details, network requirements, audit status
- **Member portal:** answer questions about benefits, copay, deductible status, pharmacy locations, drug coverage
- **Client portal:** answer questions about program performance, billing status, report availability
- **Medical portal:** answer questions about PA requirements, coverage criteria, appeal process

**Architecture:**
1. User asks a question
2. NLP classifies intent and extracts entities (member ID, claim number, drug name)
3. RAG retrieves relevant data from the appropriate module's API (billing, claims, member, plan design)
4. LLM generates response using retrieved data + conversation history
5. Response includes confidence score
6. Low confidence → escalate to human agent with full context

**Guardrails:**
- Cannot make coverage determinations ("Your claim will be approved") — only state facts ("Your claim is currently pending review")
- Cannot provide medical advice
- Cannot modify any data (read-only access to other modules)
- Escalation trigger: 2 consecutive low-confidence responses, user frustration detected, or user explicitly requests human agent
- Conversation history preserved for quality review

### 4.5 Intelligent Document Routing

When a document is uploaded (via any portal, email, SFTP, or API):

1. Document Intelligence classifies the document type
2. Based on type, route to the correct processing queue:
   - EOB → Medical Claims module
   - PA form → Prior Auth module
   - Audit evidence → ReclaimRx investigation
   - Invoice → Billing module
   - Unknown → manual classification queue
3. Extract key identifiers (member ID, claim number, pharmacy NPI) for auto-linking to existing records
4. Confidence score on classification: HIGH → auto-route, MEDIUM → route with flag, LOW → manual queue

### 4.6 Anomaly Narrative Generation

When ReclaimRx flags a claim or entity:

1. ReclaimRx emits `fwa.claim_flagged` event with evidence data
2. AI/NLP generates a human-readable narrative explaining:
   - What was detected ("This pharmacy's NQ exceeded 150% of WAC on 47 claims in March")
   - Why it's unusual ("The pharmacy's 90-day average NQ/WAC ratio is 105%. This month's ratio is 152%.")
   - Comparison context ("This pharmacy is in the 98th percentile for NQ inflation among independent pharmacies in this network")
   - Suggested action ("Recommend desk audit. Estimated recovery: $23,400 - $31,200")
3. Narrative attached to the flag/investigation for investigator to review
4. Investigator does NOT have to read raw data tables — the narrative tells the story

### 4.7 LLM Provider Fallback

Primary: Azure OpenAI GPT-4.1. If Azure OpenAI is unavailable (API error, rate limit, outage):

1. Circuit breaker detects consecutive failures (threshold: 3)
2. Automatic failover to secondary provider: Anthropic Claude API (configured per tenant)
3. For critical-path services (document routing, chatbot): local spaCy models provide degraded but functional service without any LLM
4. All failover events logged and alerted
5. When primary recovers: circuit breaker half-opens, test call, resume if successful
6. Configurable: tenants can disable fallback if they require data to stay within Azure

### 4.8 Human Feedback Loop

When a human corrects an AI output (modifies extracted fields, edits generated content, overrides classification):

1. Store the correction: original AI output + human correction + correction type (field_value, classification, content_edit)
2. Track accuracy per document type per extraction field over time
3. Monthly: analyze correction patterns. If a specific field is corrected >20% of the time, flag prompt template for refinement.
4. Corrections feed into fine-tuning dataset (if using fine-tuned models) or prompt example library (if using few-shot prompting)
5. Dashboard: AI accuracy trending by service type, document type, and field

### 4.9 Batch Document Processing

For bulk uploads (100+ documents):

1. Client uploads a zip/folder of documents via API or portal
2. System creates a batch job with progress tracking
3. Documents queued and processed in parallel (configurable concurrency: default 10 simultaneous)
4. Progress: X of Y complete, estimated time remaining
5. Results available as batch: download all extractions as CSV/Excel, or review individually
6. Failed documents (low confidence, unreadable) collected in a separate review queue
7. Batch completion notification when all documents processed

### 4.10 Model Version Pinning

1. Every service request records the exact model version used (e.g., `gpt-4.1-2026-03-15`)
2. Prompt templates pin to a specific model version (configurable)
3. When Azure deploys a new model version: do NOT auto-switch. New version tested against known test documents/prompts first.
4. Test suite: 50+ known-good input/output pairs per service type. Run against new version. If accuracy drops: alert, do not switch.
5. Manual promotion: admin reviews test results and approves version switch.

### 4.11 Response Caching

For chatbot and repeated queries:

1. Cache key = hash(tenant_id + service_type + input_content + model_version)
2. If cache hit and cache age < TTL (configurable, default: 1 hour for chatbot, 24 hours for document routing): return cached response
3. Cache invalidation: when underlying data changes (new claims, payment status change), invalidate relevant cached responses
4. Cache storage: Redis with configurable TTL per service type
5. Cache hit rate tracked as a metric (target: >30% for chatbot, reduces cost significantly)

### 4.12 CMS-0057-F FHIR PA Support

CMS mandates FHIR-based electronic prior authorization by January 2027:

1. **FHIR Prior Authorization Resource builder**: convert internal PA data into FHIR R4 Prior Authorization Request resource
2. **FHIR API consumer**: submit PA requests to payer FHIR endpoints per CMS-0057-F specification
3. **FHIR status polling**: check PA decision status via FHIR API
4. **FHIR response parser**: parse PA decisions (approved, denied, pended) from FHIR responses
5. Integration point for Module 10 (Prior Auth) when built in Phase 5

### 4.13 Denial Prediction

Before submitting a PA request:

1. Extract: payer, drug, diagnosis, clinical criteria from the PA data
2. Query historical PA outcomes for this payer + drug + diagnosis combination
3. ML model (logistic regression or gradient boosting) predicts approval probability
4. If probability < configurable threshold (default: 50%): flag as "likely denial" with reasons (which criteria are typically required but missing)
5. Suggest: additional clinical documentation that would increase approval probability
6. Accuracy tracked: predicted vs actual outcome

### 4.14 Clinical Criteria Matching

For PA automation:

1. Maintain a structured database of payer-specific PA criteria per drug (from payer formularies, companion guides)
2. Extract clinical data from the patient's record (via document intelligence)
3. Automatically match: which criteria are satisfied, which are missing, which are ambiguous
4. Output: criteria checklist with status (met / not met / insufficient data) and citations to source document
5. Configurable per payer per drug — criteria loaded from payer publications or manually entered

### 4.15 NLP Auto-Coding (Medical Claims Support)

For Module 14 (Medical Claims) and Module 22 (Medical Claims Domain):

1. Extract clinical text from medical records, encounter notes, or discharge summaries
2. NLP suggests ICD-10 diagnosis codes based on clinical language
3. NLP suggests CPT/HCPCS procedure codes based on documented procedures
4. Output: suggested codes with confidence scores and citations to source text
5. Human coder reviews and confirms/corrects before submission
6. Accuracy tracking: auto-coded vs human-corrected, by code type and specialty

### 4.16 Performance Requirements

- Document extraction (single page): <5 seconds
- Document extraction (multi-page, 10 pages): <30 seconds
- Content generation (single template): <10 seconds
- Chatbot response: <3 seconds
- Text classification: <1 second
- Batch processing throughput: 100 documents/hour minimum
- Denial prediction: <2 seconds

### 4.17 Data Retention

- Service request logs: 7 years (audit trail)
- Document extraction results: per tenant policy (default: 7 years)
- Conversation history: 2 years (operational), then archive
- Prompt templates: indefinite (configuration)
- Human corrections: indefinite (training data)
- Cost summaries: indefinite (financial reporting)

### 4.18 Document Processing Pipeline Architecture

The complete document processing pipeline runs in this order:

```
INBOUND DOCUMENT
       │
  ┌────┴────┐
  │ PRE-PROCESS │ → deskew, denoise, enhance, red-ink dropout (CMS-1500)
  └────┬────┘
       │
  ┌────┴────┐
  │ SPLIT    │ → detect document boundaries in fax bundles, split into individual docs
  └────┬────┘
       │
  ┌────┴────┐
  │ CLASSIFY │ → identify document type (CMS-1500, UB-04, EOB, PA form, clinical note, etc.)
  └────┬────┘
       │
  ┌────┴────┐
  │ ROUTE    │ → structured forms → Azure Doc Intel primary; unstructured → Mistral OCR primary
  └────┬────┘
       │
  ┌────┴────────────────┐
  │ DUAL EXTRACTION      │ → Parser 1 extracts, Parser 2 extracts (parallel or selective)
  └────┬────────────────┘
       │
  ┌────┴────┐
  │ CONSENSUS│ → per-field comparison, confidence scoring, disagreement flagging
  └────┬────┘
       │
  ┌────┴────┐
  │ VALIDATE │ → cross-field dependency checks (diagnosis pointers, revenue code cascading)
  └────┬────┘
       │
  ┌────┴────┐
  │ CORRECT  │ → self-correction loops (total vs sum-of-lines), agentic LLM correction for low-conf
  └────┬────┘
       │
  ┌────┴────┐
  │ OUTPUT   │ → structured data + per-field confidence + page citations + correction audit trail
  └────┬────┘
       │
  AUTO-ROUTE or HUMAN REVIEW
```

### 4.19 Document Pre-Processing Pipeline

Before OCR, every document passes through pre-processing:

1. **Deskew**: detect and correct rotated/skewed scans (common from fax machines and mobile scans). Skew of even 2° can shift CMS-1500 Box 24 line items to wrong rows.
2. **Denoise**: remove scan artifacts, fax noise, copy shadows, background patterns
3. **Resolution enhancement**: upscale low-resolution images (faxes typically 200 DPI) to 300+ DPI for better character recognition
4. **Binarization**: convert to high-contrast black/white for cleaner text extraction
5. **CMS-1500 red-ink dropout**: CMS-1500 forms are printed in RED ink with data typed/written in BLACK. Apply red-channel removal to isolate only the data layer. Without this, OCR reads the form labels AND the data, confusing extraction.
6. **Brightness/contrast normalization**: standardize across different scanner settings and paper types

Pre-processing is configurable per document type (skip red-ink dropout for non-CMS-1500 documents).

### 4.20 Multi-Document Fax Bundle Splitting

Fax transmissions frequently bundle multiple documents into a single file:

1. **Page classification**: classify each page individually — CMS-1500 page, UB-04 page, clinical note page, lab result page, cover sheet, blank page
2. **Boundary detection**: identify where one document ends and another begins based on page type transitions and visual markers (new form header, different layout)
3. **Split**: create separate document records for each identified document
4. **Metadata**: record source fax (parent), page range per child document, split confidence
5. **Azure Document Intelligence Custom Classification** model handles this with training on 10+ examples of multi-document faxes
6. **Blank page handling**: detect and discard blank filler pages (common in fax output)

### 4.21 Document Auto-Classification (Pre-Extraction)

Classification happens BEFORE extraction — not after:

1. **Classifier model**: trained on document types relevant to PBM operations:
   - CMS-1500 (professional claim form)
   - UB-04 / CMS-1450 (institutional claim form)
   - EOB (Explanation of Benefits) — per-payer variable format
   - Prior Authorization form (payer-specific)
   - Clinical note / medical record
   - Lab result / pathology report
   - Insurance card (front/back)
   - Prescription / Rx order
   - Appeal letter
   - Audit evidence (signature log, inventory record, prescription copy)
   - Invoice / billing statement
   - Correspondence / cover letter
   - Unknown
2. **Classification confidence**: HIGH → auto-route to correct extraction model; MEDIUM → route with flag; LOW → manual classification queue
3. **Why pre-extraction matters**: CMS-1500 and UB-04 use different extraction models with different field mappings. Misclassification causes silent extraction failures where fields map to wrong locations.

### 4.22 Document Type-Specific Routing

Not every document needs both parsers. Cost and latency optimization:

| Document Type | Primary Parser | Invoke Secondary? | Rationale |
|---|---|---|---|
| CMS-1500 | Azure Doc Intel (custom model) | Only if primary confidence <0.95 on any required field | Highly structured, fixed layout |
| UB-04 | Azure Doc Intel (custom model) | Only if primary confidence <0.95 | Highly structured, fixed layout |
| EOB | Both (always) | Yes — variable format, no standard layout | Each payer different, needs consensus |
| PA form | Both (always) | Yes — semi-structured, payer-specific | Important for PA automation |
| Clinical note | Mistral OCR (primary) | Only if Mistral confidence <0.75 on key fields | Unstructured narrative text |
| Insurance card | Azure Doc Intel (prebuilt model) | Only if primary confidence <0.90 | Azure has prebuilt health insurance card model |
| Lab result | Mistral OCR | Only if confidence <0.80 | Semi-structured, variable format |
| Prescription | Mistral OCR | Only if confidence <0.75 | Handwritten common |

This reduces cost by 40-60% compared to running both parsers on every document.

### 4.23 Per-Field Consensus Scoring Algorithm

When both parsers process a document:

```python
def calculate_consensus(field_name: str, parser_1_result: FieldResult, parser_2_result: FieldResult) -> ConsensusResult:
    p1_val, p1_conf = parser_1_result.value, parser_1_result.confidence
    p2_val, p2_conf = parser_2_result.value, parser_2_result.confidence
    
    # Case 1: Both parsers agree on value
    if normalize(p1_val) == normalize(p2_val):
        return ConsensusResult(
            value=p1_val,
            confidence=max(p1_conf, p2_conf),
            status="AGREED",
            source="consensus"
        )
    
    # Case 2: One parser high confidence, other low
    if p1_conf >= 0.95 and p2_conf < 0.50:
        return ConsensusResult(
            value=p1_val,
            confidence=p1_conf * 0.85,  # discount for disagreement
            status="SINGLE_HIGH_P1",
            source="parser_1_dominant"
        )
    if p2_conf >= 0.95 and p1_conf < 0.50:
        return ConsensusResult(
            value=p2_val,
            confidence=p2_conf * 0.85,
            status="SINGLE_HIGH_P2",
            source="parser_2_dominant"
        )
    
    # Case 3: Both have moderate confidence but disagree
    # → flag for agentic correction layer or human review
    return ConsensusResult(
        value=None,
        confidence=Decimal("0"),
        status="DISAGREED",
        source="needs_review",
        parser_1_value=p1_val,
        parser_2_value=p2_val
    )
```

**Special rules for amount fields**: if both parsers return amounts that differ by exactly a power of 10 (one reads $1,234.56 and other reads $123.46), it's likely a decimal point misread — route to human review with CRITICAL flag.

### 4.24 Adaptive Confidence Thresholds Per Document Type

Configurable per document type, per field category:

| Document Type | Amount Fields | Code Fields (ICD/CPT/NDC) | Name/Address Fields | Date Fields |
|---|---|---|---|---|
| CMS-1500 | 0.95 | 0.95 | 0.90 | 0.95 |
| UB-04 | 0.95 | 0.95 | 0.90 | 0.95 |
| EOB | 0.90 | 0.85 | 0.85 | 0.90 |
| PA form | 0.85 | 0.85 | 0.80 | 0.85 |
| Clinical note | N/A | 0.75 | 0.70 | 0.80 |
| Insurance card | N/A | 0.85 | 0.85 | 0.90 |

- Above threshold: auto-accept
- Within 10% below threshold: flag for quick review (human sees highlighted field, confirms or corrects in <5 seconds)
- More than 10% below threshold: route to full manual review queue

Thresholds configurable per tenant — high-volume tenants may accept lower thresholds for speed; low-volume high-stakes tenants want tighter thresholds.

### 4.25 Cross-Field Dependency Validation

Post-extraction validation that catches errors OCR alone misses:

**CMS-1500 validations:**
- Box 24E diagnosis pointers MUST reference valid ICD-10 codes that exist in Box 21
- Box 24D modifiers MUST be logically consistent with the procedure code and provider type
- Box 33 NPI MUST be valid 10-digit Luhn-checked NPI
- Box 24A dates of service MUST be within reasonable range (not future, not >1 year old)
- Box 28 total charge MUST equal sum of Box 24F line charges

**UB-04 validations:**
- FL42 revenue codes MUST align with FL43 service descriptions per NUBC standard
- FL47 total charges MUST equal sum of line-level charges in FL47
- FL46 service units MUST be consistent with FL42 revenue code (units vs days vs visits)
- Type of Bill (FL4) MUST be valid 4-digit code consistent with the claim type
- Cascading validation: a misread revenue code in one row invalidates the entire row — flag for human review

**Cross-document validations:**
- If processing a claim + supporting clinical note: diagnosis codes on claim should appear in clinical note
- If processing an EOB + original claim: EOB claim number should match a known submitted claim

### 4.26 Agentic Correction Layer

Third-pass LLM review for DISAGREED fields:

1. When consensus scoring returns DISAGREED on a field, invoke the agentic correction agent
2. Agent receives: the source document image (cropped to the relevant region), Parser 1's value + confidence, Parser 2's value + confidence, field type and expected format
3. Agent uses a multimodal LLM (GPT-4.1 Vision or equivalent) to re-examine the source image with focused attention
4. Agent applies domain knowledge: "This field should contain an ICD-10 code. Parser 1 says 'S72.001A' and Parser 2 says 'S72.0O1A'. ICD-10 code S72.001A is valid (femoral neck fracture). S72.0O1A is not a valid code — the 'O' is a misread '0'. Corrected value: S72.001A with HIGH confidence."
5. Agent outputs: corrected value, confidence, reasoning citation
6. If agent is also low-confidence: route to human review with all three attempts visible

Cost control: agentic correction only invoked for DISAGREED fields (typically 2-5% of fields), not every field. Estimated additional cost: $0.01-0.03 per document.

### 4.27 Self-Correction Validation Loops

After initial extraction, run validation loops that catch arithmetic and logical errors:

1. **Total vs line-item sum**: if extracted total ≠ sum of extracted line items, re-examine the differing values. Common cause: OCR misreads one digit in one line item.
2. **Duplicate detection**: two line items with identical procedure code + date + amount → likely a duplicate scan, not two services. Flag for review.
3. **Format validation**: NPI that fails Luhn check → re-examine the digit that, if changed, would make it pass. Often a single-digit misread.
4. **Amount reasonableness**: $12,345.67 for a routine office visit → flag as potentially misread (decimal point in wrong place)
5. **Loop limit**: maximum 2 re-examination passes to prevent infinite correction cycles
6. **Audit**: every correction loop iteration logged with before/after values

### 4.28 Field-Level Correction Audit Trail

Immutable record of every extraction and correction:

```sql
CREATE TABLE ai_nlp.extraction_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_result_id UUID NOT NULL REFERENCES ai_nlp.document_results(id),
    
    field_name VARCHAR(255) NOT NULL,
    
    -- Original extraction
    parser_1_value TEXT,
    parser_1_confidence DECIMAL(5,4),
    parser_2_value TEXT,
    parser_2_confidence DECIMAL(5,4),
    consensus_value TEXT,
    consensus_confidence DECIMAL(5,4),
    consensus_status VARCHAR(50),
    
    -- Agentic correction (if invoked)
    agent_corrected_value TEXT,
    agent_confidence DECIMAL(5,4),
    agent_reasoning TEXT,
    
    -- Self-correction loop (if invoked)
    loop_corrected_value TEXT,
    loop_correction_reason TEXT,
    
    -- Human correction (if reviewed)
    human_corrected_value TEXT,
    corrected_by UUID,
    corrected_at TIMESTAMPTZ,
    
    -- Final value used
    final_value TEXT NOT NULL,
    final_source VARCHAR(50) NOT NULL,  -- consensus, parser_1, parser_2, agent, loop, human
    
    -- Source citation
    source_page INTEGER,
    source_bounding_box JSONB,  -- {x, y, width, height} on the source page
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Every extracted value is traceable from source document → parser outputs → consensus → corrections → final value. Auditors can see exactly what each parser returned and who/what corrected it.

### 4.29 Page-Level Source Citations

Every extracted field includes a citation back to the source document:

1. **Page number**: which page of the multi-page document contains this field
2. **Bounding box**: {x, y, width, height} coordinates of the region on the page where the value was extracted
3. **Source image snippet**: optional — a cropped image of just the extraction region, stored as a reference
4. **Citation format**: stored in document_results.extracted_fields JSON: `{field_name: {value, confidence, page, bounding_box, source_parser}}`
5. **API response**: when returning extraction results, include citations so the UI can highlight the source region on the document image
6. **Audit use**: when a payer questions a submitted value, the system can show exactly where on the original document the value was read from

### 4.30 Paper EOB → 835 Conversion Pipeline

Convert paper/scanned EOBs into standardized 835 EDI format:

1. **EOB extraction**: OCR + dual-parser extraction of: payer name, check/EFT number, payment date, claim-level data (claim number, billed, allowed, paid, patient responsibility, adjustment reason codes, denial codes)
2. **Template-free extraction**: EOBs have NO standard format. Each of 100+ payers designs their own. Use template-free AI extraction (contextual reading, not coordinate-based mapping) to handle any payer format without per-payer template maintenance.
3. **835 mapping**: map extracted fields to 835 segments (BPR, TRN, N1, CLP, SVC, CAS, MOA) per 005010X221A1
4. **Validation**: verify extracted amounts are internally consistent (payment + adjustments + patient responsibility = billed amount)
5. **Output**: generated 835 file → passed to EDI module for standard processing → auto-posted to Billing AR
6. **Accuracy target**: 95%+ auto-conversion rate for clean paper EOBs; remaining 5% flagged for human review

### 4.31 Extracted-Data-to-EDI Auto-Mapping

Bridge between document extraction and EDI generation:

1. **CMS-1500 → 837P**: after OCR extracts structured data from a CMS-1500, auto-map to 837P segments:
   - Box 1-13 → 2010BA/2010BB subscriber/payer loops
   - Box 21 → HI segment (diagnosis codes)
   - Box 24 → 2400 service line loop (CLM, SV1, DTP segments)
   - Box 33 → 2010AA billing provider loop
2. **UB-04 → 837I**: similar mapping for institutional claims with revenue codes, value codes, condition codes
3. **Validation**: run EDI module Level 1-3 validation on the generated 837 before submission
4. **Human review gate**: if any extraction field used in the mapping had confidence < threshold, flag the generated 837 for review before transmission

---

## 5. API Endpoints

```
/api/v1/ai/

# Document Intelligence
POST   /documents/process               Upload + process document (classify, extract)
GET    /documents/{id}/results           Get extraction results
POST   /documents/{id}/retrain           Submit correction (improves future extraction)

# Text Understanding
POST   /text/classify                    Classify text (document type, sentiment, urgency)
POST   /text/extract-entities            Extract named entities from text
POST   /text/summarize                   Summarize long text
POST   /text/compare                     Compare two texts for discrepancies

# Content Generation
POST   /generate                         Generate content from template
GET    /generate/templates               List available templates
POST   /generate/templates               Create custom template
PUT    /generate/templates/{id}          Update template

# Conversational AI
POST   /chat                             Send message to virtual assistant
GET    /chat/sessions                    List chat sessions
GET    /chat/sessions/{id}/messages      Get conversation history
POST   /chat/sessions/{id}/escalate      Escalate to human agent

# Anomaly Narrative
POST   /narrative/anomaly                Generate narrative for flagged claim/entity

# Document Routing
POST   /route/document                   Classify and route a document

# Cost & Usage
GET    /usage                            Usage and cost summary by tenant/period/service
GET    /usage/by-module                  Usage breakdown by requesting module

# Model Management
GET    /models                           List available models
GET    /models/{id}/performance          Model accuracy metrics
```

---

## 6. Events

### Published
- `ai.document_processed` — document classified and extracted
- `ai.content_generated` — content ready for human review
- `ai.confidence_low` — AI output below confidence threshold, needs human review
- `ai.conversation_escalated` — chatbot escalated to human agent
- `ai.document_routed` — document classified and sent to target module

### Consumed
- `fwa.claim_flagged` — generate anomaly narrative
- `fwa.investigation_opened` — generate investigation summary
- Documents uploaded via any module → classify and route

---

## 7. Guardrails & Safety

1. **Every AI output has a confidence score.** Outputs below configurable threshold (default: 0.80) require human review.
2. **No auto-execution of consequential actions.** AI suggests, humans confirm. Generated letters must be approved before sending. Classification must be verified before routing to billing.
3. **PHI handling:** AI services can process PHI (they need to read member data to answer questions). PHI is logged in audit trail. PHI is never stored in AI/NLP tables beyond the service_request record. PHI is never sent to external AI services without encryption in transit.
4. **Prompt injection defense:** user inputs to chatbot are sanitized. System prompts are immutable. User messages are wrapped in explicit delimiters. LLM output is validated against expected format before returning.
5. **Cost controls:** configurable monthly token budget per tenant. Alert at 80%. Soft-block at 100% (admin can override). Prevents runaway costs from a misconfigured integration.
6. **Hallucination prevention:** RAG architecture grounds all responses in actual data. Chatbot responses include citations to source data. Generated content validated against input data (generated PA letter must reference actual member and drug from input).
7. **Bias monitoring:** track AI acceptance/rejection rates by pharmacy type, geography, and demographic indicators. Alert if disparities detected.

---

## 8. Default Implementation

Ships fully functional:

**Document Processing Pipeline:**
- **Document pre-processing** — deskew, denoise, resolution enhancement, binarization, CMS-1500 red-ink dropout
- **Multi-document fax bundle splitting** — page classification, boundary detection, automatic splitting
- **Document auto-classification** — 13 document types classified BEFORE extraction with routing confidence
- **Document type-specific routing** — structured forms → Azure Doc Intel primary; unstructured → Mistral OCR primary; selective second-parser invocation (40-60% cost reduction)
- **Dual-model document intelligence** — Azure Document Intelligence v4.0 + Mistral OCR with per-field consensus scoring algorithm
- **Per-field consensus scoring** — AGREED/SINGLE_HIGH/DISAGREED status with configurable confidence thresholds per document type per field category
- **Adaptive confidence thresholds** — configurable per document type (CMS-1500: 0.95, EOB: 0.90, clinical note: 0.75)
- **Agentic correction layer** — multimodal LLM third-pass review for DISAGREED fields with domain knowledge (drug names, ICD-10 validation)
- **Self-correction validation loops** — total vs line-item sum, format validation, amount reasonableness, duplicate detection
- **Cross-field dependency validation** — CMS-1500 diagnosis pointers, UB-04 revenue code cascading, NPI Luhn checks
- **8 pre-built document type extractors** (CMS-1500, UB-04, EOB, PA form, clinical note, insurance card, audit evidence, appeal letter)
- **Template-free extraction mode** for variable-format documents (EOBs — each payer different layout)
- **Paper EOB → 835 conversion pipeline** — OCR paper EOBs, extract payment data, generate standardized 835 for auto-posting
- **Extracted-data-to-EDI auto-mapping** — CMS-1500 → 837P, UB-04 → 837I automatic field mapping
- **Page-level source citations** — page number + bounding box coordinates on every extracted field
- **Field-level correction audit trail** — immutable record of every parser output, consensus result, correction, and final value

**NLP + Content + Chatbot:**
- **spaCy NLP pipeline** — NER for drugs, diagnoses, procedures, entities. Text classification.
- **7 content generation templates** — PA request, PA appeal, audit demand, investigation summary, member communication, report narrative, corrective action plan
- **RAG-based chatbot** for 4 portal types (pharmacy, member, client, medical)
- **Anomaly narrative generation** — human-readable explanations for ReclaimRx flags
- **NLP auto-coding** — ICD-10 and CPT/HCPCS code suggestions from clinical text
- **Denial prediction** — ML-based PA approval probability before submission
- **Clinical criteria matching** — automated criteria checklist from clinical data vs payer requirements
- **CMS-0057-F FHIR PA support** — FHIR R4 Prior Authorization resource builder and consumer

**Infrastructure:**
- **LLM provider fallback** — Azure OpenAI primary, Anthropic secondary, spaCy degraded mode
- **Human feedback loop** — corrections tracked, accuracy trending, continuous model retraining after 50+ corrections
- **Batch document processing** — queue-based with progress tracking and parallel processing
- **Model version pinning** — test new versions against known-good outputs before switching
- **Response caching** — Redis-backed, configurable TTL, reduces LLM costs 30%+
- **Full audit trail** on every AI call with cost tracking
- **Prompt injection defense** — input sanitization, output validation
- **Cost controls** — configurable monthly budget per tenant

---

## 9. Test Scenarios (100% Coverage Required)

### Critical Paths (100%)
- Document extraction returns correct fields for all 8 document types (against known test documents)
- Dual-model consensus correctly identifies agreements and disagreements
- Confidence scores accurately reflect extraction quality
- Low-confidence outputs routed to human review queue
- Content generation follows template and includes all required patterns
- Content generation rejects prohibited patterns
- Chatbot retrieves correct data from source module APIs
- Chatbot escalates after 2 consecutive low-confidence responses
- PHI appears in audit log but not in application logs
- Prompt injection attempts do not alter system behavior
- Cost tracking accurately counts tokens and estimates cost

### Edge Cases
- Document with zero extractable text (scanned image, poor quality) → returns low confidence, routes to manual
- Chatbot asked about data outside its scope → gracefully declines and suggests human agent
- LLM returns malformed JSON → parsing handles gracefully, flags for retry
- Token budget exceeded → soft-block with admin notification
- Both document models return different results → disagreement fields flagged correctly

---

## 10. Session Decomposition

1. **Document processing pipeline + pre-processing**: document pre-processing (deskew, denoise, enhance, red-ink dropout), multi-document fax bundle splitting (Azure Custom Classification), document auto-classification (13 types), document type-specific routing logic, Azure Document Intelligence v4.0 integration, Mistral OCR integration, per-field consensus scoring algorithm, adaptive confidence thresholds table
2. **Extraction validation + correction + audit**: cross-field dependency validation (CMS-1500 diagnosis pointers, UB-04 revenue code cascading, NPI Luhn), self-correction validation loops (total vs sum, format, reasonableness), agentic correction layer (multimodal LLM third-pass), field-level correction audit trail table, page-level source citations (bounding box storage), 8 document type extractors, template-free extraction mode for EOBs
3. **EOB→835 + OCR→EDI + document intelligence output**: paper EOB → 835 conversion pipeline (template-free extraction + 835 mapping), CMS-1500 → 837P auto-mapping, UB-04 → 837I auto-mapping, human feedback loop (corrections → model retraining trigger), batch document processing queue, document processing metrics and accuracy dashboards
4. **LLM gateway + NLP + chatbot + generation**: Azure OpenAI integration with provider fallback, prompt template system, content generation engine (7 templates), guardrails, model version pinning, response caching, spaCy NLP pipeline (NER, classification), RAG chatbot for 4 portal types, anomaly narrative generator, denial prediction ML model, clinical criteria matching, NLP auto-coding (ICD-10/CPT), CMS-0057-F FHIR PA support, cost tracking
