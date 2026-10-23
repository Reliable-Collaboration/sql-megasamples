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
    assert calls[-1] == ("docker", "rm", "-fv", "megasamples-reset-mysql")


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
