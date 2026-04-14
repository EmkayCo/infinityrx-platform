# SOP: Access Control

**Document ID:** SOP-AC-001  
**HIPAA Reference:** 45 CFR §164.308(a)(4) — Access Control; §164.312(a)(1) — Unique User Identification  
**Version:** 1.0  
**Effective Date:** 2026-04-14  
**Review Date:** 2026-04-14  
**Owner:** Chief Security Officer / Privacy Officer  
**Approved By:** HIPAA Compliance Committee

---

## 1. Purpose

This Standard Operating Procedure establishes the requirements for controlling
access to electronic Protected Health Information (ePHI) on the InfinityRx
platform. It implements the HIPAA Security Rule's Access Control standard
(§164.308(a)(4)) and satisfies the 2026 HIPAA Final Rule requirements for
multi-factor authentication (MFA) on all ePHI access paths.

---

## 2. Scope

This SOP applies to:
- All workforce members accessing the InfinityRx platform (employees, contractors, vendors)
- All system components that store, process, or transmit ePHI
- All API clients, service accounts, and automated processes

---

## 3. Role Definitions (RBAC)

InfinityRx implements role-based access control enforced at the API and
database layers via `TenantScopedMixin` and JWT claims. The following roles
are defined:

| Role | Description | ePHI Access | Financial Access |
|---|---|---|---|
| `super_admin` | Platform-level administration (InfinityRx staff only) | Full | Full |
| `tenant_admin` | Tenant administrator; manages users and configuration | Masked | Full |
| `pharmacist` | Licensed pharmacist reviewing claims | Full (job-related) | None |
| `claims_analyst` | Claims review and adjudication support | Partial (masked) | None |
| `billing_analyst` | Billing and AR management | None | Full |
| `fwa_investigator` | Fraud investigation specialist | Full | Partial |
| `reporting_analyst` | Dashboard and report access | Redacted | Aggregated only |
| `auditor` | Read-only audit log access | None | None |
| `api_client` | Programmatic access (API key bearer) | Per-scope | Per-scope |
| `member` | Member self-service portal | Own PHI only | None |

PHI access levels: `full` = unmasked; `partial` = masked SSN, DOB; `redacted` = no PHI fields.

---

## 4. Access Provisioning

### 4.1 New User Onboarding
1. Requesting manager submits access request via IT ticketing system with:
   - Justification of business need
   - Role requested
   - Supervised or privileged access flag if applicable
2. HIPAA Privacy Officer reviews and approves within 2 business days.
3. IT provisions account with minimum-necessary role assignment.
4. User completes HIPAA training (see `sop-workforce-training.md`) before account activation.
5. User enrolls in MFA before first login (TOTP via `pyotp` or FIDO2 hardware key).
   - SMS-based MFA is **not accepted** per HIPAA 2026 Final Rule.
   - FIDO2 `UserVerificationRequirement.REQUIRED` (not PREFERRED) per `shared/auth/mfa/`.

### 4.2 Role Assignment Changes
- Changes require the same approval as new access provisioning.
- Privilege escalation (any move toward higher ePHI access) requires Privacy Officer sign-off.
- Changes are effective within one business day of approval.

### 4.3 Third-Party and Vendor Access
- Vendors require a signed Business Associate Agreement (BAA) before any access.
- Vendor accounts are provisioned as `api_client` with the narrowest scope sufficient.
- All vendor API keys are stored as SHA-256 hashes (`shared/auth/api_keys/service.py`).
- Vendor access is reviewed quarterly.

---

## 5. Access Review

### 5.1 Quarterly Access Review
The Privacy Officer conducts a quarterly review of all user accounts:
1. Export current user list with roles from Admin API (`GET /admin/users`).
2. Send to department heads for attestation of "need this access" for each user.
3. Department heads return attestation within 10 business days.
4. Revoke access for any unattested accounts or users who have left the organization.
5. Document review in `docs/compliance/access-reviews/YYYY-QQ-attestation.md`.

### 5.2 Immediate Revocation Triggers
The following events trigger same-day access revocation:
- Employment termination (any type)
- Role change reducing scope
- Security incident implicating the account
- Compromise or suspected compromise of credentials

---

## 6. Break-Glass Procedure

Break-glass access provides emergency access to ePHI beyond normal role boundaries.

### 6.1 When to Use
- Patient safety emergency requiring immediate record access
- System outage preventing normal access for critical operations
- Law enforcement request with proper legal process

### 6.2 Process
1. Requestor contacts on-call Privacy Officer by phone (not email).
2. Privacy Officer verbally authorizes and documents the reason.
3. IT provisions time-limited elevated access (maximum 4 hours).
4. All break-glass access is automatically logged to the tamper-evident audit chain
   with `action="break_glass_access"`.
5. Privacy Officer reviews the break-glass audit entries within 24 hours.
6. A post-use report is filed within 5 business days documenting:
   - Who used break-glass access
   - What ePHI was accessed
   - Business justification
   - Whether access was appropriate

---

## 7. Session Controls

Per HIPAA 2026 and `shared/auth/sessions/service.py`:
- Automatic session timeout: 15 minutes of inactivity (configurable per tenant).
- Maximum concurrent sessions per user: 5.
- Session tokens expire after 60 minutes (configurable).
- Session revocation on password change or MFA change.

---

## 8. Attestation Requirements

All workforce members with ePHI access must complete annual attestation confirming:
- They understand their role-based access restrictions.
- They will not access ePHI beyond their minimum-necessary scope.
- They will report suspected unauthorized access immediately.

Attestation records are retained for 6 years per §164.316(b)(2).

---

## 9. Monitoring and Enforcement

- All ePHI access (read) is logged with `action="phi_access"` per `phi-compliance.md`.
- The audit hash chain (`shared/crypto/hash_chain.py`) prevents tampering.
- Anomalous access patterns trigger alerts via the DataIQ monitoring module.
- Policy violations are subject to workforce sanctions per the Sanctions Policy.

---

## 10. References

- 45 CFR §164.308(a)(4) — Information Access Management
- 45 CFR §164.312(a)(1) — Access Control
- 45 CFR §164.312(d) — Person or Entity Authentication
- NIST SP 800-63B — Digital Identity Guidelines (Authentication)
- `shared/auth/mfa/` — TOTP and FIDO2 implementation
- `shared/auth/api_keys/` — API key hashing
- `modules/core-platform/src/auth/` — Auth service implementation
- `docs/compliance/sop-workforce-training.md`
- `docs/compliance/sop-breach-notification.md`

---

**Review Date:** 2026-04-14
