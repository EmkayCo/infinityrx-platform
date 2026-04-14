# SOP: Device and Media Controls

**Document ID:** SOP-DM-001  
**HIPAA Reference:** 45 CFR §164.310(d) — Device and Media Controls; §164.312(a)(2)(iv) — Encryption  
**Version:** 1.0  
**Effective Date:** 2026-04-14  
**Review Date:** 2026-04-14  
**Owner:** Chief Technology Officer / Security Officer  
**Approved By:** HIPAA Compliance Committee

---

## 1. Purpose

This SOP establishes the requirements for controlling hardware and electronic
media (including portable devices, workstations, and removable storage) that
contain or have access to ePHI. It satisfies 45 CFR §164.310(d) and the
2026 HIPAA Final Rule's strengthened encryption requirements.

---

## 2. Scope

Applies to all hardware and electronic media that:
- Contain ePHI
- Are used to access systems that contain ePHI
- Are being moved within or out of InfinityRx facilities

Includes: laptops, desktop workstations, servers, virtual machines, cloud
storage volumes, USB drives, mobile devices, backup media, and decommissioned
hardware.

---

## 3. Encryption at Rest

Per HIPAA 2026 Final Rule, AES-256 encryption at rest is **required** (not
addressable) for all ePHI storage.

### 3.1 Database Encryption

All PHI columns are encrypted using `EncryptedString` (`shared/crypto/sqlalchemy_types.py`):
- Algorithm: AES-256-GCM
- Tenant-scoped Additional Authenticated Data (AAD): ciphertext from one
  tenant MUST fail decryption in another tenant's context.
- Key management: Azure Key Vault (production); environment variable (development).
- Key rotation: Keys are rotated annually or immediately on suspected compromise.

### 3.2 Storage Volume Encryption

All PostgreSQL data volumes must use:
- Azure Managed Disks with platform-managed encryption (AES-256) AND
- PostgreSQL Transparent Data Encryption where available.

Redis data volumes: Azure Cache for Redis with in-transit TLS 1.3 and
at-rest AES-256 encryption.

### 3.3 Backup Encryption

All database backup files are encrypted with AES-256 before upload to
Azure Blob Storage. The encryption key is stored in Key Vault, not in
the backup itself.

### 3.4 Workstation Encryption

All workstations and laptops used to access InfinityRx systems must have
full-disk encryption enabled:
- macOS: FileVault 2 (AES-256)
- Windows: BitLocker (AES-256)
- Linux: LUKS2 (AES-256)

Evidence of full-disk encryption is verified at provisioning and in
quarterly device audits.

---

## 4. Workstation Policies

Per 45 CFR §164.310(b) — Workstation Use and (c) — Workstation Security:

### 4.1 Authorized Use
- Workstations accessing ePHI must be used ONLY for business purposes.
- ePHI must never be stored locally on workstations; use only cloud-stored
  encrypted volumes.
- Auto-lock must be configured: screen lock after 5 minutes of inactivity.
- Automatic OS security updates must be enabled and applied within 7 days.

### 4.2 Physical Security
- Unattended workstations must be locked or logged out.
- Screens must not be visible to unauthorized individuals (privacy screens
  required in open-plan offices).
- Work-from-home workstations must be in a private area during ePHI access.

### 4.3 Prohibited Configurations
- Sharing workstation credentials between users is strictly prohibited.
- VPN is required for all remote access to InfinityRx systems.
- Connecting to public or untrusted Wi-Fi without VPN is prohibited.

---

## 5. Removable Media Prohibition

ePHI must NOT be stored on removable media (USB drives, external hard drives,
SD cards, optical discs) under any circumstances. Exceptions:
- Encrypted backup media physically transported under documented chain of
  custody for DR purposes only.
- Law enforcement request with documented legal process.

All removable media ports on workstations should be disabled via group
policy where technically feasible.

---

## 6. Device Disposal — NIST 800-88 Sanitization

All hardware containing ePHI must be sanitized before disposal, transfer,
or repurposing per NIST SP 800-88 Rev.1.

### 6.1 Sanitization Methods by Media Type

| Media Type | Method | Standard |
|---|---|---|
| HDD (spinning disk) | Purge: DoD 5220.22-M overwrite (7-pass) | NIST 800-88 §2.4 |
| SSD / NVMe / Flash | Purge: Cryptographic erase (ATA Secure Erase or vendor tool) | NIST 800-88 §2.6 |
| Cloud volumes | Destroy (Azure managed disk deletion with crypto-shred) | NIST 800-88 §2.7 |
| Backup tapes/drives | Destroy: physical degaussing + shredding | NIST 800-88 §2.4 |
| Mobile devices | Factory reset + cryptographic wipe via MDM | NIST 800-88 §2.6 |

**Cryptographic erase** (preferred for SSDs): The encrypted volume key is
deleted, rendering all data on the device computationally unrecoverable.
This relies on the device's AES-256 full-disk encryption being active
throughout its lifecycle — hence the workstation encryption requirement in §3.4.

### 6.2 Disposal Process

1. IT department initiates disposal ticket.
2. IT confirms full-disk encryption was active for the entire device lifecycle
   (if not, perform physical destruction instead of crypto-erase).
3. Perform sanitization appropriate to media type.
4. Complete Disposal Certificate form (template in `docs/compliance/templates/`).
5. For physical destruction: use certified vendor with chain-of-custody documentation.
6. Retain Disposal Certificate for 6 years per §164.316(b)(2).

### 6.3 Emergency Disposal

If a device must be disposed of urgently (e.g., end of lease, theft risk):
1. Perform cryptographic erase immediately.
2. If crypto-erase not possible: physically destroy (drill through platters/chips).
3. Document in IT security ticket and notify Privacy Officer within 24 hours.

---

## 7. Hardware Inventory

A hardware inventory is maintained and reviewed quarterly. The inventory includes:
- Device type and serial number
- Operating system and encryption status
- Assigned user
- ePHI access capability (yes/no)
- Last sanitization/disposal date (for retired devices)

---

## 8. Mobile Device Management (MDM)

All mobile devices with InfinityRx email or application access must be
enrolled in the corporate MDM system:
- Remote wipe capability enabled.
- Screen lock with 6-digit minimum PIN.
- Jailbroken/rooted devices are automatically blocked.
- MDM enrollment verified in quarterly device audit.

---

## 9. References

- 45 CFR §164.310(b) — Workstation Use
- 45 CFR §164.310(c) — Workstation Security
- 45 CFR §164.310(d) — Device and Media Controls
- 45 CFR §164.312(a)(2)(iv) — Encryption and Decryption
- NIST SP 800-88 Rev.1 — Guidelines for Media Sanitization
- NIST SP 800-111 — Guide to Storage Encryption Technologies for End User Devices
- `shared/crypto/sqlalchemy_types.py` — EncryptedString implementation
- `docs/compliance/sop-access-control.md`
- `docs/compliance/sop-contingency-plan.md`

---

**Review Date:** 2026-04-14
