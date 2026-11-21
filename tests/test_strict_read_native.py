"""Opt-in, authenticated native regressions for the shipped read account.

MEGASAMPLES_NATIVE_READ_TESTS=1 enables these against a running isolated stack.
Only the explicitly supplied test containers are used; credentials use private files.
"""
import os
import subprocess

import pytest

from megasamples import config
from megasamples.copy_config import CopySettings
from megasamples.credentials import client, session
from megasamples.engines import unique_databases
from megasamples.engines.mysql.image_test import expected_demo_grants

pytestmark = pytest.mark.skipif(os.environ.get('MEGASAMPLES_NATIVE_READ_TESTS') != '1',
                                reason='requires explicitly enabled isolated native stack')
CFG = config.load()
TARGETS = {}   # engine -> the container ID the fixture checked


@pytest.fixture(scope='module', autouse=True)
def isolated_clients():
    if os.environ.get('MEGASAMPLES_NATIVE_READ_TESTS') != '1':
        yield
        return
    # The isolated store is named by the caller, and every target container must carry a task's
    # ownership label: a service container of a real deployment never does.
    graph = os.environ.get('DL077_ISOLATED_GRAPH')
    assert graph, 'set DL077_ISOLATED_GRAPH to the isolated store the test containers live in'
    store = subprocess.check_output(['docker', 'info', '--format', '{{.DockerRootDir}}'], text=True).strip()
    assert os.path.realpath(store) == os.path.realpath(graph)
    expected = os.environ.get('STRICT_READ_OWNER', '')
    assert expected, 'set STRICT_READ_OWNER to the owner label of the test containers'
    for engine in ('postgres', 'mysql'):
        container = os.environ.get('STRICT_READ_' + engine.upper() + '_CONTAINER')
        if container:
            inspected = subprocess.run(['docker', 'inspect', '-f',
                                        '{{.Id}} {{index .Config.Labels "org.sql-megasamples.gates.owner"}}',
                                        container], capture_output=True, text=True)
            fields = inspected.stdout.split()
            # The exact owner the caller names, as tests/gates/native.py's manifests require:
            # another task's container in the same store is refused.
            assert inspected.returncode == 0 and len(fields) == 2 and fields[1] == expected, container
            # Sol round 4, P2-2: every later command uses the ID checked here, never the name again,
            # so a replacement that reuses the name is never reached.
            TARGETS[engine] = fields[0]
    with session():
        yield


def batch_text(engine, text):
    """A library client's text with the mysql CLI's --batch backslash doubling (Sol round 12, 2), so grants on
    schemas with escaped underscores compare as the same grant on both paths. Only that escape: --batch also
    writes a tab, newline or NUL inside a value as \\t, \\n or \\0, which no statement here returns."""
    return text.replace('\\', '\\\\') if engine == 'mysql' else text


def query(engine, database, sql, user='demo'):
    container = TARGETS[engine]   # the checked ID, never a name
    if os.environ.get('STRICT_READ_NATIVE_DRIVER') == 'library':
        from docs.validation.strict_read_clients import query as native_query
        result = native_query(engine, container, user, database, sql)
        return subprocess.CompletedProcess(result.args, result.returncode, batch_text(engine, result.stdout),
                                           result.stderr)
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


PG_SELECTED = unique_databases(CFG.datasets('postgres'))
MY_SELECTED = unique_databases(CFG.datasets('mysql'))
PG_DATABASES = PG_SELECTED + ['megasamples', 'postgres', 'template1']
MY_DATABASES = MY_SELECTED + ['megasamples']


def selection_matches(names, datasets):
    """Whether the registry's names (one per database) are the configured datasets' databases: an append
    dataset shares its base's database and row, so the comparison is per database (Sol and Opus round 12)."""
    return sorted(names) == sorted(unique_databases(datasets))


# Sol round 11, 7: the checks follow the target's own dataset selection. The checkout's configuration must
# name the databases the checked image carries (its registry, one row per database), and dataset-specific
# cases run only where the selection holds their dataset. Whether an append dataset's tables are present is
# not something the registry's names show.
@pytest.mark.parametrize('engine', ['postgres', 'mysql'])
def test_target_carries_the_configured_selection(engine):
    if engine not in TARGETS:
        pytest.skip(f'no {engine} target named')
    names = accepted(engine, 'megasamples', 'SELECT name FROM datasets ORDER BY name',
                     'postgres' if engine == 'postgres' else 'root').splitlines()
    assert selection_matches(names, CFG.datasets(engine)), (
        'configure the checkout for the image under test: its registry lists ' + ', '.join(names))


@pytest.mark.parametrize('database', PG_DATABASES)
def test_postgres_demo_cannot_create_large_objects(database):
    for expression in ['lo_create(0)', 'lo_creat(-1)', "lo_from_bytea(0,decode('00','hex'))", "lo_import('/nonexistent')"]:
        denied('postgres', database, 'BEGIN; SELECT ' + expression + '; ROLLBACK')


@pytest.mark.parametrize('database', PG_DATABASES)
@pytest.mark.parametrize('user', ['admin', 'postgres'])
def test_postgres_writers_retain_temporary_large_object_and_ddl_rights(database, user):
    accepted('postgres', database, 'BEGIN; CREATE TEMP TABLE strict_writer_temp(i int); '
             'INSERT INTO strict_writer_temp VALUES (1); SELECT lo_create(0); ROLLBACK', user)


@pytest.mark.parametrize('database', MY_DATABASES)
def test_mysql_demo_only_reads(database):
    denied('mysql', database, 'CREATE TEMPORARY TABLE strict_read_temp(i int)')
    datasets = CFG.datasets('mysql')
    assert set(accepted('mysql', database, 'SHOW GRANTS').splitlines()) == expected_demo_grants(
        datasets, CopySettings(CFG, 'mysql', datasets).foreign)
    denied('mysql', database, 'SELECT COUNT(*) FROM mysql.user')
    for user in ['admin', 'root']:
        accepted('mysql', database, 'CREATE TEMPORARY TABLE strict_writer_temp(i int); '
                 'INSERT INTO strict_writer_temp VALUES (1); DROP TEMPORARY TABLE strict_writer_temp', user)


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


@pytest.mark.parametrize('database', PG_DATABASES)
def test_postgres_demo_reads_column_and_constraint_metadata(database):
    accepted('postgres', database, "SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public'")
    accepted('postgres', database, "SELECT constraint_name,column_name FROM information_schema.key_column_usage WHERE table_schema='public'")


def test_mysql_library_mode_shows_escapes_as_the_cli_does(monkeypatch):
    """Sol round 14, 3: query()'s library mode, through which the exact-grant check runs, brings the text to
    the CLI's form on every selection, by a value that always holds an escaped underscore."""
    if 'mysql' not in TARGETS:
        pytest.skip('no mysql target named')
    sql = "SELECT 'GRANT SELECT ON `copy\\\\_x`.*'"
    results = {}
    for driver in ('', 'library'):
        monkeypatch.setenv('STRICT_READ_NATIVE_DRIVER', driver)
        results[driver or 'cli'] = accepted('mysql', MY_SELECTED[0], sql)
    assert results['cli'] == results['library'] == 'GRANT SELECT ON `copy\\\\_x`.*', results


@pytest.mark.parametrize('engine', ['postgres', 'mysql'])
def test_native_protocol_matches_cli(engine, monkeypatch):
    from docs.validation.strict_read_clients import query as protocol_query
    container = TARGETS[engine]
    monkeypatch.delenv('STRICT_READ_NATIVE_DRIVER', raising=False)
    statements = ['SELECT 1, NULL', 'BEGIN; SELECT 1; SELECT 2; ROLLBACK']
    statements += (['SELECT current_user', 'BEGIN; CREATE TABLE public.parity_denied(i int); ROLLBACK']
                   if engine == 'postgres' else ['SHOW GRANTS', 'CREATE TEMPORARY TABLE parity_denied(i int)',
                                                 # Sol round 13, 5: an escaped underscore on every selection
                                                 "SELECT 'GRANT SELECT ON `copy\\\\_x`.*'"])
    database = (PG_SELECTED if engine == 'postgres' else MY_SELECTED)[0]   # one the selection carries
    for sql in statements:
        cli = query(engine, database, sql)
        protocol = protocol_query(engine, container, 'demo', database, sql)
        protocol = subprocess.CompletedProcess(protocol.args, protocol.returncode,
                                               batch_text(engine, protocol.stdout), protocol.stderr)
        assert (cli.returncode == 0) == (protocol.returncode == 0), sql
        if cli.returncode == 0:
            assert cli.stdout.strip() == protocol.stdout.strip(), sql
        else:
            assert 'denied' in cli.stderr.lower() and 'denied' in protocol.stderr.lower()
