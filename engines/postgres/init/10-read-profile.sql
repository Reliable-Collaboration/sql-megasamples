-- Run as postgres in EVERY database, including postgres, registry and both templates.
-- Existing objects: close PUBLIC, restore full routine access to the writer,
-- then admit only the explicitly named, nonvolatile initdb built-ins to demo.
SELECT format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT TEMPORARY ON DATABASE %I TO admin', current_database()) \gexec

-- Materialize the writer's existing effective EXECUTE rights before removing
-- PUBLIC. Never grant admin a formerly superuser-only routine (file access,
-- lo_import, server administration, etc.). Ownership rights remain intact.
SELECT format('GRANT EXECUTE ON ROUTINE %s TO admin', p.oid::regprocedure)
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE has_function_privilege('admin',p.oid,'EXECUTE')
  AND n.nspname !~ '^pg_temp_' AND n.nspname !~ '^pg_toast' \gexec
SELECT format('REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA %I FROM PUBLIC', nspname)
FROM pg_namespace WHERE nspname !~ '^pg_temp_' AND nspname !~ '^pg_toast' \gexec

-- Global defaults matter: a per-schema REVOKE cannot subtract the global default.
ALTER DEFAULT PRIVILEGES FOR ROLE admin REVOKE EXECUTE ON ROUTINES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres REVOKE EXECUTE ON ROUTINES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres GRANT EXECUTE ON ROUTINES TO admin;

\ir read-routine-names.sql
SELECT format('GRANT EXECUTE ON ROUTINE %s TO demo', p.oid::regprocedure)
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
JOIN read_routine_names r ON r.name=p.proname AND r.namespace=n.nspname
WHERE ((n.nspname='pg_catalog' AND p.oid < 16384)
    OR (n.nspname='information_schema' AND p.proowner='postgres'::regrole))
  AND p.provolatile IN ('i','s') AND NOT p.prosecdef \gexec
-- Operators/casts are needed by ordinary expressions and information_schema.
-- Admit only the initdb definitions and their nonvolatile, invoker functions.
SELECT format('GRANT EXECUTE ON ROUTINE %s TO demo', p.oid::regprocedure)
FROM pg_proc p WHERE p.pronamespace='pg_catalog'::regnamespace AND p.oid<16384
  AND p.provolatile IN ('i','s') AND NOT p.prosecdef
  AND (EXISTS (SELECT 1 FROM pg_operator o WHERE o.oid<16384 AND o.oprcode=p.oid)
    OR EXISTS (SELECT 1 FROM pg_cast c WHERE c.oid<16384 AND c.castfunc=p.oid)) \gexec
DROP TABLE read_routine_names;

-- Packaging as an extension keeps template-resident policy objects out of
-- pg_dump's object list. CREATE EXTENSION IF NOT EXISTS on restore is safe even
-- though the freshly cloned template already contains the policy.
CREATE EXTENSION read_policy;
