#!/usr/bin/env python3
"""Run the verification stages (ARCHITECTURE.md section 5) against a loaded dataset on an engine.

  python3 -m megasamples verify <dataset> [stage ...] [--engine mysql] [--pin]

Stages: counts (S3), digests (S4), fks (S5), indexes (S6), views (S4v), routines (S8), triggers
(S9), explain (S6), smoke (S7). Default: all the engine supports. The expectations under
datasets/<name>/tests/ are engine-neutral: every engine is checked against the same counts, the
same canonical digests, the same foreign keys, the same index set, the same view results, the same
routine outputs and the same trigger effects, which is what makes a port provably the same
database as the MySQL corpus. explain and smoke are MySQL-only, since their queries are written in
MySQL's dialect; routines and triggers scenarios are written in MySQL's dialect too, and the ports
translate them with the same translator that ported the objects (megasamples/port/sqltranslate.py).

A dataset marked `live: true` in its dataset.yaml is built from a feed that changes, so its tests/
files describe a snapshot rather than a pin: counts are floors (a feed grows, and a short download
shows as a shortfall), the content digests of tables and views are compared for their column sets
only, and the smoke queries are run but their results not compared. Everything structural -- foreign
keys, indexes, routines, triggers, query plans -- is held exactly. The hub's build records what it
holds under build/live/, and a port is held to that exactly, so the three engines hold the same rows.

`--pin` writes the observed values into the tests/ files instead of comparing, and is allowed on
MySQL only: expectations come from the hub, never from a port. It is how a native-SQL dataset with
no converter-side baseline gets its first values (knowledge/decisions/test-checksum-method.md).
"""
import argparse, json, os, sys

import yaml

from megasamples.paths import BUILD, ROOT


def dataset_dir(name):
    return os.path.join(ROOT, "datasets", name)


def load_yaml(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def dump_yaml(path, data, header):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header.rstrip("\n") + "\n")
        yaml.safe_dump(data, fh, sort_keys=True, default_flow_style=False, allow_unicode=True)


def live_hub_observed(cfg, ad, stage, observed, res):
    """A live dataset's rows are today's, so the tests/ files cannot hold a port to them. On the hub
    (MySQL) this records what this machine's build holds, per stage, under build/live/; on a port it
    returns that record as the expectation, so the ports are held to the hub built beside them --
    exactly, as every other dataset's are to the tests/ files. None on the hub; None on a port with
    a failure noted when the hub has not been built on this machine."""
    path = os.path.join(BUILD, "live", f"{cfg.get('name') or cfg['database']}.observed.yaml")
    if ad.name == "mysql":
        data = (load_yaml(path) or {}) if os.path.exists(path) else {}
        data[stage] = observed
        os.makedirs(os.path.dirname(path), exist_ok=True)
        dump_yaml(path, data, "# What this machine's MySQL build of a live dataset holds, stage by stage: its ports are\n"
                              "# verified against this, since the tests/ files describe a snapshot of another day.")
        return None
    data = load_yaml(path) or {}
    if stage not in data:
        res.fail(f"live dataset: no record of the hub's {stage} on this machine ({os.path.relpath(path, ROOT)}); "
                 "build it on MySQL first")
        return None
    return data[stage]


class Result:
    def __init__(self): self.failures, self.notes = [], []
    def fail(self, msg): self.failures.append(msg)
    def note(self, msg): self.notes.append(msg)


def extended_tables(database):
    """Tables that an `append: true` dataset declares for this database."""
    owned = set()
    root = os.path.join(ROOT, "datasets")
    for name in sorted(os.listdir(root)):
        config = os.path.join(root, name, "dataset.yaml")
        if not os.path.exists(config):
            continue
        other = load_yaml(config) or {}
        if other.get("append") and other.get("database") == database:
            counts = load_yaml(os.path.join(root, name, "tests", "expected_counts.yaml")) or {}
            owned |= set(counts)
    return owned


def own_tables(cfg, d, tables):
    """The tables this dataset is responsible for: all of them, or for an `append: true` dataset the
    ones its own expected_counts.yaml names, so a shared database is not accounted for twice."""
    if not cfg.get("append"):
        return tables
    mine = load_yaml(os.path.join(d, "tests", "expected_counts.yaml")) or {}
    return [t for t in tables if t in mine]


def stage_counts(ad, cfg, schema, d, pin, res):
    path = os.path.join(d, "tests", "expected_counts.yaml")
    observed = {t: ad.count(schema, t) for t in ad.tables(schema)}
    if pin and os.path.exists(path) and open(path, encoding="utf-8").readline().startswith("# authority:"):
        res.note(f"counts not pinned: {os.path.relpath(path)} is generated from the source")
        pin = False
    if pin and cfg.get("append"):
        declared = load_yaml(path)
        if declared is None:
            res.fail(f"{cfg['database']}: an append dataset needs its table list written by hand "
                     f"in {os.path.relpath(path)} before counts can be pinned"); return
        missing = sorted(set(declared) - set(observed))
        if missing:
            res.fail(f"declared table(s) not present: {', '.join(missing)}"); return
        header = "".join(line for line in open(path, encoding="utf-8")
                         if line.startswith("#")) or "# S3: row count per table.\n"
        dump_yaml(path, {t: observed[t] for t in declared}, header.rstrip("\n"))
        res.note(f"counts pinned for the {len(declared)} table(s) this dataset declares"); return
    if pin:
        dump_yaml(path, observed, "# S3: row count per table. Pinned from a verified load.")
        res.note(f"counts pinned for {len(observed)} tables"); return
    expected = load_yaml(path)
    if expected is None:
        res.fail(f"no expected_counts.yaml for {cfg['database']}; run with --pin"); return
    live = bool(cfg.get("live"))
    if live:
        hub = live_hub_observed(cfg, ad, "counts", observed, res)
        if ad.name != "mysql":
            if hub is None:
                return
            expected, live = hub, False      # a port is held to the hub's rows, exactly
    for table, want in sorted(expected.items()):
        got = observed.get(table)
        if got is None:
            res.fail(f"table {table} missing (expected {want} rows)")
        elif live and got < want:
            res.fail(f"{table}: {got} rows, below the snapshot's {want} (a live feed grows; a short download?)")
        elif not live and got != want:
            res.fail(f"{table}: {got} rows, expected {want}")
    if cfg.get("append"):
        res.note(f"counts OK for {len(expected)} table(s) added to `{cfg['database']}` "
                 f"({len(observed) - len(expected)} more belong to the core dataset)")
        return
    extended = extended_tables(cfg["database"])
    unexpected = sorted(set(observed) - set(expected) - extended)
    shared = sorted((set(observed) - set(expected)) & extended)
    for extra in unexpected:
        res.fail(f"unexpected table {extra} ({observed[extra]} rows)")
    if shared:
        res.note(f"ignoring {len(shared)} extended-tier table(s) also loaded here: " + ", ".join(shared))
    res.note(f"counts OK for {len(expected)} tables" + (" (live feed: floors)" if live else ""))


def stage_digests(ad, cfg, schema, d, pin, res):
    from megasamples import canon
    path = os.path.join(d, "tests", "checksums.yaml")
    excluded = load_yaml(os.path.join(d, "tests", "digest_exclude.yaml"), {}) or {}
    observed = {}
    for table in own_tables(cfg, d, ad.tables(schema)):
        cols = [c for c in ad.columns(schema, table) if c[0] not in (excluded.get(table, {}) or {})]
        n, x, s = ad.fingerprint(schema, table, cols)
        observed[table] = {"n": n, "x": x, "s": s,
                           "columns": [c for c, t in cols if t.lower() not in canon.EXCLUDED],
                           "excluded": [c for c, t in cols if t.lower() in canon.EXCLUDED]}
    if pin:
        dump_yaml(path, observed,
                  "# S4: canonical per-table fingerprint (count, BIT_XOR, SUM mod 2^64) over the\n"
                  "# row digest defined in megasamples/canon.py. float/double/json columns are excluded.")
        res.note(f"digests pinned for {len(observed)} tables"); return
    expected = load_yaml(path)
    if expected is None:
        res.fail(f"no checksums.yaml for {cfg['database']}; run with --pin"); return
    live = bool(cfg.get("live"))
    if live:
        hub = live_hub_observed(cfg, ad, "digests", observed, res)
        if ad.name != "mysql":
            if hub is None:
                return
            expected, live = hub, False      # a port is held to the hub's digests, exactly
    for table, want in sorted(expected.items()):
        got = observed.get(table)
        if not got:
            res.fail(f"table {table} missing for digest"); continue
        if got["columns"] != want["columns"]:
            res.fail(f"{table}: digested column set changed {want['columns']} -> {got['columns']}"); continue
        if live:
            continue   # the rows are today's; the snapshot's digest describes another day's
        for k in ("n", "x", "s"):
            if got[k] != want[k]:
                res.fail(f"{table}: digest {k} {got[k]} != expected {want[k]}")
    res.note(f"digests OK for {len(expected)} tables" + (" (live feed: column sets only)" if live else ""))


def stage_fks(ad, cfg, schema, d, pin, res):
    fks = ad.foreign_keys(schema)
    orphans, external = 0, 0
    for name, table, col, rschema, rtable, rcol in fks:
        external += rschema != schema
        n = ad.orphans(schema, table, col, rschema, rtable, rcol)
        if n:
            res.fail(f"foreign key {name} ({table}.{col} -> {rschema}.{rtable}.{rcol}) has {n} orphan rows")
            orphans += n
    across = f" ({external} across databases)" if external else ""
    res.note(f"{len(fks)} foreign keys validated{across}, {orphans} orphans")


def stage_indexes(ad, cfg, schema, d, pin, res):
    path = os.path.join(d, "tests", "indexes.yaml")
    mine = set(own_tables(cfg, d, ad.tables(schema)))
    observed = {t: idx for t, idx in ad.indexes(schema).items() if t in mine}
    if pin:
        dump_yaml(path, observed, "# S6: every index that must exist after load.")
        res.note(f"indexes pinned for {len(observed)} tables"); return
    expected = load_yaml(path)
    if expected is None:
        res.fail(f"no indexes.yaml for {cfg['database']}; run with --pin"); return
    skipped = 0
    for table, want in sorted(expected.items()):
        got = observed.get(table, {})
        for index, spec in sorted(want.items()):
            if not ad.carries_index(spec):
                skipped += 1
                continue
            if index not in got:
                res.fail(f"{table}: index {index} missing"); continue
            for k in ("unique", "type", "columns"):
                if got[index][k] != spec[k]:
                    res.fail(f"{table}.{index}: {k} {got[index][k]} != expected {spec[k]}")
        for extra in sorted(set(got) - set(want)):
            res.fail(f"{table}: unexpected index {extra}")
    res.note(f"indexes OK for {len(expected)} tables" + (f" ({skipped} not carried by {ad.name})" if skipped else ""))


def stage_explain(ad, cfg, schema, d, pin, res):
    spec = load_yaml(os.path.join(d, "tests", "explain.yaml"))
    if not spec:
        res.note("no explain.yaml, skipped"); return
    for case in spec:
        plan = json.loads(ad.explain_json(schema, case["query"]))
        blob = json.dumps(plan)
        for table in case.get("must_not_full_scan", []):
            marker = f'"table_name": "{table}"'
            idx = blob.find(marker)
            if idx < 0:
                # A unique-index lookup on a constant can be resolved before execution, and the
                # table then does not appear in the plan at all -- the strongest access path, not
                # a missing table -- but a typo would look the same, so it only passes when the plan
                # says the rows were fetched before execution.
                if "Rows fetched before execution" in blob or '"const"' in blob:
                    continue
                res.fail(f"{case['name']}: table {table} not in the plan"); continue
            window = blob[idx:idx + 400]
            if '"access_type": "ALL"' in window:
                res.fail(f"{case['name']}: {table} is a full scan")
    res.note(f"explain OK for {len(spec)} queries")


def stage_smoke(ad, cfg, schema, d, pin, res):
    path = os.path.join(d, "tests", "smoke.expected.yaml")
    spec = load_yaml(os.path.join(d, "tests", "smoke.yaml"))
    if not spec:
        res.note("no smoke.yaml, skipped"); return
    observed = {c["name"]: ad.query_text(schema, c["query"]) for c in spec}
    if pin:
        dump_yaml(path, observed, "# S7: canonical query results, tab-separated as the client prints them.")
        res.note(f"smoke results pinned for {len(observed)} queries"); return
    expected = load_yaml(path)
    if expected is None:
        res.fail(f"no smoke.expected.yaml for {cfg['database']}; run with --pin"); return
    if cfg.get("live"):
        res.note(f"smoke: {len(observed)} queries ran (live feed: results not compared)"); return
    for name, want in sorted(expected.items()):
        got = observed.get(name)
        if got != want:
            res.fail(f"smoke {name}:\n    expected {want!r}\n    got      {got!r}")
    res.note(f"smoke OK for {len(expected)} queries")


def stage_views(ad, cfg, schema, d, pin, res):
    """Every view's row count and canonical digest, pinned from MySQL: a ported view is right when
    it returns the same rows, not merely when it exists."""
    from megasamples import canon
    path = os.path.join(d, "tests", "views.yaml")
    expected = None if pin else load_yaml(path)
    observed = {}
    for view in ad.views(schema):
        cols = ad.view_columns(schema, view)
        n, x, s = ad.fingerprint(schema, view, cols)
        observed[view] = {"n": n, "x": x, "s": s,
                          "columns": [c for c, t in cols if t.lower() not in canon.EXCLUDED],
                          "excluded": [c for c, t in cols if t.lower() in canon.EXCLUDED]}
        # a decimal the view computes is exact on MySQL and PostgreSQL and floating-point on
        # SQLite: the digest without those columns is pinned too, and SQLite is held to that one
        inexact = (ad.view_inexact_columns(schema, view) if pin else (expected or {}).get(view, {}).get("inexact")) or []
        if inexact:
            exact_cols = [(c, t) for c, t in cols if c not in inexact]
            _, x2, s2 = ad.fingerprint(schema, view, exact_cols)
            observed[view].update({"inexact": sorted(inexact), "x_exact": x2, "s_exact": s2})
    if pin:
        dump_yaml(path, observed, "# S4v: every view's row count and canonical fingerprint (count, BIT_XOR, SUM mod\n"
                                  "# 2^64) over the row digest of megasamples/canon.py, pinned from MySQL. x_exact and\n"
                                  "# s_exact leave out the `inexact` columns: decimals the view computes, which an engine\n"
                                  "# without decimal arithmetic (SQLite) cannot reproduce to the digit.")
        res.note(f"views pinned for {len(observed)} views"); return
    if expected is None:
        if observed:
            res.fail(f"no views.yaml for {cfg['database']}; run with --pin"); return
        res.note("no views"); return
    live = bool(cfg.get("live"))
    if live:
        hub = live_hub_observed(cfg, ad, "views", observed, res)
        if ad.name != "mysql":
            if hub is None:
                return
            expected, live = hub, False      # a port is held to the hub's views, exactly
    absent = ad.views_not_ported(schema)
    checked, by_count, without = 0, [], []
    for view, want in sorted(expected.items()):
        if view in absent:
            continue
        got = observed.get(view)
        if not got:
            res.fail(f"view {view} missing"); continue
        if got["columns"] != want["columns"]:
            res.fail(f"view {view}: digested column set changed {want['columns']} -> {got['columns']}"); continue
        if live:
            checked += 1
            continue   # the hub's rows are today's; the snapshot's digest describes another day's
        # a GROUP_CONCAT with no ORDER BY concatenates in whatever order the engine reads the rows,
        # which MySQL itself leaves unspecified; such a view is held to its row count
        if ad.view_has_unordered_aggregate(schema, view):
            keys = ("n",)
            by_count.append(view)
        elif want.get("inexact") and not ad.exact_decimals:
            keys = ("n", "x_exact", "s_exact")
            without.append(view)
        else:
            keys = ("n", "x", "s")
        for k in keys:
            if got.get(k) != want.get(k):
                res.fail(f"view {view}: digest {k} {got.get(k)} != expected {want.get(k)}")
        checked += 1
    res.note(f"views OK for {checked} views" + (" (live feed: column sets only)" if live else "")
             + (f"; {len(by_count)} compared by row count only (unordered GROUP_CONCAT): {', '.join(by_count)}" if by_count else "")
             + (f"; {len(without)} compared without their computed decimals (no decimal arithmetic on {ad.name}): {', '.join(without)}" if without else "")
             + (f"; {len(absent)} not ported on {ad.name}" if absent else ""))


def stage_routines(ad, cfg, schema, d, pin, res):
    """Every call in tests/routines.yaml, run inside a transaction that is rolled back, printed by
    the engine's client and compared line by line (megasamples/probe.py) with what MySQL printed."""
    from megasamples import probe
    spec = load_yaml(os.path.join(d, "tests", "routines.yaml"))
    path = os.path.join(d, "tests", "routines.expected.yaml")
    if not spec:
        res.note("no routines.yaml, skipped"); return
    absent = ad.routines_not_ported(schema)
    observed, skipped = {}, []
    for case in spec:
        if case["routine"] in absent:
            skipped.append(case["name"]); continue
        observed[case["name"]] = ad.call_routine(schema, case)
    if pin:
        dump_yaml(path, observed, "# S8: what each call in routines.yaml prints on MySQL, normalised and sorted line by\n"
                                  "# line (megasamples/probe.py); 'ERROR' when the call must fail.")
        res.note(f"routine calls pinned for {len(observed)} calls"); return
    expected = load_yaml(path)
    if expected is None:
        res.fail(f"no routines.expected.yaml for {cfg['database']}; run with --pin"); return
    checked = 0
    for name, want in sorted(expected.items()):
        if name not in observed:
            if name in skipped:
                continue
            res.fail(f"routine call {name} not run"); continue
        got = observed[name]
        if got != want:
            res.fail(f"routine call {name}:\n    expected {want!r}\n    got      {got!r}")
        checked += 1
    res.note(f"routine calls OK for {checked} calls"
             + (f"; {len(skipped)} skipped, routine not ported on {ad.name}: {', '.join(skipped)}" if skipped else ""))


def stage_triggers(ad, cfg, schema, d, pin, res):
    """Every scenario in tests/triggers.yaml: its statements run inside a transaction, the probe
    query is printed, the transaction is rolled back; compared with MySQL like the routine calls."""
    spec = load_yaml(os.path.join(d, "tests", "triggers.yaml"))
    path = os.path.join(d, "tests", "triggers.expected.yaml")
    if not spec:
        res.note("no triggers.yaml, skipped"); return
    absent = ad.triggers_not_ported(schema)
    observed, skipped = {}, []
    for case in spec:
        if case.get("trigger") in absent:
            skipped.append(case["name"]); continue
        observed[case["name"]] = ad.run_scenario(schema, case)
    if pin:
        dump_yaml(path, observed, "# S9: what each scenario's probe in triggers.yaml prints on MySQL after the scenario's\n"
                                  "# statements, normalised and sorted line by line (megasamples/probe.py).")
        res.note(f"trigger scenarios pinned for {len(observed)} scenarios"); return
    expected = load_yaml(path)
    if expected is None:
        res.fail(f"no triggers.expected.yaml for {cfg['database']}; run with --pin"); return
    checked = 0
    for name, want in sorted(expected.items()):
        if name not in observed:
            if name in skipped:
                continue
            res.fail(f"trigger scenario {name} not run"); continue
        got = observed[name]
        if got != want:
            res.fail(f"trigger scenario {name}:\n    expected {want!r}\n    got      {got!r}")
        checked += 1
    res.note(f"trigger scenarios OK for {checked} scenarios"
             + (f"; {len(skipped)} skipped, trigger not ported on {ad.name}: {', '.join(skipped)}" if skipped else ""))


STAGES = {"counts": stage_counts, "digests": stage_digests, "fks": stage_fks,
          "indexes": stage_indexes, "views": stage_views, "routines": stage_routines, "triggers": stage_triggers,
          "explain": stage_explain, "smoke": stage_smoke}


def adapter_for(engine, dataset):
    if engine == "mysql":
        from megasamples.engines.mysql.adapter import MySQLAdapter
        return MySQLAdapter()
    if engine == "postgres":
        from megasamples.engines.postgres.adapter import PostgresAdapter
        return PostgresAdapter(dataset)
    if engine == "sqlite":
        from megasamples.engines.sqlite.adapter import SQLiteAdapter
        return SQLiteAdapter(dataset)
    raise SystemExit(f"no verification adapter for engine {engine!r}")


def verify(dataset, stages=None, engine="mysql", pin=False):
    """Run the stages; returns the number of failures. Prints one line per note and failure."""
    d = dataset_dir(dataset)
    cfg = load_yaml(os.path.join(d, "dataset.yaml"))
    if not cfg:
        sys.exit(f"no datasets/{dataset}/dataset.yaml")
    if pin and engine != "mysql":
        sys.exit("--pin is for the hub only: expectations come from MySQL, never from a port")
    ad = adapter_for(engine, dataset)
    schema = cfg["database"]
    res = Result()
    for name in (stages or list(STAGES)):
        if name not in STAGES:
            sys.exit(f"unknown stage {name}; choose from {list(STAGES)}")
        if not ad.supports(name):
            res.note(f"{name}: not run on {ad.name} (MySQL-dialect queries)")
            continue
        STAGES[name](ad, cfg, schema, d, pin, res)
    for n in res.notes:
        print(f"  . {n}")
    for f in res.failures:
        print(f"  x {f}")
    print(f"{dataset} on {ad.name}: {len(res.failures)} failure(s)")
    return len(res.failures)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dataset")
    ap.add_argument("stages", nargs="*", default=[])
    ap.add_argument("--engine", default="mysql")
    ap.add_argument("--pin", action="store_true")
    a = ap.parse_args(argv)
    return 1 if verify(a.dataset, a.stages, a.engine, a.pin) else 0


if __name__ == "__main__":
    sys.exit(main())
