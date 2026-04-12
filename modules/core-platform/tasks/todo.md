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
