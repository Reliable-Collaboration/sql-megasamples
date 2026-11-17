#!/usr/bin/env python3
"""Generate the provenance registry SQL: the only writer of the `megasamples.datasets` table.

  python3 -m megasamples registry sakila chinook northwind pubs [--dialect mysql|postgres|sqlite] [--out FILE]

Rows are built from the places that already hold the facts -- datasets/<name>/dataset.yaml,
manifest.yaml plus downloads/<id>.meta.json for the source artifacts, build/mysql/dumps/<database>.json
for the built artifact, tests/expected_counts.yaml for the row counts, and for a port
build/<engine>/<database>/dropped.txt for what that engine does not carry -- so provenance is queryable
from SQL without anyone maintaining a second copy by hand. One row per database: an `append: true`
dataset's artifacts, licences and counts join the row of the database it extends.
"""
import argparse, json, os, sys
import yaml

from megasamples.paths import ROOT, engine_build_dir


def esc(value, dialect="mysql"):
    text = str(value).replace("'", "''")
    if dialect == "mysql":
        text = str(value).replace("\\", "\\\\").replace("'", "''")
    return "'" + text + "'"


def load_dataset(dataset):
    d = os.path.join(ROOT, "datasets", dataset)
    cfg = yaml.safe_load(open(os.path.join(d, "dataset.yaml"), encoding="utf-8"))
    counts_path = os.path.join(d, "tests", "expected_counts.yaml")
    counts = yaml.safe_load(open(counts_path, encoding="utf-8")) if os.path.exists(counts_path) else {}
    return cfg, counts


def image_counts(dataset):
    """Exact shipped counts: immutable pins, or the live snapshot verified on this build's hub."""
    from megasamples.paths import BUILD
    cfg, counts = load_dataset(dataset)
    if not cfg.get("live"):
        return counts
    path = os.path.join(BUILD, "live", f"{dataset}.observed.yaml")
    if not os.path.exists(path):
        raise ValueError(f"{dataset}: no verified hub counts at {path}; build and verify MySQL first")
    with open(path, encoding="utf-8") as fh:
        observed = (yaml.safe_load(fh) or {}).get("counts") or {}
    for table, floor in counts.items():
        value = observed.get(table)
        if not isinstance(value, int) or value < floor:
            raise ValueError(f"{dataset}: missing or below-floor hub count for {table}")
    return {table: observed[table] for table in counts}


def row(datasets, build_id, dialect="mysql", engine="mysql"):
    """One row for one database. `datasets` are the datasets that live in it: the base first, then
    any `append: true` dataset, whose artifacts, licences and row counts join the base's."""
    cfgs = [(load_dataset(name)[0], image_counts(name)) for name in datasets]
    base = next((c for c, _ in cfgs if not c.get("append")), cfgs[0][0])
    schema = base["database"]
    licenses, counts, artifacts = [], {}, []
    for cfg, own_counts in cfgs:
        for lic in cfg.get("licenses") or []:
            if lic not in licenses:
                licenses.append(lic)
        counts.update(own_counts)
        for art_id in cfg.get("artifacts") or []:
            meta_path = os.path.join(ROOT, "downloads", art_id + ".meta.json")
            entry = {"id": art_id}
            if os.path.exists(meta_path):
                meta = json.load(open(meta_path, encoding="utf-8"))
                entry.update({"sha256": meta.get("sha256"), "bytes": meta.get("size_bytes"),
                              "source": meta.get("source")})
            artifacts.append(entry)
    dump_path = os.path.join(engine_build_dir("mysql"), "dumps", f"{schema}.json")
    if os.path.exists(dump_path):
        dump = json.load(open(dump_path, encoding="utf-8"))
        artifacts.append({"id": f"dump/{schema}", "sha256": dump["sha256"], "bytes": dump["bytes"]})

    values = [esc(schema, dialect), esc(base.get("tier", "core"), dialect), esc(base["record"], dialect),
              esc(base.get("upstream_version", "") or "", dialect),
              esc(json.dumps(licenses), dialect), esc(json.dumps(artifacts), dialect),
              esc(json.dumps(counts), dialect), esc(build_id, dialect)]
    if engine != "mysql":
        dropped_path = os.path.join(engine_build_dir(engine), schema, "dropped.txt")
        dropped = [l.rstrip("\n") for l in open(dropped_path, encoding="utf-8")] if os.path.exists(dropped_path) else []
        values += [esc(engine, dialect), esc(json.dumps([l for l in dropped if l]), dialect)]
    return "(" + ", ".join(values) + ")"


COLUMNS = "(name, tier, record, upstream_version, licenses, artifacts, row_counts, build_id"


def by_database(datasets):
    """{database: [datasets]} in database order: the registry has one row per database."""
    groups = {}
    for name in sorted(datasets):
        groups.setdefault(load_dataset(name)[0]["database"], []).append(name)
    return dict(sorted(groups.items()))


def render(datasets, build_id, dialect="mysql", engine="mysql"):
    rows = [row(group, build_id, dialect, engine) for group in by_database(datasets).values()]
    table = "megasamples.datasets" if dialect == "mysql" else "datasets"
    cols = COLUMNS + (", engine, not_ported)" if engine != "mysql" else ")")
    return ("-- Generated by megasamples registry. Do not edit; it is rewritten on every image build.\n"
            f"DELETE FROM {table};\n"
            f"INSERT INTO {table}\n  {cols}\nVALUES\n  " + ",\n  ".join(rows) + ";\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("datasets", nargs="+")
    ap.add_argument("--build-id", default=os.environ.get("MEGASAMPLES_BUILD_ID", "dev"))
    ap.add_argument("--dialect", default="mysql", choices=["mysql", "postgres", "sqlite"])
    ap.add_argument("--engine", default=None, help="the engine the rows describe (default: the dialect)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    engine = a.engine or a.dialect
    out = a.out or os.path.join(engine_build_dir(engine), "registry.sql")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(render(a.datasets, a.build_id, a.dialect, engine))
    print(f"  . registry: {len(a.datasets)} dataset(s) -> {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
