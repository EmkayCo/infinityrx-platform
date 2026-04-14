# SOP: Backup and 72-Hour Restoration

**Scope:** All PHI-bearing databases in the InfinityRx platform.
**Owner:** Platform SRE / DBA.
**HIPAA citation:** §164.308(a)(7)(ii)(A)-(D) — contingency plan, data
backup, disaster recovery, emergency-mode operation.

## Why this SOP exists

HIPAA 2026 requires that any covered entity demonstrate the ability to
restore an exact copy of electronic protected health information from a
backup within 72 hours of a destructive incident. This SOP documents the
backup schedule, the restore procedure, and — critically — the proof
that the restore actually works. "Untested backup" is not a backup.

## Backup cadence

| Target | Tool | Frequency | Retention |
|---|---|---|---|
| Postgres (all schemas) | `infrastructure/scripts/backup.sh` | every 4 hours | 30 days hot, 7 years cold |
| WAL archive | `pg_wal_archive` → S3/Azure Blob | continuous | 14 days |
| Redis (MFA challenges, rate buckets) | RDB snapshot every hour | hourly | 7 days |
| RabbitMQ (DLQ) | JSON dump of queue metadata | every 15 minutes | 14 days |
| Object storage (uploaded files) | cross-region replication | real-time | 7 years |

Only Postgres requires PITR capability. Redis and RabbitMQ backups are
operational conveniences — they MUST NOT be the source of truth for any
PHI or financial data.

## Backup encryption

- Postgres dumps are encrypted at rest with AES-256-GCM. The key lives
  in the platform's HSM-backed key vault, not in the object store.
- The backup script refuses to run if `ENCRYPTION_KEY_ACTIVE` is not
  set in the environment.
- Backup files are tagged `encrypted=true` in the object store manifest
  so restore tooling can verify before decryption.

## Restore procedure (production incident)

1. Declare the incident in the status channel. Record the timestamp.
2. Pause writes: put the app in read-only mode by setting
   `PLATFORM_READ_ONLY=true` in the deployment config and rolling.
3. Identify the target recovery point. Check
   `infrastructure/scripts/tests/` for the most recent successful
   restore test result — the recovery window is bounded by that proof,
   not by the backup frequency alone.
4. Run `infrastructure/scripts/restore.sh --target <recovery-point>`.
   The script:
   a. Allocates a fresh Postgres instance in a quarantine subnet.
   b. Downloads the base backup + WAL segments up to the target.
   c. Decrypts with the vault key.
   d. Runs `pg_restore` with `--single-transaction --no-owner
      --no-privileges`.
   e. Runs `verify_backup.py` — see "Verification" below.
5. Wire the restored instance to the application by flipping the
   `DATABASE_URL` secret. Roll deployments.
6. Exit read-only mode.
7. File the incident post-mortem within 24 hours.

## Verification (`verify_backup.py`)

The verifier runs a fixed set of queries against the restored database
and MUST all pass before the backup is considered usable:

- **Row counts** per tenant match the manifest dumped at backup time
  (±0 rows; exact match).
- **Hash chain** unbroken for every tenant's audit log (runs
  `compute_entry_hash` on each row and chains previous→current).
- **Encryption roundtrip** — decrypt 10 random PHI rows per tenant
  successfully using the active key.
- **Referential integrity** — every foreign key resolves; no orphaned
  child rows.
- **Sanity**: `SELECT 1` on every schema, NOT a single one uses
  `public` (the platform refuses to run with PHI in the default schema).

A failed verifier aborts the restore and the incident escalates.

## Proof-of-Readiness test (weekly)

Every Monday at 02:00 UTC a scheduled job in CI:

1. Snapshots the most recent backup.
2. Restores it into an ephemeral Postgres container (testcontainers).
3. Runs `verify_backup.py` against the restored instance.
4. Records `pass/fail` with the duration in
   `infrastructure/scripts/tests/restore_evidence/YYYY-MM-DD.json`.

A missing or stale evidence file means we CANNOT claim the 72-hour
restoration requirement. The monthly compliance review reads this
directory and flags any week without a successful restore proof.

**Recent evidence:** see `infrastructure/scripts/tests/restore_evidence/`
for timestamps and outcomes.

## Runbook for tenant-specific restores

A single-tenant restore (e.g., accidentally deleted data for tenant X)
does NOT require a full-cluster restore:

1. Mount the latest backup read-only in the quarantine subnet.
2. `pg_dump --schema-only core` plus `pg_dump --data-only -t <table>
   --where "tenant_id = '<uuid>'"` for each affected table.
3. Re-apply into the production cluster inside a single transaction
   with the tenant's row IDs still held out of the UI.
4. Re-verify hash chain continuity for the tenant (any surgical insert
   invalidates `entry_hash` linkage — the chain must be re-computed
   from GENESIS for the affected rows).
5. Audit log the operation with `action="tenant.restored"` and the
   incident ID in `correlation_id`.

## What is NOT backed up

- The Redis `processed_events` table (idempotency keys). Loss simply
  means a few events might be delivered twice — consumers are
  idempotent by contract.
- In-memory rate-limit state (it's in-memory and ephemeral by design).
- Ephemeral test databases, worktree branches.

## Related files

- `infrastructure/scripts/backup.sh` — executes the backup
- `infrastructure/scripts/restore.sh` — executes the restore
- `infrastructure/scripts/verify_backup.py` — verifier
- `infrastructure/scripts/tests/` — evidence directory
- `.claude/rules/hipaa-2026.md` — regulatory citation and scope
