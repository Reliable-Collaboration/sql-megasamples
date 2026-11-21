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
