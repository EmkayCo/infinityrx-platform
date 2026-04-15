# PRD — Module 9: Switch Connectivity (FINAL)

**Module:** Switch Connectivity
**Folder:** `modules/switch-connectivity/`
**Phase:** 5, Wave 4 (after Adjudication Engine)
**Dependencies:** Core Platform (1), Claims Adjudication Engine (8)

---

## 1. Purpose

Switch Connectivity is the network interface between the outside world (pharmacies, switch networks) and the adjudication engine. Pharmacy systems submit claims through switch networks (RelayHealth, Change Healthcare, RedSail/PowerLine). This module handles the telecommunications protocol, BIN/PCN routing, connection management, and message framing.

---

## 2. Architecture

```
Pharmacy POS → Switch Network → InfinityRx Switch Module
  → NCPDP D.0 message parsing → BIN/PCN routing → Adjudication Engine
  → Response framing → Switch → Pharmacy
```

---

## 3. Switch Integrations

Each switch is a configurable adapter — adding a new switch never requires code changes to core routing.

**Initial:** RelayHealth (Change Healthcare Relay), Change Healthcare (Emdeon), RedSail/PowerLine. Each adapter implements: connect(), receive_message(), send_response(), heartbeat(), disconnect().

---

## 4. NCPDP SCRIPT Standard Support

**Dual-version support during transition (required by Jan 1, 2028):**
- NCPDP SCRIPT 2017071 (current standard)
- NCPDP SCRIPT 2023011 (new standard — enhanced ePA, EPCS, LTC transfer, structured Sig, improved medication history)

Configurable per switch/pharmacy: which version to use. Auto-detect from message header where possible. Both versions fully supported until 2017071 retirement.

---

## 5. BIN/PCN Routing

When a claim arrives, BIN + PCN identify which tenant and plan should process it.

- Configurable per tenant via UI
- Wildcard support: BIN=610341, PCN=* → default handler for unknown PCNs
- Priority ordering: specific routes match before wildcards
- Pass-through routing: forward claims to another processor (network sharing)

---

## 6. Connection Management

- Connection pooling: persistent connections, configurable pool size
- Health monitoring: configurable heartbeat interval, alert on failure
- Automatic failover: primary down → route to secondary (configurable chains)
- Response timeout: configurable per switch (industry standard 30 seconds)
- Graceful degradation: all connections down → queue for retry
- Connection metrics: latency, throughput, error rate, uptime per switch

---

## 7. Switch Certification

- Import switch-specific certification test scripts
- Map to simulator format (Testing Simulator module)
- Run certification suite against adjudication engine in test mode
- Generate evidence package (request/response pairs, pass/fail summary)
- Re-certification scheduling and tracking

---

## 8. Data Models

```
switch_configs, switch_health, bin_pcn_routes, switch_failover_chains, switch_transaction_log (encrypted), certification_runs, script_version_config (per switch/pharmacy)
```

---

## 9. API, Events, Tests

**API:** CRUD switches, health status, BIN/PCN routes, test connection, run certification, metrics.

**Events:** `switch.connected`, `switch.disconnected`, `switch.health_degraded`, `switch.failover_triggered`, `switch.certification_completed`

**Tests:** claim routed by BIN/PCN and adjudicated within timeout, failover works, unknown BIN/PCN returns reject (not crash), malformed message handled, both SCRIPT versions work, certification suite runs correctly, batch of 100 claims processed, connection drop mid-transaction safe.

---

## 10. Session Decomposition

1. **Switch adapters:** RelayHealth, Change Healthcare, RedSail + adapter interface + message framing + SCRIPT version negotiation
2. **Routing engine:** BIN/PCN table, wildcard matching, pass-through, priority ordering
3. **Connection management:** pooling, health monitoring, failover, graceful degradation, metrics
4. **Certification:** test harness integration, scenario runner, evidence generation
