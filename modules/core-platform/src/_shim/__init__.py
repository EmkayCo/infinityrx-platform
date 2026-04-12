"""Local shim for dependencies owned by teammates T1-T3.

This module provides minimal, test-friendly implementations of:
- shared.db        (Base, get_session, tenant_context)
- shared.auth      (current_user dependency, roles)
- shared.events    (publish)
- shared.config    (settings)
- shared.notifications (NotificationService)

When the real shared packages are wired up, swap imports from
`src._shim` to `shared.*`. This shim is the only concession to the
empty shared/ scaffolding in the worktree and is documented as an
integration contract in the report.
"""
