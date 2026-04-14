# ADR-005: Dual-mode event bus (RabbitMQ / InMemory)

**Status:** Accepted
**Date:** 2026-04-14
**Deciders:** Platform architecture

## Context

InfinityRx modules communicate asynchronously via published events. The
production event bus uses RabbitMQ (local development) and Azure Service Bus
(production cloud deployment). Testing requires a fast, deterministic bus
that does not need external infrastructure.

Three problems existed at audit date:

1. **No event bus E2E tests** — all 13 modules had consumer `CONSUMER_ROUTING`
   dicts but none called `bus.subscribe()` at startup. Handlers were dead code
   in production (audit CR-01). This was the LESSON-006 pattern repeating at
   the cross-module layer.

2. **Duplicate EventBus Protocol definitions** — billing and edi-compliance
   each defined their own local `EventBus` Protocol instead of using
   `shared.events.bus.EventBus` ABC (audit H-02).

3. **No migration path** — the platform will move from RabbitMQ to Azure
   Service Bus in production but there was no strategy for testing the
   transition.

## Decision

### Two concrete bus implementations

1. **`RabbitMQEventBus`** (`shared/events/rabbitmq_bus.py`)
   - Used in production (local dev) and integration tests with live RabbitMQ.
   - Wraps `aio-pika`. Implements `EventEnvelope` serialization, DLQ routing,
     and idempotency store.

2. **`InMemoryEventBus`** (`shared/events/in_memory_bus.py`)
   - Used in unit tests. Zero external dependencies.
   - Stores published envelopes in `self._published: list[EventEnvelope]`.
   - Subscribers can be registered and driven synchronously.
   - Supports `assert_published(event_type, ...)` for test assertions.

Both implement the same `EventBus` ABC (`shared/events/bus.py`):
```python
class EventBus(ABC):
    @abstractmethod
    async def publish(self, envelope: EventEnvelope) -> None: ...
    @abstractmethod
    async def subscribe(self, event_type: str, handler: EventHandler) -> None: ...
```

### Module wiring rule

Every module's `lifespan` (or startup event) MUST call `bus.subscribe()` for
each entry in `CONSUMER_ROUTING`. The `InMemoryEventBus` enables this to be
tested without RabbitMQ:

```python
@pytest.fixture()
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()

async def test_claim_flagged_handler_triggered(bus):
    await setup_subscriptions(bus)
    await bus.publish(make_envelope("fwa.claim_flagged", {...}))
    await bus.drain()
    assert bus.count_handled("fwa.claim_flagged") == 1
```

### Azure Service Bus migration path

When the platform migrates to Azure Service Bus in production:
1. Implement `AzureServiceBusEventBus` in `shared/events/azure_bus.py`.
2. `lifespan` selects implementation based on `settings.EVENT_BUS_PROVIDER`:
   `rabbitmq` (default) | `azure_service_bus` | `in_memory` (test only).
3. No consumer handler code changes required — the ABC isolates them.
4. Integration tests run against both providers using
   `@pytest.mark.parametrize("bus_impl", [rabbitmq_bus, azure_bus])`.

### Idempotency

- Every consumer handler MUST be wrapped with `@idempotent_handler` from
  `shared/events/idempotency.py`.
- Idempotency store: `ProcessedEvent` table in PostgreSQL (`processed_at`,
  `consumer_name`, `idempotency_key`).
- Cleanup job: `DELETE FROM processed_events WHERE processed_at < NOW() - INTERVAL '7 days'`
  scheduled via the jobs subsystem (event-bus rule in `.claude/rules/event-bus.md`).

---

## Alternatives considered

1. **Single RabbitMQ bus everywhere, use Docker for tests.** Rejected: Docker
   startup adds 10–30 seconds to every test run. The InMemory bus enables
   sub-second unit test feedback loops.

2. **Mock the bus at the function level.** Rejected: `unittest.mock.patch`
   of `bus.publish` bypasses the `EventEnvelope` validation, `idempotency_key`
   enforcement, and `ordering_key` requirements. The InMemoryEventBus is
   behaviorally correct, not a mock.

3. **Keep both RabbitMQ and Azure Service Bus at all times.** Rejected: adds
   dual-broker operational complexity. The adapter pattern allows a clean
   cut-over rather than maintaining two live brokers.

## Consequences

**Positive:**
- Unit tests have no external dependencies.
- E2E consumer tests are trivially written: publish → assert handled.
- Azure migration is a configuration change, not a code change.
- The InMemoryEventBus catches idempotency bugs before they reach production.

**Negative:**
- InMemoryEventBus does not reproduce RabbitMQ's message ordering or
  dead-letter behavior exactly — integration tests on live RabbitMQ remain
  required for these edge cases.
- Adding `AzureServiceBusEventBus` requires testing against real Azure
  Service Bus in CI; requires an Azure subscription in the test environment.

## Cross-references

- Audit CR-01 — consumers not subscribed at startup (5 of 6 flows broken)
- Audit H-02 — local EventBus Protocol definitions (billing, edi-compliance)
- Audit M-18 — zero cross-module event-bus E2E tests
- `shared/events/bus.py` — EventBus ABC
- `shared/events/in_memory_bus.py` — InMemoryEventBus
- `shared/events/idempotency.py` — idempotent_handler decorator
- `.claude/rules/event-bus.md` — event bus coding rules
