-- The physical database is still private to the builder while its grants are changed.
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM megasamples_working_write;
REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM megasamples_working_write;
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
    REVOKE INSERT, UPDATE, DELETE ON TABLES FROM megasamples_working_write;
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
    REVOKE USAGE ON SEQUENCES FROM megasamples_working_write;

GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pg_database_owner;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO pg_database_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
    GRANT INSERT, UPDATE, DELETE ON TABLES TO pg_database_owner;
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO pg_database_owner;
VACUUM (FREEZE, ANALYZE);
