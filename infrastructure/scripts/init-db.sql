-- ---------------------------------------------------------------------------
-- IFX local-dev Postgres bootstrap (runs once on first container start)
-- ---------------------------------------------------------------------------
-- Schema names below must match the SCHEMA constants in each module's
-- src/models/*.py — grep `SCHEMA = "..."` under modules/ and shared/ to audit.
-- ---------------------------------------------------------------------------

-- Shared foundation
CREATE SCHEMA IF NOT EXISTS core;                      -- shared/db/models/*.py
CREATE SCHEMA IF NOT EXISTS shared;                    -- shared/data_ingestion/models.py (ingestion_runs, ingestion_schedules)

-- Phase 2
CREATE SCHEMA IF NOT EXISTS billing;
CREATE SCHEMA IF NOT EXISTS payment_proc;
CREATE SCHEMA IF NOT EXISTS reclaimrx;
CREATE SCHEMA IF NOT EXISTS reporting;

-- Phase 3
CREATE SCHEMA IF NOT EXISTS ai_nlp;
CREATE SCHEMA IF NOT EXISTS dataiq;
CREATE SCHEMA IF NOT EXISTS drug_db;                   -- modules/drug-database/src/models/tables.py (legacy tables)
CREATE SCHEMA IF NOT EXISTS drug_database;             -- modules/drug-database/src/models/{ndc,pricing,orange_book}_tables.py
CREATE SCHEMA IF NOT EXISTS pharmacy_dir;              -- modules/pharmacy-directory/src/models/*.py
CREATE SCHEMA IF NOT EXISTS prescriber_dir;            -- modules/prescriber-directory/src/models/*.py
CREATE SCHEMA IF NOT EXISTS member_mgmt;

-- Phase 4
CREATE SCHEMA IF NOT EXISTS edi;                       -- modules/edi-compliance/src/models/edi_models.py
CREATE SCHEMA IF NOT EXISTS edi_compliance;            -- alternate name, kept for compatibility
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

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
