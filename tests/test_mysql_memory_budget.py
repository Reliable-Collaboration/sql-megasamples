"""Keep the running server's resource limit consistent with its memory consumers."""
from megasamples import config, engines


def size(value):
    value = value.lower()
    return int(value[:-1]) * {'m': 1 << 20, 'g': 1 << 30}[value[-1]]


def test_mysql_runtime_funds_temp_tables_pool_and_server_overhead():
    cfg = config.Config({'engines': {'mysql': {'datasets': ['pubs']}}})
    service = engines.get('mysql').compose_service(cfg)
    options = dict(arg.removeprefix('--').split('=', 1)
                   for arg in service['command'][1:])
    pool = size(options['innodb-buffer-pool-size'])
    # The observed 26.10 TempTable minimum is 1 GiB. Instrumented non-pool
    # allocations already exceed 256 MiB; reserve 512 MiB for those and threads.
    temporary_tables = size(options.get('temptable-max-ram', '1g'))
    overhead = 512 << 20
    assert size(service['mem_limit']) >= pool + temporary_tables + overhead, (
        'The container cannot fund TempTable, its buffer pool and server overhead; '
        'the full Contoso query was killed by its 1 GiB cgroup limit.')


def test_mysql_temp_table_allowance_does_not_grow_with_host_memory():
    cfg = config.Config({'engines': {'mysql': {'datasets': ['pubs']}}})
    command = engines.get('mysql').compose_service(cfg)['command']
    assert any(arg.startswith('--temptable-max-ram=') for arg in command), (
        'TempTable otherwise scales its allowance from host memory, independently '
        'of the container limit.')
