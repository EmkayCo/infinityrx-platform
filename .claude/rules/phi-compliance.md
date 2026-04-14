# PHI Compliance Rules

## Encryption
- MUST use `EncryptedString` (`shared/crypto/sqlalchemy_types.py`) for ALL PHI database columns: name, DOB, SSN, address, phone, email.
- MUST use `PHIMixin` (`shared/db/models/phi_mixin.py`) for any model containing patient/member data.
- MUST use tenant-scoped AAD (Additional Authenticated Data) — cross-tenant ciphertext must fail decryption.

## Logging
- MUST NOT log PHI fields (`member_name`, `date_of_birth`, `ssn`, `address`, `phone`, `email`) at ANY log level.
- MUST NOT include PHI in error messages, exception messages, or stack trace context.
- MUST NOT include PHI in event bus payloads unless encrypted.

## Access Logging
- MUST log every PHI access (read) as a separate audit entry with `action="phi_access"`.
- MUST include `user_id`, `tenant_id`, `entity_type`, `entity_id` in PHI access audit entries.

## API Responses
- MUST include `Cache-Control: no-store` header on every response containing PHI.
- MUST mask PHI in API responses based on user's PHI access level (`full`, `partial`, `redacted`).

## Reports
- MUST watermark PDF reports containing PHI with "CONFIDENTIAL — CONTAINS PHI".
- MUST log every report download/view containing PHI.
