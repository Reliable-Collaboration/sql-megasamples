-- The schema is an extension member, so pg_dump never carries it, and is owned by the installing
-- superuser, so no copy owner can drop it. The extension itself lives in pg_catalog (as plpgsql
-- does): it depends on no schema an ordinary owner can drop.
CREATE SCHEMA megasamples_policy;
REVOKE ALL ON SCHEMA megasamples_policy FROM PUBLIC;
CREATE FUNCTION megasamples_policy.close_routine_defaults() RETURNS pg_catalog.event_trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE command pg_catalog.record;
BEGIN
  FOR command IN SELECT * FROM pg_catalog.pg_event_trigger_ddl_commands() LOOP
    IF command.classid OPERATOR(pg_catalog.=) 'pg_catalog.pg_proc'::pg_catalog.regclass THEN
      IF pg_catalog.has_function_privilege(pg_catalog.to_regrole('admin')::pg_catalog.oid, command.objid, 'EXECUTE') THEN
        EXECUTE pg_catalog.format('GRANT EXECUTE ON ROUTINE %s TO admin', command.objid::pg_catalog.regprocedure);
      END IF;
      EXECUTE pg_catalog.format('REVOKE EXECUTE ON ROUTINE %s FROM PUBLIC', command.objid::pg_catalog.regprocedure);
    END IF;
  END LOOP;
END
$$;
REVOKE ALL ON FUNCTION megasamples_policy.close_routine_defaults() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION megasamples_policy.close_routine_defaults() TO admin;
CREATE EVENT TRIGGER megasamples_close_routines ON ddl_command_end
EXECUTE FUNCTION megasamples_policy.close_routine_defaults();
ALTER EVENT TRIGGER megasamples_close_routines ENABLE ALWAYS;
-- The healthcheck's witness. A library loaded on demand by this call, rather than preloaded,
-- answers false; demo, the probe's account, may call it (with the superuser), and no one else.
CREATE FUNCTION pg_catalog.megasamples_policy_loaded() RETURNS boolean
LANGUAGE C STABLE STRICT AS 'MODULE_PATHNAME', 'read_policy_loaded';
REVOKE ALL ON FUNCTION pg_catalog.megasamples_policy_loaded() FROM PUBLIC;
-- admin's default EXECUTE on routines postgres creates (10-read-profile.sql) must not reach it.
REVOKE ALL ON FUNCTION pg_catalog.megasamples_policy_loaded() FROM admin;
GRANT EXECUTE ON FUNCTION pg_catalog.megasamples_policy_loaded() TO demo;
