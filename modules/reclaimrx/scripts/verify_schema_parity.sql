-- verify_schema_parity.sql
-- Schema parity verification: reclaimrx_scratch.reclaimrx vs infinityrx_dev.reclaimrx
-- Both DBs must be at revision 0008_ml_detector_seed.
-- Run against either DB using cross-DB queries via dblink, or run sections
-- against each DB individually and compare outputs.
--
-- Usage (run against each DB separately and diff output):
--   psql -U infinityrx -d infinityrx_dev -f verify_schema_parity.sql
--   psql -U infinityrx -d reclaimrx_scratch -f verify_schema_parity.sql
--
-- Sections:
--   1. alembic_version check
--   2. Tables present (pg_tables)
--   3. Columns per table (information_schema.columns: name, data_type, is_nullable)
--   4. CHECK constraints (pg_constraint contype='c')
--   5. Indexes (pg_indexes incl. partial predicates)
--   6. RLS: pg_policies + relrowsecurity + relforcerowsecurity
--   7. Grants (information_schema.role_table_grants for app/admin roles)
--   8. Catalog data: ml_detector_registry rows
--   9. Catalog data: detection_rule_types count

\echo '=== SECTION 1: alembic_version ==='
SELECT version_num FROM reclaimrx.alembic_version;

\echo '=== SECTION 2: tables in reclaimrx schema (ordered) ==='
SELECT tablename
FROM pg_tables
WHERE schemaname = 'reclaimrx'
ORDER BY tablename;

\echo '=== SECTION 3: columns per table (name, data_type, is_nullable, column_default) ==='
SELECT
    table_name,
    column_name,
    data_type,
    udt_name,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'reclaimrx'
  AND table_name != 'alembic_version'
ORDER BY table_name, ordinal_position;

\echo '=== SECTION 4: CHECK constraints ==='
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    con.conname AS constraint_name,
    pg_get_constraintdef(con.oid) AS constraint_def
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'reclaimrx'
  AND con.contype = 'c'
ORDER BY c.relname, con.conname;

\echo '=== SECTION 5: indexes (incl. partial predicates) ==='
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'reclaimrx'
ORDER BY tablename, indexname;

\echo '=== SECTION 6: RLS policies + row security flags ==='
-- Policies
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE schemaname = 'reclaimrx'
ORDER BY tablename, policyname;

-- Row security flags per table
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'reclaimrx'
  AND c.relkind = 'r'
ORDER BY c.relname;

\echo '=== SECTION 7: grants (role_table_grants for ifx_ roles) ==='
SELECT
    table_schema,
    table_name,
    grantee,
    privilege_type,
    is_grantable
FROM information_schema.role_table_grants
WHERE table_schema = 'reclaimrx'
  AND grantee IN ('ifx_dev_app', 'ifx_dev_admin', 'ifx_prod_admin', 'ifx_mock_app', 'ifx_mock_admin')
ORDER BY table_name, grantee, privilege_type;

\echo '=== SECTION 8: ml_detector_registry catalog rows ==='
SELECT
    detector_name,
    feature_schema_class,
    is_placeholder
FROM reclaimrx.ml_detector_registry
ORDER BY detector_name;

\echo '=== SECTION 9: detection_rule_types count ==='
SELECT count(*) AS detection_rule_types_count
FROM reclaimrx.detection_rule_types;
