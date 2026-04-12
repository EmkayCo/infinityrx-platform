-- infrastructure/docker/init-schemas.sql
-- Executed by the Postgres container on first init.
-- Creates one schema per module. Each module owns its schema exclusively.
-- Keep this list in sync with docs/prd/prd-core-platform.md section 5.2.

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS billing;
CREATE SCHEMA IF NOT EXISTS reclaimrx;
CREATE SCHEMA IF NOT EXISTS drug_db;
CREATE SCHEMA IF NOT EXISTS pharmacy_dir;
CREATE SCHEMA IF NOT EXISTS med_prescriber_dir;
CREATE SCHEMA IF NOT EXISTS member_mgmt;
CREATE SCHEMA IF NOT EXISTS plan_design;
CREATE SCHEMA IF NOT EXISTS rules_engine;
CREATE SCHEMA IF NOT EXISTS adjudication;
CREATE SCHEMA IF NOT EXISTS switch_conn;
CREATE SCHEMA IF NOT EXISTS prior_auth;
CREATE SCHEMA IF NOT EXISTS payment_proc;
CREATE SCHEMA IF NOT EXISTS edi_compliance;
CREATE SCHEMA IF NOT EXISTS medical_claims;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS program_config;
CREATE SCHEMA IF NOT EXISTS testing_sim;
CREATE SCHEMA IF NOT EXISTS ebv_ebi;
CREATE SCHEMA IF NOT EXISTS ai_nlp;
CREATE SCHEMA IF NOT EXISTS rebate_mgmt;
CREATE SCHEMA IF NOT EXISTS dataiq;
CREATE SCHEMA IF NOT EXISTS part_d;
CREATE SCHEMA IF NOT EXISTS mtm_clinical;

-- Required extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;
