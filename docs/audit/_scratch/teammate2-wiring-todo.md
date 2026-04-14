# Teammate 2 → Teammate 1 Wiring TODO

These items require Teammate 1 (main.py owner) to add the `wire_consumers()` call
to each module's lifespan. Teammate 2 has written the `wire_consumers()` helper
in each module's `src/events/__init__.py`.

## Modules Requiring Lifespan Hook Addition

### 1. billing — `modules/billing/src/main.py`
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
await wire_consumers(bus)
```

### 2. reclaimrx — `modules/reclaimrx/src/main.py` (or app.py)
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
await wire_consumers(bus)
```

### 3. payment-processing — `modules/payment-processing/src/app.py`
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
await wire_consumers(bus)
```

### 4. ai-nlp — `modules/ai-nlp/src/app.py` (or main.py)
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
# Requires openai_client and db_factory from app state:
await wire_consumers(bus, openai_client=app.state.openai_client, db_factory=get_db_session)
```

### 5. reporting — `modules/reporting/src/app.py` (or main.py)
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
await wire_consumers(bus)
```

### 6. dataiq — `modules/dataiq/src/app.py` (or main.py)
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
# Requires redis client from app state:
await wire_consumers(bus, redis=app.state.redis)
```

### 7. medical-claims — `modules/medical-claims/src/app.py` (or main.py)
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
# Requires service instances:
await wire_consumers(
    bus,
    claim_service=app.state.claim_service,
    unified_spend_service=app.state.unified_spend_service,
    db=app.state.db,
)
```

### 8. edi-compliance — `modules/edi-compliance/src/main.py`
```python
from src.events import wire_consumers
# In lifespan, after bus.start():
await wire_consumers(bus)  # no-op currently (publisher-only module)
```

## Reference Pattern

See `modules/pharmacy-directory/src/app.py` lifespan for the reference wiring pattern:
```python
bus = get_event_bus()
await bus.start()
await bus.subscribe("fwa.credentialing_risk_elevated", handle_fwa_credentialing_risk_elevated)
await bus.subscribe("fwa.pharmacy_risk_elevated", handle_fwa_pharmacy_risk_elevated)
```

## Notes
- wire_consumers() helpers are idempotent — safe to call multiple times.
- Each module uses InMemoryIdempotencyStore by default; swap for PostgresIdempotencyStore
  at production startup with a real DB engine.
- billing/src/main.py is 18 lines with no lifespan — Teammate 1 needs to add a proper
  lifespan function first (CR-07).
