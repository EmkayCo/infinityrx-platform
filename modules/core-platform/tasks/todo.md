# TODO — core-platform

Tasks tracked here during build.

## Integration (post-merge) — T2 auth-users

- **swap-revoked-repo-redis**: Replace `InMemoryRevokedTokenRepo` with a
  Redis-backed implementation keyed by `revoked:jti:{jti}` with TTL equal
  to each token's remaining lifetime. Referenced from
  `shared/auth/tokens_repo.py` and `src/auth/wiring.py::configure_core_auth`.
- **replace-standin-models**: Delete `src/auth/_models.py` and
  `src/auth/_db.py` once T1's `shared.db.models.core` and
  `shared.db.session.get_session` are available; rewire all imports.
- **audit-sink-to-t3**: Replace `src/auth/audit_sink.py::InMemoryAuditSink`
  with the real `shared.events`-backed sink from T3.

## Integration (post-merge) — T3 events/audit/notifications

- `notifications.sms.wire-provider` — Wire a real SMS provider (Twilio or
  AWS SNS) behind the ``SmsDelivery`` protocol. Today the default is
  ``NoOpSmsDelivery`` — it records but does not send. Owner: T3 follow-up.
  Linked from: ``modules/core-platform/src/notifications/delivery.py``.
- `shared.db.integration-reconcile` — Replace the stand-in SQLAlchemy
  models in ``src/audit/models.py`` and ``src/notifications/models.py``
  with re-exports from ``shared.db.models.core`` once T1 publishes them.
- `shared.auth.integration-reconcile` — Replace the ``AuditContext`` +
  ``current_user`` shims with ``shared.auth.dependencies.get_current_user``
  + ``require_permissions`` from T2.
- `events.rabbitmq.integration-test` — Once docker-compose RabbitMQ is
  reliably available in CI, add a testcontainers[rabbitmq] integration
  test exercising ``RabbitMQEventBus`` publish → ack, retry, DLQ paths.
