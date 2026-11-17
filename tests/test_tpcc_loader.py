"""The latest Connector/C must reach the private server over its own loopback."""
from types import SimpleNamespace
import re

from megasamples.sources import tpcc_load


def test_tpcc_loader_shares_only_its_build_servers_network(monkeypatch):
    calls = []
    monkeypatch.setattr(tpcc_load.db, 'start', lambda: None)
    monkeypatch.setattr(tpcc_load.db, 'sql', lambda sql: None)
    monkeypatch.setattr(tpcc_load.db, 'NAME', 'isolated-build-mysql')

    def rows(sql):
        match = re.search(r'FROM `tpcc`\.`(\w+)1`', sql)
        if not match:
            return [['1']]
        name = match[1]
        count = {**tpcc_load.CARDINALITY, **tpcc_load.FIXED, 'order_line': 300000}[name]
        return [[str(count)]]

    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='10.88.0.1', stderr='')

    monkeypatch.setattr(tpcc_load.db, 'rows', rows)
    monkeypatch.setattr(tpcc_load.subprocess, 'run', run)
    tpcc_load.main(['--warehouses', '1'])
    loaders = [args for args in calls if args[:2] == ['docker', 'run']]
    assert len(loaders) == 1
    args = loaders[0]
    assert ('--network' in args) is True
    assert (args[args.index('--network') + 1] == 'container:isolated-build-mysql') is True
    assert ('--mysql-host=127.0.0.1' in args[-1]) is True
    assert all(args[:2] != ['docker', 'inspect'] for args in calls)
