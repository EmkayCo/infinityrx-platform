# Event Contract: `paysync.upload.parsed`

**Schema version:** 1.0
**Status:** Active

---

## Description

An operator-submitted claim CSV/XLSX upload has finished parsing and persisting
in the billing module. The terminal upload `status` is one of:

- `validated` — at least one row parsed cleanly; corresponding `ClaimRecord`
  rows have been written with `upload_id` set
- `validation_failed` — all rows rejected; `row_errors` populated on the
  Upload, no `ClaimRecord` rows written

Consumers should refresh any cached inbox/cycle views that may include this
upload.

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `upload_id` | `str (UUID)` | yes | Upload row id (matches `Upload.id`) |
| `tenant_id` | `str (UUID)` | yes | Tenant that owns this upload |
| `status` | `str` | yes | Terminal status: `validated` or `validation_failed` |
| `row_count` | `int` | yes | Total rows seen in the file |
| `error_count` | `int` | yes | Rows rejected by `validate_row` |

Consumers MUST ignore unknown payload fields (forward compatibility).

---

## Publishers

| Module | Condition |
|--------|-----------|
| `billing` | After `POST /api/v1/billing/uploads` or `POST /api/v1/billing/uploads/{id}/supersede` commits |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `billing` | `handle_upload_parsed` | Invalidate Redis keys matching `paysync:inbox:list:{tenant_id}:*` |

---

## Ordering Key Convention

**`ordering_key`:** `upload_id` (per-upload ordering — supersede produces a
distinct new upload, so its event is independently ordered)

## Idempotency Key Convention

**`idempotency_key`:** `paysync:upload:{upload_id}:parsed`

Each upload publishes exactly one `paysync.upload.parsed`; re-delivery is a
no-op via `@idempotent_handler`.

---

## Example Payload

```json
{
  "event_type": "paysync.upload.parsed",
  "schema_version": "1.0",
  "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  "correlation_id": "...",
  "source_module": "billing",
  "ordering_key": "dddddddd-dddd-dddd-dddd-dddddddddddd",
  "idempotency_key": "paysync:upload:dddddddd-dddd-dddd-dddd-dddddddddddd:parsed",
  "payload": {
    "upload_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
    "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "status": "validated",
    "row_count": 100,
    "error_count": 0
  }
}
```
