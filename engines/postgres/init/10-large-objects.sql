-- Run as postgres in every database, the templates included, so databases made from them inherit it.
-- PostgreSQL's defaults let every role create large objects, which persist in the database: the one
-- write a read-only account would otherwise inherit from PUBLIC. admin keeps the right.
REVOKE EXECUTE ON FUNCTION pg_catalog.lo_creat(integer), pg_catalog.lo_create(oid),
    pg_catalog.lo_from_bytea(oid, bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION pg_catalog.lo_creat(integer), pg_catalog.lo_create(oid),
    pg_catalog.lo_from_bytea(oid, bytea) TO admin;
