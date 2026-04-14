# Financial Precision Rules

## Decimal Only
- MUST use Python `Decimal` for ALL money amounts — no `float`, no int-cents.
- MUST NOT use `float` or `Float` anywhere in models, services, schemas, or events that touch money.
- MUST specify `rounding=ROUND_HALF_UP` on EVERY `.quantize()` call — never rely on default (`ROUND_HALF_EVEN`).
- MUST use `Decimal(str(value))` when converting from external sources — never `Decimal(float_value)`.

## Database
- MUST use `sa.Numeric(x, 2)` or `sa.Numeric(x, 4)` for money columns — never `sa.Float` or `sa.REAL`.
- MUST wrap SQLAlchemy `func.sum()` / `func.avg()` results in `Decimal(str(result))` — SA returns float for aggregates.

## Penny Allocation
- MUST use `shared/utils/money.py` `penny_allocate()` for ALL amount splits — no module-local copies.
- MUST verify `sum(split_amounts) == original_amount` in unit tests for every split operation.

## Batch Totals
- MUST compute batch/invoice totals as sum of components — never calculate independently.
- MUST verify `batch_total == sum(payment_amounts)` with a test for every batch generation path.

## Events
- MUST serialize `Decimal` amounts as `str()` in event payloads — never publish float dollar amounts.
- MUST deserialize with `Decimal(payload["amount"])` on the consumer side.

## Pre-commit
- MUST reject commits containing `float`/`Float` in any file under `*/services/` or `*/models/` that touches money.
