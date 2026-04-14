# Error Handling Rules

## Response Format
All API errors MUST return:
```json
{"error": {"code": "ERROR_CODE", "message": "Human readable message", "field": "field_name_if_applicable", "correlation_id": "uuid"}}
```

## HTTP Status Codes
- `400`: validation error, bad request format.
- `401`: authentication failed (expired/invalid token, missing credentials).
- `403`: authorization failed (valid auth but insufficient permissions, wrong tenant).
- `404`: resource not found.
- `409`: conflict (duplicate, concurrent operation).
- `422`: unprocessable entity (valid format but business rule violation).
- `429`: rate limit exceeded (include `Retry-After` header).
- `500`: unexpected server error (log full stack trace, return generic message to client).

## Internal Errors
- MUST log full exception with stack trace at ERROR level for 500s.
- MUST NOT expose stack traces, internal paths, or database errors to API consumers.
- MUST include `correlation_id` in every error log entry for tracing.
