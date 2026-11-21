#!/bin/bash
set -euo pipefail
# Run only inside the task-created scratch policy container.
[ "${STRICT_READ_SMOKE:-}" = 1 ] || exit 2
initdb -D /tmp/policy-pg --auth=trust >/dev/null
pg_ctl -D /tmp/policy-pg -l /tmp/policy-start.log -o '-c listen_addresses=localhost' -w start >/dev/null
psql -v ON_ERROR_STOP=1 -q -f /tmp/policy-init/00-users.sql postgres
psql -v ON_ERROR_STOP=1 -q -c 'ALTER DATABASE template0 ALLOW_CONNECTIONS true' postgres
for db in postgres template1 template0 megasamples; do
 psql -v ON_ERROR_STOP=1 -q -f /tmp/policy-init/10-read-profile.sql "$db"
done
psql -v ON_ERROR_STOP=1 -q -c 'ALTER DATABASE template0 ALLOW_CONNECTIONS false' postgres
printf "shared_preload_libraries = 'read_policy'\n" >> /tmp/policy-pg/postgresql.conf
pg_ctl -D /tmp/policy-pg -l /tmp/policy-start.log -w restart >/dev/null
for template in template1 template0; do
 psql -U admin -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE roundtrip TEMPLATE $template" postgres
 test "$(psql -U demo -d roundtrip -Atc "SELECT has_database_privilege(current_database(),'TEMP')")" = f
 psql -U admin -v ON_ERROR_STOP=1 -q -d roundtrip -c "CREATE TABLE t(i int); INSERT INTO t VALUES(1); CREATE FUNCTION f() RETURNS int LANGUAGE sql AS 'SELECT 1'; CREATE PROCEDURE p() LANGUAGE sql AS 'SELECT 1'"
 test "$(psql -U demo -d roundtrip -Atc "SELECT has_function_privilege('f()','EXECUTE')")" = f
 test "$(psql -U postgres -d roundtrip -Atc "SELECT has_function_privilege('admin','pg_read_file(text)','EXECUTE')")" = f
 pg_dump -Fc --create -f /tmp/policy-roundtrip.dump roundtrip
 psql -v ON_ERROR_STOP=1 -q -c 'DROP DATABASE roundtrip' postgres
 pg_restore -d postgres --create --exit-on-error /tmp/policy-roundtrip.dump
 test "$(psql -U admin -d roundtrip -Atc 'SELECT count(*) FROM t')" = 1
 test "$(psql -U demo -d roundtrip -Atc "SELECT has_database_privilege(current_database(),'TEMP')")" = f
 psql -v ON_ERROR_STOP=1 -q -c 'DROP DATABASE roundtrip' postgres
 echo "$template creation, routines, writer preservation and dump/restore Passed"
done
