# Security Rules

## Authentication
- MUST enforce MFA check in every login flow — never issue JWT without MFA verification when `tenant.mfa_required` is true.
- MUST use FIDO2 `UserVerificationRequirement.REQUIRED`, never `PREFERRED` (HIPAA 2026).
- MUST store API keys as SHA-256 hash, never plaintext.
- MUST use constant-time comparison for all secret/token/key validation.

## Input Validation
- MUST validate all request bodies via Pydantic models — no raw `request.json()` parsing.
- MUST use `\A...\Z` anchors or `re.fullmatch()` for security-sensitive regex — `re.match` with `^...$` accepts trailing newlines (LESSON-004).
- MUST validate NPI with Luhn check (prefix 80840), NDC as 11 digits, phone as E.164, email via Pydantic `EmailStr`.

## Secrets
- MUST NOT hardcode secrets, keys, passwords, or tokens in source code.
- MUST NOT log secrets, tokens, or API keys at any log level.
- MUST load secrets from environment variables or vault references.

## Middleware
- MUST mount `SecurityHeadersMiddleware` and `RateLimitMiddleware` on every production FastAPI app — not just in test fixtures.
- MUST mount DLQ router on production app.

## Dependencies
- MUST run `pip-audit` before every release.
- MUST NOT merge code with known critical CVEs in dependencies.
