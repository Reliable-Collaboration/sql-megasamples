"""Run each image gate's registry/count checks with a changing feed and a shared database."""
import importlib
import json
import re
from pathlib import Path
from subprocess import CompletedProcess

import pytest
import yaml

from megasamples import paths, registry


@pytest.fixture
def hub_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "BUILD", str(tmp_path))
    (tmp_path / "live").mkdir()
    for name, counts in [("chicago_crimes", {"crimes": 260000, "iucr": 434}),
                         ("chicago_crimes_full", {"crimes_all": 8400000})]:
        (tmp_path / "live" / f"{name}.observed.yaml").write_text(yaml.safe_dump({"counts": counts}))
    return tmp_path


@pytest.mark.parametrize("engine", ["mysql", "postgres", "sqlite"])
@pytest.mark.parametrize("append", [False, True])
def test_image_gate_checks_exact_hub_snapshot_and_one_registry_row_per_database(engine, append, hub_counts, monkeypatch):
    tester = importlib.import_module(f"megasamples.engines.{engine}.image_test")
    targets = ["chicago_crimes", "chicago_crimes_full"] if append else ["chicago_crimes"]
    actual = {"crimes": 260000, "iucr": 434, "crimes_all": 8400000}
    overrides = {}

    def sh(*args, **kwargs):
        if "run" in args:
            if "--env-file" in args:
                path = Path(args[args.index("--env-file") + 1])
                assert path.stat().st_mode & 0o777 == 0o600
                overrides.update(line.split("=", 1) for line in path.read_text().splitlines())
            for i, value in enumerate(args[:-1]):
                if value == "-e":
                    key, value = args[i + 1].split("=", 1)
                    overrides[key] = value
        return CompletedProcess([], 0, "", "")

    def q(sql, *args, **kwargs):
        if kwargs.get("container") == tester.NAME + "2":
            key = ("DEMO_PASSWORD" if kwargs.get("user") == "demo" else
                   "MYSQL_ROOT_PASSWORD" if engine == "mysql" else "POSTGRES_PASSWORD")
            return CompletedProcess([], int(kwargs.get("pw") != overrides[key]), "", "")
        upper = sql.upper()
        if "SELECT NAME FROM" in upper:
            answer = "chicago_crimes\n"
        elif "COUNT(*) FROM" in upper:
            table = re.search(r'FROM\s+[`"]?(\w+)', sql, re.I)[1]
            answer = str(actual[table]) + "\n"
        elif upper.startswith("CHECK TABLE"):
            answer = "OK\n"
        elif "INTEGRITY_CHECK" in upper:
            answer = "ok\n"
        elif "JOURNAL_MODE" in upper:
            answer = "delete\n"
        elif "PAGE_COUNT" in upper:
            answer = "0\n"
        else:
            answer = "1\n" if upper == "SELECT 1" else ""
        return CompletedProcess([], 0, answer, "")

    class CountsChecked(Exception):
        pass

    class Checks:
        seen = 0

        def expect(self, condition, label):
            assert condition, label
            if "tables match" in label:
                self.seen += 1
                if self.seen == len(targets):
                    raise CountsChecked

    monkeypatch.setattr(tester, "q", q)
    monkeypatch.setattr(tester, "sh", sh)
    if hasattr(tester, "q_net"):
        monkeypatch.setattr(tester, "q_net", q)
    monkeypatch.setattr(tester, "Checks", Checks)
    with pytest.raises(CountsChecked):
        tester.main(targets)


def test_registry_records_observed_live_counts_not_historical_floors(hub_counts):
    sql = registry.render(["chicago_crimes", "chicago_crimes_full"], "test")
    assert json.dumps({"crimes": 260000, "iucr": 434, "crimes_all": 8400000}) in sql


@pytest.mark.parametrize("bad_counts", [None, {"crimes": 1, "iucr": 434}, {"iucr": 434}])
def test_live_image_provenance_requires_complete_verified_counts(hub_counts, bad_counts):
    path = hub_counts / "live/chicago_crimes.observed.yaml"
    if bad_counts is None:
        path.unlink()
    else:
        path.write_text(yaml.safe_dump({"counts": bad_counts}))
    with pytest.raises(ValueError, match="hub count"):
        registry.render(["chicago_crimes"], "test")
