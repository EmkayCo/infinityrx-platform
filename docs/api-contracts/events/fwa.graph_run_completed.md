# Event Contract: `fwa.graph_run_completed`

**Schema version:** 1.0
**Status:** Active

---

## Description

A graph analysis run has completed (successfully, partially, or with failure).
Published via transactional outbox by the reclaimrx graph analysis job when the
run reaches a terminal state. Downstream consumers use this event to trigger ML
retraining feeds, update dashboards, and alert on detected fraud rings.

---

## Envelope Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_type` | `string` | yes | `"fwa.graph_run_completed"` |
| `schema_version` | `string` | yes | `"1.0"` |
| `tenant_id` | `UUID` | yes | Tenant context — envelope-level |
| `ordering_key` | `string` | yes | `graph_run_id` |
| `idempotency_key` | `string` | yes | `"graph_run:{graph_run_id}:completed"` |

---

## Payload Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `graph_run_id` | `UUID` | yes | The completed run |
| `status` | `"completed" \| "completed_partial" \| "failed"` | yes | Terminal status |
| `rings_detected` | `int` | yes | Count of fraud rings detected; 0 if `status=failed` |
| `investigations_opened` | `int` | yes | Auto-opened investigations; 0 if `status=failed` |
| `records_scanned` | `int` | yes | Records scanned; 0 if failed before scan began |
| `lookback_window_days` | `int` | yes | Lookback window used for this run |
| `started_at` | `string (ISO-8601)` | yes | Run start timestamp |
| `completed_at` | `string (ISO-8601) \| null` | yes | Completion timestamp; `null` if `status=failed` |
| `failed_at` | `string (ISO-8601) \| null` | yes | Failure timestamp; set when `status=failed` |
| `error_code` | `string \| null` | yes | Machine-readable error code; set when `status=failed` |
| `error_message` | `string \| null` | yes | Sanitized human-readable message; set when `status=failed` |

---

## Forward Compatibility

Consumers MUST ignore unknown fields. New fields added in 1.x are non-breaking.
Never reject a message solely because an unrecognized field is present.

---

## Publishers

| Module | Condition |
|--------|-----------|
| `reclaimrx` | Graph analysis job — transactional outbox publish when run reaches terminal state |

## Consumers

| Module | Handler | Action |
|--------|---------|--------|
| `reporting` | `handle_fwa_graph_run_completed` | Refresh graph-run dashboard tile |
| *(future)* | *(ML retraining feed)* | Trigger model retraining on new ring data |

---

## Ordering Key Convention

**`ordering_key`:** `graph_run_id`

Each run is independent; per-run ordering guarantees that status updates for the
same run (e.g., partial completion events) are consumed in sequence.

## Idempotency Key Convention

**`idempotency_key`:** `graph_run:{graph_run_id}:completed`

Consumer wraps handler with `idempotent_handler` decorator. A run can only
complete once; duplicate deliveries replay safely without re-processing.

---

## Example Payload — Successful Run

```json
{
  "event_type": "fwa.graph_run_completed",
  "schema_version": "1.0",
  "tenant_id": "11111111-0000-0000-0000-000000000001",
  "ordering_key": "44444444-0000-0000-0000-000000000007",
  "idempotency_key": "graph_run:44444444-0000-0000-0000-000000000007:completed",
  "graph_run_id": "44444444-0000-0000-0000-000000000007",
  "status": "completed",
  "rings_detected": 3,
  "investigations_opened": 2,
  "records_scanned": 48920,
  "lookback_window_days": 90,
  "started_at": "2026-05-18T03:00:00Z",
  "completed_at": "2026-05-18T03:12:34Z",
  "failed_at": null,
  "error_code": null,
  "error_message": null
}
```

## Example Payload — Failed Run

```json
{
  "event_type": "fwa.graph_run_completed",
  "schema_version": "1.0",
  "tenant_id": "11111111-0000-0000-0000-000000000001",
  "ordering_key": "44444444-0000-0000-0000-000000000008",
  "idempotency_key": "graph_run:44444444-0000-0000-0000-000000000008:completed",
  "graph_run_id": "44444444-0000-0000-0000-000000000008",
  "status": "failed",
  "rings_detected": 0,
  "investigations_opened": 0,
  "records_scanned": 0,
  "lookback_window_days": 90,
  "started_at": "2026-05-18T03:00:00Z",
  "completed_at": null,
  "failed_at": "2026-05-18T03:01:02Z",
  "error_code": "GRAPH_BUILD_TIMEOUT",
  "error_message": "Graph construction exceeded maximum allowed duration"
}
```

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-05-18 | Initial contract — SP-3 Plan A (R1 BLOCK 3) |
