"""megasamples reset: what a reset is told to restore, before anything runs."""
import pytest

from megasamples import config as stack, datasets as inventory
from megasamples.engines import unique_databases
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
    assert chosen == {"mysql": unique_databases(inventory.select("quick"))}
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
