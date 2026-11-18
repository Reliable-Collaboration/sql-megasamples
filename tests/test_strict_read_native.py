"""Opt-in, authenticated native regressions for the shipped read account.

MEGASAMPLES_NATIVE_READ_TESTS=1 enables these against a running isolated stack.
Only the explicitly supplied test containers are used; credentials use private files.
"""
import os
import subprocess

import pytest

from megasamples import config
from megasamples.credentials import client, session
from megasamples.engines import unique_databases

pytestmark = pytest.mark.skipif(os.environ.get('MEGASAMPLES_NATIVE_READ_TESTS') != '1',
                                reason='requires explicitly enabled isolated native stack')
CFG = config.load()


@pytest.fixture(scope='module', autouse=True)
def isolated_clients():
    if os.environ.get('MEGASAMPLES_NATIVE_READ_TESTS') != '1':
        yield
        return
    assert os.environ['COMPOSE_PROJECT_NAME'] == 'megasamples-upgrade'
    assert os.environ['CONTAINERS_STORAGE_CONF'] == '/home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf'
    store = subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip()
    assert store.startswith('/home/rcc-vstudio/working/sql-megasamples-upgrade-env/')
    with session():
        yield


def query(engine, database, sql, user='demo'):
    container = os.environ.get('STRICT_READ_' + engine.upper() + '_CONTAINER', 'megasamples-' + engine)
    key = {'postgres': 'POSTGRES_PASSWORD', 'root': 'MYSQL_ROOT_PASSWORD'}.get(user, user.upper() + '_PASSWORD')
    with client(engine, container, user, config.passwords()[key]) as command:
        args = (['-X', '-d', database, '-v', 'ON_ERROR_STOP=1', '-qAt', '-c', sql]
                if engine == 'postgres' else ['--batch', '-N', database, '-e', sql])
        return subprocess.run([*command, *args], capture_output=True, text=True)


def accepted(engine, database, sql, user='demo'):
    result = query(engine, database, sql, user)
    assert result.returncode == 0, result.stderr[:500]
    return result.stdout.strip()


def denied(engine, database, sql):
    result = query(engine, database, sql)
    assert result.returncode != 0, 'demo unexpectedly accepted: ' + sql
    assert (any(message in result.stderr for message in ('permission denied', 'must be owner')) if engine == 'postgres'
            else 'denied' in result.stderr.lower()), result.stderr[:500]


PG_DATABASES = unique_databases(CFG.datasets('postgres')) + ['megasamples', 'postgres', 'template1']
MY_DATABASES = unique_databases(CFG.datasets('mysql')) + ['megasamples']


@pytest.mark.parametrize('database', PG_DATABASES)
def test_postgres_demo_cannot_make_temporary_objects(database):
    denied('postgres', database, 'BEGIN; CREATE TEMP TABLE strict_read_temp(i int); ROLLBACK')
    assert accepted('postgres', database, "SELECT has_database_privilege(current_database(),'TEMP')") == 'f'


@pytest.mark.parametrize('database', PG_DATABASES)
def test_postgres_demo_cannot_create_large_objects(database):
    for expression in ['lo_create(0)', 'lo_creat(-1)', "lo_from_bytea(0,decode('00','hex'))", "lo_import('/nonexistent')"]:
        denied('postgres', database, 'BEGIN; SELECT ' + expression + '; ROLLBACK')


@pytest.mark.parametrize('database', PG_DATABASES)
def test_postgres_demo_has_no_unapproved_routines(database):
    # STABLE alone is insufficient: txid_current / pg_current_xact_id allocate XIDs.
    # User promises of volatility never qualify a user routine for this profile.
    unsafe = accepted('postgres', database, """SELECT p.oid::regprocedure::text FROM pg_proc p
        WHERE has_function_privilege(current_user,p.oid,'EXECUTE') AND
        (p.pronamespace <> 'pg_catalog'::regnamespace OR p.provolatile='v' OR
         p.proname IN ('txid_current','pg_current_xact_id') OR p.prosecdef) ORDER BY 1""")
    assert unsafe == '', 'demo can execute unapproved routines: ' + unsafe


@pytest.mark.parametrize('database', PG_DATABASES)
@pytest.mark.parametrize('user', ['admin', 'postgres'])
def test_postgres_writers_retain_temporary_large_object_and_ddl_rights(database, user):
    accepted('postgres', database, 'BEGIN; CREATE TEMP TABLE strict_writer_temp(i int); '
             'INSERT INTO strict_writer_temp VALUES (1); SELECT lo_create(0); ROLLBACK', user)


@pytest.mark.parametrize('database', MY_DATABASES)
def test_mysql_demo_only_reads(database):
    denied('mysql', database, 'CREATE TEMPORARY TABLE strict_read_temp(i int)')
    grants = accepted('mysql', database, 'SHOW GRANTS')
    assert grants == "GRANT SELECT, SHOW VIEW ON *.* TO `demo`@`%`", grants
    for user in ['admin', 'root']:
        accepted('mysql', database, 'CREATE TEMPORARY TABLE strict_writer_temp(i int); '
                 'INSERT INTO strict_writer_temp VALUES (1); DROP TEMPORARY TABLE strict_writer_temp', user)


def test_postgres_future_databases_schemas_and_owners():
    # Both creation paths must be safe immediately, before a maintenance script can run.
    for creator, template in [('admin', 'template1'), ('postgres', 'template0')]:
        db = 'strict_future_' + creator
        accepted('postgres', 'postgres', f'CREATE DATABASE {db} OWNER admin TEMPLATE {template}', creator)
        try:
            test_postgres_demo_cannot_make_temporary_objects(db)
            test_postgres_demo_cannot_create_large_objects(db)
            test_postgres_demo_has_no_unapproved_routines(db)
            for user in ['admin', 'postgres']:
                accepted('postgres', db, f"CREATE SCHEMA later_{user} AUTHORIZATION {user}; "
                         f"CREATE FUNCTION later_{user}.f() RETURNS int LANGUAGE sql AS 'SELECT 1'; "
                         f"CREATE PROCEDURE later_{user}.p() LANGUAGE sql AS 'SELECT 1'; "
                         f"CREATE FUNCTION later_{user}.definer() RETURNS int LANGUAGE sql SECURITY DEFINER AS 'SELECT 1'", user)
            test_postgres_demo_has_no_unapproved_routines(db)
            # A new owner has no ALTER DEFAULT PRIVILEGES entry in either template.
            accepted('postgres', db, 'CREATE ROLE strict_later_owner; CREATE SCHEMA later_owner AUTHORIZATION strict_later_owner; '
                     "SET ROLE strict_later_owner; CREATE FUNCTION later_owner.f() RETURNS int LANGUAGE sql AS 'SELECT 1'; RESET ROLE", 'postgres')
            test_postgres_demo_has_no_unapproved_routines(db)
        finally:
            accepted('postgres', 'postgres', f'DROP DATABASE {db} WITH (FORCE)', 'postgres')
            accepted('postgres', 'postgres', 'DROP ROLE IF EXISTS strict_later_owner', 'postgres')


def test_mysql_stored_routine_execution_is_refused():
    for database in MY_DATABASES:
        inventory = accepted('mysql', database, "SELECT routine_name,routine_type FROM information_schema.routines "
                             "WHERE routine_schema=DATABASE() ORDER BY 1", 'root')
        # Zero arguments can produce an arity error *after* EXECUTE permission.
        # Use a transaction and require access denial, never an arity error.
        for row in inventory.splitlines():
            name, kind = row.split('\t')
            params = accepted('mysql', database, "SELECT parameter_mode FROM information_schema.parameters "
                              f"WHERE specific_schema=DATABASE() AND specific_name='{name}' AND ordinal_position>0 ORDER BY ordinal_position", 'root')
            args = ','.join('@strict_read_out' if mode in ('OUT', 'INOUT') else 'NULL' for mode in params.splitlines())
            call = ('CALL' if kind == 'PROCEDURE' else 'SELECT') + f' `{name}`({args})'
            denied('mysql', database, call)


@pytest.mark.parametrize('database', PG_DATABASES)
def test_postgres_demo_cannot_change_persistent_data_or_schema(database):
    denied('postgres', database, 'BEGIN; CREATE TABLE public.strict_read_table(i int); ROLLBACK')
    table = accepted('postgres', database, "SELECT quote_ident(tablename) FROM pg_tables WHERE schemaname='public' ORDER BY tablename LIMIT 1")
    if not table:
        return  # postgres and template1 have no dataset tables
    column = accepted('postgres', database, "SELECT quote_ident(attname) FROM pg_attribute "
                      f"WHERE attrelid='public.{table}'::regclass AND attnum>0 AND NOT attisdropped ORDER BY attnum LIMIT 1")
    for statement in [f'INSERT INTO public.{table} SELECT * FROM public.{table} LIMIT 0',
                      f'UPDATE public.{table} SET {column}={column} WHERE false',
                      f'DELETE FROM public.{table} WHERE false',
                      f'ALTER TABLE public.{table} ADD COLUMN strict_read_column int',
                      f'DROP TABLE public.{table}']:
        denied('postgres', database, 'BEGIN; ' + statement + '; ROLLBACK')


def test_postgres_demo_exact_routine_allowlist():
    import re
    from pathlib import Path
    names = re.findall(r"\('([^']+)','[^']+'\)", Path('engines/postgres/init/read-routine-names.sql').read_text())
    sql_names = ','.join("'" + name + "'" for name in names)
    for database in PG_DATABASES:
        expected = accepted('postgres', database, "SELECT oid::regprocedure::text FROM pg_proc "
            f"WHERE proname IN ({sql_names}) AND pronamespace='pg_catalog'::regnamespace "
            "AND oid<16384 AND provolatile IN ('i','s') AND NOT prosecdef ORDER BY 1", 'postgres')
        actual = accepted('postgres', database, "SELECT oid::regprocedure::text FROM pg_proc "
            "WHERE has_function_privilege('demo',oid,'EXECUTE') ORDER BY 1", 'postgres')
        assert actual == expected, database + ': executable routines differ from the explicit policy'
        for signature in ['pg_read_file(text)', 'pg_reload_conf()', 'lo_import(text)']:
            assert accepted('postgres', database,
                f"SELECT has_function_privilege('admin','{signature}','EXECUTE')", 'postgres') == 'f'
