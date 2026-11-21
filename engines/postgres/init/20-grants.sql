-- Run inside each database after its data is loaded, which happens as `admin`: admin owns every
-- table, view, routine and trigger of the sample databases and can alter or drop them.
SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO megasamples_working_read, megasamples_working_write',
              current_database()) \gexec
GRANT SELECT ON ALL TABLES IN SCHEMA public TO megasamples_read;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO megasamples_working_write;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO megasamples_working_write;
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public GRANT SELECT ON TABLES TO megasamples_read;
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
    GRANT INSERT, UPDATE, DELETE ON TABLES TO megasamples_working_write;
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public GRANT USAGE ON SEQUENCES TO megasamples_working_write;
