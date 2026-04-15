-- ---------------------------------------------------------------------------
-- IFX local-dev Postgres bootstrap — creates THREE separate databases
-- ---------------------------------------------------------------------------
-- prod : clean slate, awaits first real production batch
-- dev  : developer/testing sandbox, freely re-seedable
-- mock : demo environment, populated with SCRAMBLED claims (no real PHI)
--
-- This script runs ONCE on first container start (when the postgres data
-- volume is empty). To re-run, you must `docker compose down -v` first.
--
-- Schema names below MUST match the SCHEMA constants in each module's
-- src/models/*.py. Keep this list in sync with init-db.sql (legacy single-db).
-- ---------------------------------------------------------------------------

-- Per-environment roles for credential isolation. Each role can only log into
-- its own database. Real production passwords are loaded via the deploy vault;
-- the local-dev passwords below are baked into .env.{dev,mock,prod} so they
-- match exactly. Change them in BOTH places if you rotate.
CREATE ROLE ifx_prod LOGIN PASSWORD 'CHANGEME_PROD_PASSWORD';
CREATE ROLE ifx_dev  LOGIN PASSWORD 'ifx_local_dev_2026';
CREATE ROLE ifx_mock LOGIN PASSWORD 'ifx_mock_demo_2026';

CREATE DATABASE infinityrx_prod OWNER ifx_prod;
CREATE DATABASE infinityrx_dev  OWNER ifx_dev;
CREATE DATABASE infinityrx_mock OWNER ifx_mock;

-- Bootstrap superuser keeps full access for migrations and admin ops.
GRANT ALL PRIVILEGES ON DATABASE infinityrx_prod TO infinityrx;
GRANT ALL PRIVILEGES ON DATABASE infinityrx_dev  TO infinityrx;
GRANT ALL PRIVILEGES ON DATABASE infinityrx_mock TO infinityrx;

-- ---------------------------------------------------------------------------
-- infinityrx_prod
-- ---------------------------------------------------------------------------
\connect infinityrx_prod

SET ROLE ifx_prod;
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
CREATE SCHEMA IF NOT EXISTS part_d;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- infinityrx_dev
-- ---------------------------------------------------------------------------
\connect infinityrx_dev

SET ROLE ifx_dev;
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
CREATE SCHEMA IF NOT EXISTS part_d;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- infinityrx_mock  (demo environment — safe for prospect demos)
-- ---------------------------------------------------------------------------
\connect infinityrx_mock

SET ROLE ifx_mock;
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
CREATE SCHEMA IF NOT EXISTS part_d;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
