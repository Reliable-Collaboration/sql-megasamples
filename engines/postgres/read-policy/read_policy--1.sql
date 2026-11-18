CREATE SCHEMA megasamples_policy AUTHORIZATION postgres;
REVOKE ALL ON SCHEMA megasamples_policy FROM PUBLIC;
CREATE FUNCTION megasamples_policy.close_routine_defaults() RETURNS event_trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE command record;
BEGIN
  FOR command IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
    IF command.classid = 'pg_proc'::regclass THEN
      EXECUTE format('REVOKE EXECUTE ON ROUTINE %s FROM PUBLIC', command.objid::regprocedure);
      EXECUTE format('GRANT EXECUTE ON ROUTINE %s TO admin', command.objid::regprocedure);
    END IF;
  END LOOP;
END
$$;
REVOKE ALL ON FUNCTION megasamples_policy.close_routine_defaults() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION megasamples_policy.close_routine_defaults() TO admin;
CREATE EVENT TRIGGER megasamples_close_routines ON ddl_command_end
EXECUTE FUNCTION megasamples_policy.close_routine_defaults();
