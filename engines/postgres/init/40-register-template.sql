SELECT pg_database_size(:'working'::name) AS bytes,
       CASE WHEN pg_database_size(:'working'::name) > 134217728
            THEN 'file_copy' ELSE 'wal_log' END AS strategy \gset
SELECT build_id, encode(sha256(convert_to(row_to_json(d)::text, 'UTF8')), 'hex') AS digest
FROM datasets d WHERE name = :'working' \gset

REVOKE CONNECT ON DATABASE :"working" FROM megasamples_working_read, megasamples_working_write;
ALTER DATABASE :"working" RENAME TO :"template";
ALTER DATABASE :"template" OWNER TO postgres;
ALTER DATABASE :"template" IS_TEMPLATE true ALLOW_CONNECTIONS false;
SELECT format('COMMENT ON DATABASE %I IS %L', :'template',
              'megasamples-template/1 ' || json_build_object(
                  'database', :'working', 'bytes', :bytes, 'strategy', :'strategy',
                  'build', :'build_id', 'digest', :'digest')::text) \gexec
\echo :template :bytes bytes :strategy
CREATE DATABASE :"working" OWNER admin TEMPLATE :"template" STRATEGY :strategy;
