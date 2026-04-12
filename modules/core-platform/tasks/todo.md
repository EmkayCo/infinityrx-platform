# TODO — core-platform

Tasks tracked here during build.

## Open

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
