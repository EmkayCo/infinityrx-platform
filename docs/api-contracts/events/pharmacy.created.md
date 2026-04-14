# pharmacy.created

Published when a new pharmacy record is inserted into the directory.

## Payload

```json
{
  "pharmacy_id": "uuid",
  "npi": "string(10)",
  "nabp_number": "string(7) | null",
  "display_name": "string",
  "pharmacy_type": "string",
  "city": "string",
  "state": "string(2)"
}
```

## Producer

`pharmacy-directory` — `src/events/publisher.py:publish_pharmacy_created`

## Schema Version

`1.0`
