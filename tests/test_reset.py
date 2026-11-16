"""megasamples reset: what a reset is told to restore, before anything runs."""
from subprocess import CompletedProcess

import pytest

from megasamples import config as stack, datasets as inventory, reset
from megasamples.engines import get, unique_databases
from megasamples.reset import plan

CFG = stack.Config({"engines": {"mysql": {"datasets": "quick"}, "postgres": {"datasets": "core"}, "sqlite": {"datasets": ["sakila"]}}})


def test_all_resets_every_engine_whole():
    assert plan(CFG, ["all"]) == {"mysql": None, "postgres": None, "sqlite": None}


def test_an_engine_name_resets_that_engine_whole():
    assert plan(CFG, ["postgres"]) == {"postgres": None}


def test_pairs_reset_single_databases_in_order():
    assert plan(CFG, ["postgres:northwind", "postgres:sakila", "sqlite:sakila"]) == {
        "postgres": unique_databases(["northwind", "sakila"]), "sqlite": unique_databases(["sakila"])}


def test_a_whole_engine_covers_its_pairs():
    assert plan(CFG, ["postgres:northwind", "postgres"]) == {"postgres": None}
    assert plan(CFG, ["postgres", "postgres:northwind"]) == {"postgres": None}


def test_flags_take_configures_selectors():
    chosen = plan(CFG, [], engines="mysql", datasets="quick")
    assert chosen == {"mysql": unique_databases(inventory.select("quick", include_prerequisites=False))}
    assert plan(CFG, [], engines="postgres,sqlite") == {"postgres": None, "sqlite": None}
    assert plan(CFG, [], datasets="sakila") == {e: unique_databases(["sakila"]) for e in ("mysql", "postgres", "sqlite")}


def test_a_dataset_sharing_a_database_resets_that_database_once():
    shared = [d for d in inventory.names() if inventory.load(d).get("append")]
    if not shared:
        pytest.skip("no dataset appends to another")
    names = inventory.select([shared[0]])
    cfg = stack.Config({"engines": {"mysql": {"datasets": names}}})
    assert plan(cfg, [f"mysql:{shared[0]}"]) == {"mysql": unique_databases(names)}
    assert len(plan(cfg, [f"mysql:{shared[0]}"])["mysql"]) == len(set(unique_databases(names)))


@pytest.mark.parametrize("targets, problem", [
    ([], "name what to reset"),
    (["oracle"], "is not in the stack"),
    (["sqlite:northwind"], "does not ship `northwind`"),
    (["postgres:no_such_dataset"], "no_such_dataset"),
])
def test_problems_are_named_before_anything_runs(targets, problem, capsys):
    with pytest.raises(SystemExit) as stopped:
        plan(CFG, targets)
    assert problem in str(stopped.value) + capsys.readouterr().err


@pytest.mark.parametrize("flags", [False, True])
def test_reset_does_not_include_cross_database_prerequisites(flags):
    cfg = stack.Config({"engines": {"mysql": {"datasets": ["oracle_oe"]}}})
    assert "oracle_hr" in cfg.datasets("mysql")
    selected = plan(cfg, [], engines="mysql", datasets="oracle_oe") if flags else plan(cfg, ["mysql:oracle_oe"])
    assert selected == {"mysql": ["oracle_oe"]}


def result(args, stdout="", code=0):
    return CompletedProcess(args, code, stdout, "test failure" if code else "")


@pytest.mark.parametrize("failure", [None, "body", "ready", "timeout", "run"])
def test_pristine_pins_running_image_and_cleans_up(monkeypatch, failure):
    calls = []
    def sh(*args, **kwargs):
        calls.append(args)
        return result(args, "sha256:running-build\n" if args[1] == "inspect" else "",
                      int(failure == "run" and args[1] == "run"))
    def ready(name):
        if failure == "ready":
            raise RuntimeError("readiness failed")
        return True
    monkeypatch.setattr(reset, "sh", sh)
    monkeypatch.setattr(reset, "READY_SECONDS", 0 if failure == "timeout" else 120)
    def run():
        with reset.Pristine(get("mysql"), ready):
            if failure == "body":
                raise RuntimeError("restore failed")
    if failure:
        with pytest.raises((RuntimeError, SystemExit)):
            run()
    else:
        run()
    started = next(c for c in calls if c[1] == "run")
    assert started[-1] == "sha256:running-build"
    assert "--rm" in started
    name = started[started.index("--name") + 1]
    assert name.startswith("megasamples-reset-mysql-")
    assert calls[-1] == ("docker", "rm", "-fv", name)


def test_missing_postgres_source_does_not_drop_target(monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(reset, "Pristine", lambda *a: nullcontext(type("Source", (), {"name": "pristine"})()))
    calls = []
    def pg(*args):
        calls.append(args)
        return result(args, code=1)
    monkeypatch.setattr(reset, "pg", pg)
    with pytest.raises(SystemExit, match="source database is unavailable"):
        reset.reset_postgres(get("postgres"), ["sakila"])
    assert calls == [("pristine", "SELECT 1", "sakila")]


@pytest.mark.parametrize("failure", [False, True])
def test_sqlite_restores_both_copies_from_pristine(monkeypatch, failure):
    from contextlib import nullcontext
    monkeypatch.setattr(reset, "Pristine", lambda *a: nullcontext(type("Source", (), {"name": "pristine"})()))
    calls = []
    def sh(*args, **kwargs):
        calls.append(args)
        if "sha256sum" in args:
            return result(args, ("bad" if failure and args[2] != "pristine" else "original") + "  file\n")
        return result(args)
    monkeypatch.setattr(reset, "sh", sh)
    if failure:
        with pytest.raises(SystemExit, match="differs from the image"):
            reset.reset_sqlite(get("sqlite"), ["sakila"])
    else:
        assert reset.reset_sqlite(get("sqlite"), ["sakila"]) == 0
        targets = [c[-1] for c in calls if c[1] == "cp"]
        assert "megasamples-sqlite:/data/.sakila.sqlite.part" in targets
        assert "megasamples-sqlite:/shared/.sakila.sqlite.part" in targets
    assert any(c[1:3] == ("cp", "pristine:/data/sakila.sqlite") for c in calls)
    assert not any(c[1] == "cp" and c[2].startswith("megasamples-sqlite:") for c in calls)


@pytest.mark.parametrize("target", ["sqlite", "sqlite:sakila"])
@pytest.mark.parametrize("failure", [False, True])
def test_sqlite_consoles_stop_before_reset_and_restart_after(monkeypatch, target, failure):
    events = []
    monkeypatch.setattr(reset.stack, "load", lambda: CFG)
    monkeypatch.setattr(reset.os.path, "exists", lambda p: True)
    def sh(*args, **kwargs):
        if "ps" in args:
            # DbGate is stopped already and must remain stopped.
            return result(args, "sqlite\ncloudbeaver\nadminer\n")
        events.append(args[-2:])
        return result(args)
    def restore(*args):
        events.append("restore")
        if failure:
            raise RuntimeError("restore failed")
        return 0
    monkeypatch.setattr(reset, "sh", sh)
    monkeypatch.setattr(reset, "reset_engines", restore)
    monkeypatch.setitem(reset.RESET_DATABASES, "sqlite", restore)
    if failure:
        with pytest.raises(RuntimeError):
            reset.main([target])
    else:
        assert reset.main([target]) == 0
    assert events == [("stop", "cloudbeaver"), "restore", ("start", "cloudbeaver")]


def test_pristine_instances_never_remove_each_others_container(monkeypatch):
    calls = []
    def sh(*args):
        calls.append(args)
        return result(args, "sha256:running-build" if args[1] == "inspect" else "")
    monkeypatch.setattr(reset, "sh", sh)
    with reset.Pristine(get("postgres"), lambda c: True) as first:
        with reset.Pristine(get("postgres"), lambda c: True) as second:
            assert first.name != second.name
            assert not any(c[1] == "rm" for c in calls)
        assert calls[-1] == ("docker", "rm", "-fv", second.name)
    assert calls[-1] == ("docker", "rm", "-fv", first.name)


def test_reset_lock_rejects_other_process_and_releases_after_failure(monkeypatch, tmp_path):
    import subprocess, sys
    monkeypatch.setattr(reset.tempfile, "tempdir", str(tmp_path))
    script = """
import sys, tempfile
from megasamples.reset import reset_locks
tempfile.tempdir = sys.argv[1]
with reset_locks(sys.argv[2:]):
    print('acquired')
"""
    def contender(*engines):
        return subprocess.run([sys.executable, "-c", script, str(tmp_path), *engines],
                              capture_output=True, text=True, timeout=10)
    with pytest.raises(RuntimeError):
        with reset.reset_locks(["postgres"]):
            blocked = contender("mysql", "postgres")
            assert blocked.returncode != 0
            assert "another reset is already running for postgres" in blocked.stderr
            # The failed multi-engine acquisition must release its earlier MySQL lock.
            assert contender("mysql").returncode == 0
            raise RuntimeError("reset failed")
    assert contender("postgres").returncode == 0


@pytest.mark.parametrize("target", ["postgres", "postgres:northwind", "all"])
def test_busy_engine_aborts_before_any_container_changes(monkeypatch, tmp_path, target):
    monkeypatch.setattr(reset.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(reset.stack, "load", lambda: CFG)
    monkeypatch.setattr(reset.os.path, "exists", lambda p: True)
    def unexpected(*args, **kwargs):
        pytest.fail("container command ran before acquiring every lock")
    monkeypatch.setattr(reset, "sh", unexpected)
    monkeypatch.setattr(reset.subprocess, "run", unexpected)
    with reset.reset_locks(["postgres"]):
        with pytest.raises(SystemExit, match="already running for postgres"):
            reset.main([target])


def test_whole_sqlite_reset_removes_wal_before_copy(monkeypatch, tmp_path):
    import shutil, sqlite3, subprocess, sys
    from megasamples.engines.sqlite import ENGINE
    data, shared = tmp_path / "data", tmp_path / "shared"
    data.mkdir(); shared.mkdir()
    with sqlite3.connect(data / "probe.sqlite") as db:
        db.execute("create table t(x)")
        db.execute("insert into t values(1)")
    db.close()
    shutil.copy(data / "probe.sqlite", shared / "probe.sqlite")
    # A committed WAL left by a crashed writer must not replay over the replacement database.
    subprocess.run([sys.executable, "-c", """
import sqlite3, os, sys
c = sqlite3.connect(sys.argv[1])
c.execute('pragma journal_mode=wal')
c.execute('pragma wal_autocheckpoint=0')
c.execute('update t set x=99')
c.commit()
os._exit(0)
""", str(shared / "probe.sqlite")], check=True, timeout=10)
    assert (shared / "probe.sqlite-wal").exists()
    (shared / "other.sqlite-journal").touch()
    real_run = subprocess.run
    def local(command):
        return command.replace("$$", "$").replace("/data/", str(data) + "/").replace("/shared/", str(shared) + "/")
    def sh(*args):
        assert args[1] == "compose" and "run" in args and "--rm" in args
        return real_run(["sh", "-c", local(args[-1])], capture_output=True, text=True)
    def recreate(args, **kwargs):
        assert "up" in args
        assert not list(shared.glob("*.sqlite-wal"))
        assert not list(shared.glob("*.sqlite-shm"))
        assert not list(shared.glob("*.sqlite-journal"))
        command = ENGINE.compose_service(CFG)["command"][2]
        return real_run(["sh", "-c", local(command).replace("exec sleep infinity", "true")])
    monkeypatch.setattr(reset, "data_volumes", lambda c: [])
    monkeypatch.setattr(reset, "sh", sh)
    monkeypatch.setattr(reset.subprocess, "run", recreate)
    assert reset.reset_engines(["sqlite"]) == 0
    with sqlite3.connect(shared / "probe.sqlite") as db:
        assert db.execute("select x from t").fetchone() == (1,)
    db.close()


def test_failed_sqlite_cleanup_does_not_recreate(monkeypatch):
    monkeypatch.setattr(reset, "data_volumes", lambda c: [])
    monkeypatch.setattr(reset, "sh", lambda *a: result(a, code=1))
    monkeypatch.setattr(reset.subprocess, "run", lambda *a, **kw: pytest.fail("recreated after cleanup failed"))
    with pytest.raises(SystemExit, match="could not remove stale SQLite journals"):
        reset.reset_engines(["sqlite"])


@pytest.mark.parametrize("scenario", ["noisy", "source_failure", "target_failure", "early_exit", "missing_target"])
def test_pipe_completes_and_reports_failures(scenario):
    import os, signal, subprocess, sys
    # Isolate the process group so a regression cannot hang pytest or leave children behind.
    script = r'''
import sys
from megasamples.reset import pipe
scenario = sys.argv[1]
source = "import sys; sys.stderr.write('warning\\n' * 20000); sys.stderr.flush(); sys.stdout.write('data')"
target = "import sys; assert sys.stdin.read() == 'data'"
if scenario == 'source_failure':
    source = "import sys; sys.exit(7)"
    target = "import sys; sys.stdin.read()"
elif scenario == 'target_failure':
    target = "import sys; sys.stdin.read(); sys.exit(9)"
elif scenario in ('early_exit', 'missing_target'):
    source = "import os;\nwhile True: os.write(1, b'x' * 65536)"
    target = "import sys; sys.exit(9)"
if scenario == 'missing_target':
    try:
        pipe([sys.executable, '-c', source], ['/no/such/reset-test-command'])
    except FileNotFoundError:
        pass
    else:
        raise AssertionError('missing target did not raise')
else:
    error = pipe([sys.executable, '-c', source], [sys.executable, '-c', target])
    if scenario == 'noisy':
        assert error is None, error
    else:
        assert error, 'failed command returned success'
'''
    process = subprocess.Popen([sys.executable, "-c", script, scenario], start_new_session=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr.decode()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
