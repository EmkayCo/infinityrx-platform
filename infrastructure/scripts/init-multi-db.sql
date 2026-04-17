-- ---------------------------------------------------------------------------
-- IFX local-dev Postgres bootstrap — three databases, one cluster.
-- ---------------------------------------------------------------------------
-- prod : real PHI, real money. Awaits first production batch.
-- dev  : developer/testing sandbox. Synthetic test data only.
-- mock : demo environment. Sanitized synthetic data from scramble_claims.py.
--
-- Architecture (see CLAUDE.md → Environment Architecture):
--
--   ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
--   │   infinityrx_prod   │ │   infinityrx_dev    │ │   infinityrx_mock   │
--   │  owner ifx_prod_app │ │  owner ifx_dev_app  │ │  owner ifx_mock_app │
--   ├─────────────────────┤ ├─────────────────────┤ ├─────────────────────┤
--   │ schema: reference   │ │ schema: reference   │ │ schema: reference   │
--   │  (read-only via     │ │  (read-only via     │ │  (read-only via     │
--   │   ifx_ref_reader)   │ │   ifx_ref_reader)   │ │   ifx_ref_reader)   │
--   ├─────────────────────┤ ├─────────────────────┤ ├─────────────────────┤
--   │ schema: core, ...   │ │ schema: core, ...   │ │ schema: core, ...   │
--   │ schema: billing,    │ │ schema: billing,    │ │ schema: billing,    │
--   │   payment_proc, ... │ │   payment_proc, ... │ │   payment_proc, ... │
--   │ (full CRUD via      │ │ (full CRUD via      │ │ (full CRUD via      │
--   │   ifx_prod_app)     │ │   ifx_dev_app)      │ │   ifx_mock_app)     │
--   └─────────────────────┘ └─────────────────────┘ └─────────────────────┘
--
-- Reference data (drug NDC, NPPES prescribers, NCPDP pharmacies, CMS, etc.)
-- is logically the same across all three environments — public/licensed data
-- loaded from raw files in data/raw/. Physically replicated per database to
-- avoid cross-database queries.
--
-- This script runs ONCE on first container start (when the postgres data
-- volume is empty). To re-run: docker compose down -v
-- ---------------------------------------------------------------------------

-- ── Roles ───────────────────────────────────────────────────────────────────
-- Three per-environment app roles + one shared read-only reference reader.
-- Local-dev passwords are baked into .env.{dev,mock,prod} — change BOTH
-- places if you rotate. Real prod password comes from a secrets vault.
CREATE ROLE ifx_prod_app   LOGIN PASSWORD 'CHANGEME_PROD_PASSWORD';
CREATE ROLE ifx_dev_app    LOGIN PASSWORD 'dev_password';
CREATE ROLE ifx_mock_app   LOGIN PASSWORD 'mock_password';
CREATE ROLE ifx_ref_reader LOGIN PASSWORD 'ref_password';

CREATE DATABASE infinityrx_prod OWNER ifx_prod_app;
CREATE DATABASE infinityrx_dev  OWNER ifx_dev_app;
CREATE DATABASE infinityrx_mock OWNER ifx_mock_app;

-- ifx_ref_reader needs CONNECT on every database so it can read reference
-- data from any environment.
GRANT CONNECT ON DATABASE infinityrx_prod TO ifx_ref_reader;
GRANT CONNECT ON DATABASE infinityrx_dev  TO ifx_ref_reader;
GRANT CONNECT ON DATABASE infinityrx_mock TO ifx_ref_reader;

-- Bootstrap superuser keeps full access for migrations and admin ops.
GRANT ALL PRIVILEGES ON DATABASE infinityrx_prod TO infinityrx;
GRANT ALL PRIVILEGES ON DATABASE infinityrx_dev  TO infinityrx;
GRANT ALL PRIVILEGES ON DATABASE infinityrx_mock TO infinityrx;

-- ---------------------------------------------------------------------------
-- Per-database schema scaffolding. Identical across all three databases —
-- any drift would be a bug. Schema names MUST match the SCHEMA constants
-- in each module's src/models/*.py.
-- ---------------------------------------------------------------------------

\connect infinityrx_prod
SET ROLE ifx_prod_app;

CREATE SCHEMA IF NOT EXISTS reference;
GRANT USAGE ON SCHEMA reference TO ifx_ref_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reference
  GRANT SELECT ON TABLES TO ifx_ref_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reference
  GRANT SELECT ON SEQUENCES TO ifx_ref_reader;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS shared;
CREATE SCHEMA IF NOT EXISTS billing;
CREATE SCHEMA IF NOT EXISTS payment_proc;
CREATE SCHEMA IF NOT EXISTS reclaimrx;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS ai_nlp;
CREATE SCHEMA IF NOT EXISTS dataiq;
CREATE SCHEMA IF NOT EXISTS drug_db;
CREATE SCHEMA IF NOT EXISTS drug_database;
CREATE SCHEMA IF NOT EXISTS pharmacy_dir;
CREATE SCHEMA IF NOT EXISTS prescriber_dir;
CREATE SCHEMA IF NOT EXISTS member_mgmt;
CREATE SCHEMA IF NOT EXISTS edi;
CREATE SCHEMA IF NOT EXISTS edi_compliance;
CREATE SCHEMA IF NOT EXISTS medical_claims;
CREATE SCHEMA IF NOT EXISTS adjudication;
CREATE SCHEMA IF NOT EXISTS mtm_clinical;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE SCHEMA IF NOT EXISTS tenant_config;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
RESET ROLE;

\connect infinityrx_dev
SET ROLE ifx_dev_app;

CREATE SCHEMA IF NOT EXISTS reference;
GRANT USAGE ON SCHEMA reference TO ifx_ref_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reference
  GRANT SELECT ON TABLES TO ifx_ref_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reference
  GRANT SELECT ON SEQUENCES TO ifx_ref_reader;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS shared;
CREATE SCHEMA IF NOT EXISTS billing;
CREATE SCHEMA IF NOT EXISTS payment_proc;
CREATE SCHEMA IF NOT EXISTS reclaimrx;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS ai_nlp;
CREATE SCHEMA IF NOT EXISTS dataiq;
CREATE SCHEMA IF NOT EXISTS drug_db;
CREATE SCHEMA IF NOT EXISTS drug_database;
CREATE SCHEMA IF NOT EXISTS pharmacy_dir;
CREATE SCHEMA IF NOT EXISTS prescriber_dir;
CREATE SCHEMA IF NOT EXISTS member_mgmt;
CREATE SCHEMA IF NOT EXISTS edi;
CREATE SCHEMA IF NOT EXISTS edi_compliance;
CREATE SCHEMA IF NOT EXISTS medical_claims;
CREATE SCHEMA IF NOT EXISTS adjudication;
CREATE SCHEMA IF NOT EXISTS mtm_clinical;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE SCHEMA IF NOT EXISTS tenant_config;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
RESET ROLE;

\connect infinityrx_mock
SET ROLE ifx_mock_app;

CREATE SCHEMA IF NOT EXISTS reference;
GRANT USAGE ON SCHEMA reference TO ifx_ref_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reference
  GRANT SELECT ON TABLES TO ifx_ref_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reference
  GRANT SELECT ON SEQUENCES TO ifx_ref_reader;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS shared;
CREATE SCHEMA IF NOT EXISTS billing;
CREATE SCHEMA IF NOT EXISTS payment_proc;
CREATE SCHEMA IF NOT EXISTS reclaimrx;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS ai_nlp;
CREATE SCHEMA IF NOT EXISTS dataiq;
CREATE SCHEMA IF NOT EXISTS drug_db;
CREATE SCHEMA IF NOT EXISTS drug_database;
CREATE SCHEMA IF NOT EXISTS pharmacy_dir;
CREATE SCHEMA IF NOT EXISTS prescriber_dir;
CREATE SCHEMA IF NOT EXISTS member_mgmt;
CREATE SCHEMA IF NOT EXISTS edi;
CREATE SCHEMA IF NOT EXISTS edi_compliance;
CREATE SCHEMA IF NOT EXISTS medical_claims;
CREATE SCHEMA IF NOT EXISTS adjudication;
CREATE SCHEMA IF NOT EXISTS mtm_clinical;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE SCHEMA IF NOT EXISTS tenant_config;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
RESET ROLE;
