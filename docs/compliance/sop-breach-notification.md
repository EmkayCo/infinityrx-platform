# SOP: Breach Notification

**Document ID:** SOP-BN-001  
**HIPAA Reference:** 45 CFR §§164.400–164.414 — Breach Notification Rule  
**Version:** 1.0  
**Effective Date:** 2026-04-14  
**Review Date:** 2026-04-14  
**Owner:** Privacy Officer  
**Approved By:** HIPAA Compliance Committee

---

## 1. Purpose

This SOP establishes the requirements for identifying, investigating, and
notifying affected individuals, HHS, and (where applicable) media outlets
when a breach of unsecured Protected Health Information (PHI) occurs on the
InfinityRx platform. It satisfies 45 CFR §§164.400–164.414.

---

## 2. Definitions

**Breach:** The acquisition, access, use, or disclosure of PHI in a manner
not permitted by the HIPAA Privacy Rule that compromises the security or
privacy of the PHI. 45 CFR §164.402.

**Unsecured PHI:** PHI that has not been rendered unusable, unreadable, or
indecipherable through encryption or destruction per HHS guidance.

**Presumption of Breach:** Any impermissible use or disclosure is presumed
to be a breach unless the covered entity demonstrates a low probability of
compromise using the four-factor risk assessment.

---

## 3. Incident Detection

Breaches may be detected via:
- Automated monitoring (anomalous ePHI access patterns via DataIQ)
- Workforce member reports (via `privacy@infinityrx.com` or HR)
- Security system alerts (intrusion detection, failed login clusters)
- External reports (from patients, providers, or regulators)
- Periodic audit log reviews (daily integrity check per `hipaa-2026.md`)

All potential breaches must be reported to the Privacy Officer within **24 hours**
of detection via:
- Phone: On-call Privacy Officer number (in internal directory)
- Email: `privacy@infinityrx.com` (monitored 24/7 during business hours)
- Slack: `#security-incidents` (monitored by Security team)

---

## 4. Severity Classification

| Level | Criteria | Response SLA |
|---|---|---|
| P1 — Critical | Active exfiltration, confirmed unauthorized access, ≥ 500 individuals, ransomware | Immediate (< 1 hour) |
| P2 — High | Suspected access, < 500 individuals, internal policy violation | < 4 hours |
| P3 — Low | Misdirected PHI (fax, email), minimal exposure, < 10 individuals | < 24 hours |

---

## 5. Four-Factor Risk Assessment

For any potential breach, the Privacy Officer must conduct the four-factor
risk assessment (45 CFR §164.402(2)) to determine the probability of compromise:

1. **Nature and extent of PHI involved:** What types of PHI (e.g., diagnosis,
   financial, SSN)? How sensitive? How much?
2. **Who used or accessed the PHI:** Was the unauthorized person an insider?
   A Business Associate? An unknown external party?
3. **Whether PHI was actually acquired or viewed:** Evidence of access vs.
   mere opportunity for access.
4. **Extent to which risk has been mitigated:** Was data encrypted? Has
   the recipient been contacted? Was the PHI returned or destroyed?

If all four factors indicate low probability of compromise, the incident is
documented as a non-breach. All documentation is retained for 6 years.

---

## 6. Notification Timelines

### 6.1 Affected Individual Notification

- **Deadline:** Without unreasonable delay, and no later than **60 calendar
  days** after discovery of the breach. 45 CFR §164.404(b).
- **Method:** Written notice via first-class mail to the individual's last
  known address. Electronic notice acceptable if individual agreed to electronic
  communications.
- **Content required (45 CFR §164.404(c)):**
  - Brief description of the breach (what happened, date)
  - Types of PHI involved (categories, not specific values)
  - Steps individuals should take to protect themselves
  - Brief description of what InfinityRx is doing to investigate, mitigate,
    and prevent recurrence
  - Contact information (toll-free telephone, email, website, or postal address)

- **Substitute notice:** If contact information is insufficient for ≥ 10
  individuals, post substitute notice prominently on InfinityRx website for
  90 days AND notify major print or broadcast media serving the relevant states.

### 6.2 HHS Secretary Notification

**Breaches affecting ≥ 500 individuals:**
- Notify HHS via the HHS Breach Reporting Portal within **60 calendar days**
  of discovery. 45 CFR §164.408.
- HHS will post notification on the "Wall of Shame" (OCR breach tool).

**Breaches affecting < 500 individuals:**
- Log the breach in the annual breach log.
- Submit to HHS via the Breach Reporting Portal no later than **60 days after
  the end of the calendar year** in which the breach was discovered. 45 CFR §164.408(c).

### 6.3 Media Notification (Breaches Affecting ≥ 500 Residents in a State)

If a breach affects ≥ 500 residents of a single state or jurisdiction:
- Notify prominent media outlets serving that state within **60 calendar days**
  of discovery. 45 CFR §164.406.
- Media notification is in addition to (not instead of) individual notification.
- Coordinate with Legal to draft the media statement before release.

### 6.4 Business Associate Breaches

- If a Business Associate discovers a breach, they must notify InfinityRx
  within **60 days of discovery**. 45 CFR §164.410.
- InfinityRx's 60-day notification clock begins on the BA's discovery date,
  not the date InfinityRx is notified.
- Verify BA notification obligations are included in all BAAs.

---

## 7. Breach Response Procedure

### 7.1 Immediate Containment (Day 0–1)
1. Revoke access for any compromised credentials.
2. Isolate affected systems if active exfiltration is suspected.
3. Preserve evidence (system logs, access logs, email headers).
4. Convene the Incident Response Team (Privacy Officer, CTO, Legal, Security Lead).
5. Notify cyber liability insurance carrier within 24 hours (P1/P2).

### 7.2 Investigation (Day 1–15)
1. Determine the scope: which records, which individuals, what PHI types.
2. Conduct four-factor risk assessment.
3. Document findings in the Breach Investigation Report (template below).
4. Determine if notification is required.

### 7.3 Notification (Day 15–60)
1. Draft individual notification letter (Legal review required).
2. Draft HHS notification form (Legal review required).
3. Send notifications before Day 60.
4. For ≥ 500 in a state: coordinate media notification.

### 7.4 Post-Incident
1. Update risk assessment and security controls.
2. Retrain affected workforce members.
3. Update this SOP if process gaps identified.
4. File the Breach Investigation Report in `docs/compliance/breaches/`.

---

## 8. Breach Investigation Report Template

```markdown
# Breach Investigation Report

**Incident ID:** BREACH-YYYY-NNN
**Discovery date:** 
**Notification deadline:** (discovery date + 60 days)
**Reported by:**
**Privacy Officer:**

## Incident Description

## PHI Involved
- Types:
- Number of individuals affected:
- Date range of PHI:

## Four-Factor Risk Assessment
1. Nature and extent: 
2. Who accessed: 
3. Whether PHI was acquired: 
4. Mitigation extent: 
**Risk probability:** Low / Medium / High
**Breach determination:** YES / NO (with justification)

## Notifications Sent
- Individuals: Date sent, method
- HHS: Date submitted, confirmation number
- Media (if applicable): Outlets, date

## Corrective Actions
- 
```

---

## 9. Annual Breach Summary to HHS

For breaches affecting < 500 individuals:
- Maintain a breach log at `docs/compliance/breaches/annual-log-YYYY.md`.
- Submit to HHS no later than January 31 of the following year.
- Log must include all required elements per 45 CFR §164.408(c).

---

## 10. References

- 45 CFR §§164.400–164.414 — Breach Notification Rule
- 45 CFR §164.404 — Notification to Individuals
- 45 CFR §164.406 — Notification to the Media
- 45 CFR §164.408 — Notification to the Secretary
- 45 CFR §164.410 — Notification by Business Associates
- HHS Breach Reporting Portal: https://ocrportal.hhs.gov/ocr/breach/wizard_breach.jsf
- `docs/compliance/sop-access-control.md`
- `docs/compliance/sop-contingency-plan.md`
- `docs/anti-patterns.md`

---

**Review Date:** 2026-04-14
