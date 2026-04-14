# SOP: Contingency Plan

**Document ID:** SOP-CP-001  
**HIPAA Reference:** 45 CFR §164.308(a)(7) — Contingency Plan  
**Version:** 1.0  
**Effective Date:** 2026-04-14  
**Review Date:** 2026-04-14  
**Owner:** Chief Technology Officer / Privacy Officer  
**Approved By:** HIPAA Compliance Committee

---

## 1. Purpose

This Contingency Plan SOP establishes the requirements for maintaining
continuity of operations and protecting ePHI during system failures,
disasters, or other emergencies. It satisfies 45 CFR §164.308(a)(7),
which requires covered entities to establish policies for data backup,
disaster recovery, and emergency mode operation.

---

## 2. Scope

Covers all systems that store, process, or transmit ePHI:
- PostgreSQL database cluster (all module schemas)
- Redis cache (session tokens, challenge store, reclaimrx cache)
- RabbitMQ / Azure Service Bus (event bus)
- Azure Blob Storage (file uploads, report outputs)
- AKS Kubernetes cluster (production services)

---

## 3. Recovery Objectives

| Objective | Target |
|---|---|
| Recovery Point Objective (RPO) | ≤ 4 hours — no more than 4 hours of data loss |
| Recovery Time Objective (RTO) | ≤ 72 hours — system fully operational within 72 hours |
| Maximum Tolerable Downtime | 72 hours (HIPAA §164.308(a)(7) requirement) |
| Backup Frequency | Every 4 hours for PostgreSQL; real-time replication for Redis |

---

## 4. Backup Procedure

Reference: `docs/sops/backup-restore.md` for full implementation details.

### 4.1 PostgreSQL Backups

- **Automated:** Backup script at `infrastructure/scripts/backup.sh` runs
  every 4 hours via AKS CronJob (production) or host cron (development).
- **Storage:** Encrypted with AES-256 before upload to Azure Blob Storage
  (`infinityrx-backups` container, immutable storage policy).
- **Retention:** 30 daily backups, 12 monthly backups, 7 years for PHI data
  (per HIPAA §164.316(b)(2) and state retention laws).
- **Verification:** Every backup file is verified with `pg_restore --list`
  within 1 hour of creation. Failed verification triggers an alert.

### 4.2 Application Configuration Backups

- Kubernetes manifests and Terraform state are version-controlled in git.
- Secrets (Key Vault references) are backed up separately to a secondary
  Key Vault in a paired Azure region.
- Environment configuration (non-secret) is backed up with application code.

### 4.3 Redis Backup

- Redis AOF (Append-Only File) persistence enabled; snapshotted every hour.
- Sessions and rate-limit state are considered ephemeral; only the AOF
  for reclaimrx cache and DLQ state require restore.

---

## 5. Disaster Recovery Scenarios

### Scenario 1: Single Database Node Failure
**Trigger:** PostgreSQL primary node crash, hardware failure.  
**RTO:** < 15 minutes (automatic failover to replica).  
**Response:**
1. Azure Database for PostgreSQL automatic failover activates standby replica.
2. Alert fires to on-call engineer via PagerDuty.
3. On-call verifies application connectivity within 10 minutes.
4. No data loss if WAL replication is < 4 hours behind (RPO satisfied).

### Scenario 2: Full Database Cluster Loss
**Trigger:** Datacenter failure, storage corruption, ransomware.  
**RTO:** < 72 hours.  
**Response:**
1. Declare disaster via the Incident Response Slack channel (#incident-p1).
2. Provision new PostgreSQL cluster in secondary region (Terraform: `make disaster-recovery`).
3. Restore from latest verified backup using `infrastructure/scripts/restore.sh`.
4. Run `alembic upgrade head` for all modules to apply any pending migrations.
5. Validate data integrity: run `scripts/verify_backup.py` against restored DB.
6. Re-route DNS / Azure Front Door to secondary region.
7. Resume event bus subscriptions.

### Scenario 3: Kubernetes Cluster Failure
**Trigger:** AKS control plane failure, node pool exhaustion.  
**RTO:** < 4 hours.  
**Response:**
1. Activate secondary AKS cluster (pre-provisioned via Terraform).
2. Apply stored manifests: `kubectl apply -f infrastructure/k8s/`.
3. Verify all module health endpoints: `make health-check`.
4. Re-route traffic.

### Scenario 4: Key Vault / Encryption Key Loss
**Trigger:** Azure Key Vault unavailable or key deleted.  
**RTO:** < 24 hours.  
**Response:**
1. Restore Key Vault from daily backup in secondary vault.
2. Rotate encryption keys if compromise suspected.
3. If primary keys are unrecoverable and backups are unavailable:
   - ePHI at rest is **permanently inaccessible** — treat as data loss.
   - Initiate breach notification per `sop-breach-notification.md`.

### Scenario 5: Complete Datacenter Loss
**Trigger:** Regional Azure outage (rare).  
**RTO:** < 72 hours.  
**Response:**
1. Activate cross-region DR runbook (paired region).
2. All infrastructure is reprovisioned via Terraform in paired region.
3. Restore PostgreSQL from geo-redundant Blob Storage backup.
4. Resume operations from secondary region.

---

## 6. Restore Procedure

Reference: `docs/sops/backup-restore.md` for full step-by-step restore instructions.

### 6.1 Weekly Verified Restore Test

Per HIPAA §164.308(a)(7)(ii)(B), the platform MUST demonstrate 72-hour
restoration capability. A verified restore test is conducted every week:

1. Pick a backup from the prior 7-day window at random.
2. Restore to an isolated test environment using `infrastructure/scripts/restore.sh`.
3. Run data integrity checks: `scripts/verify_backup.py`.
4. Confirm all 24 module schemas are present and populated.
5. Record result in `infrastructure/scripts/tests/restore_evidence/YYYY-MM-DD.md`.

**Status as of 2026-04-14 (audit H-09):** The
`infrastructure/scripts/tests/restore_evidence/` directory does not exist.
This is a **high-severity finding**. The directory and the first restore
evidence file must be created immediately.

### 6.2 Restore Evidence Template

```markdown
# Restore Test: YYYY-MM-DD

**Backup file:** <name and Azure Blob path>
**Backup timestamp:** <ISO-8601>
**Restore start:** <ISO-8601>
**Restore complete:** <ISO-8601>
**Duration:** <minutes>
**Schemas verified:** <list>
**Row counts spot-check:**
  - core.users: N
  - billing.claim_records: N
  - member.members: N
**verify_backup.py result:** PASS / FAIL
**Performed by:** <name>
**Signed off by:** <name>
```

---

## 7. Emergency Mode Operations

If the primary platform is unavailable, the following emergency procedures apply:

### 7.1 Claims Processing
- Switch to manual claim adjudication via the emergency manual process.
- Paper claims are accepted and keyed within 24 hours of system restoration.
- Claims are backdated to submission date.

### 7.2 Member Eligibility
- Pharmacy point-of-sale systems fall back to cached eligibility files (last
  known state, < 4 hours stale per RPO).
- Emergency override codes are available per member contract.

### 7.3 Communications
- Status page at `status.infinityrx.com` is updated within 15 minutes.
- Tenant administrators are notified by phone for outages > 1 hour.

---

## 8. Tabletop Exercise Schedule

| Quarter | Exercise Type | Scenario |
|---|---|---|
| Q1 | Tabletop discussion | Database cluster failure + key compromise |
| Q2 | Full DR simulation | Regional Azure outage (no production traffic) |
| Q3 | Tabletop discussion | Ransomware: data encrypted, key lost |
| Q4 | Full DR simulation | Complete restore from backup, timed to < 72h |

Results are documented and used to update this SOP and improve RTO/RPO targets.

---

## 9. References

- 45 CFR §164.308(a)(7) — Contingency Plan
- 45 CFR §164.308(a)(7)(ii)(A) — Data Backup Plan
- 45 CFR §164.308(a)(7)(ii)(B) — Disaster Recovery Plan
- 45 CFR §164.308(a)(7)(ii)(C) — Emergency Mode Operation Plan
- 45 CFR §164.308(a)(7)(ii)(D) — Testing and Revision Procedure
- 45 CFR §164.308(a)(7)(ii)(E) — Applications and Data Criticality Analysis
- NIST SP 800-34 Rev.1 — Contingency Planning Guide for Federal Information Systems
- `docs/sops/backup-restore.md` — Detailed backup and restore procedures
- `infrastructure/scripts/backup.sh` — Backup implementation
- `infrastructure/scripts/restore.sh` — Restore implementation

---

**Review Date:** 2026-04-14
