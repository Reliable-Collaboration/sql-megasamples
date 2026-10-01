#!/usr/bin/env python3
"""Dump one loaded database from the build server into the format the image builder consumes.

  python3 -m megasamples dump sakila

Uses MySQL Shell's `util.dumpSchemas`, whose output `util.loadDump` can restore with
`deferTableIndexes`, so the image builder creates secondary indexes after the data is in place
(ARCHITECTURE.md section 4). The dump directory is content-addressed by a manifest the image build reads.
"""
import argparse, hashlib, json, os, shutil, sys, time
import yaml
from megasamples import container_engine
from megasamples.engines.mysql import server as db  # noqa: E402

from megasamples.paths import ROOT, engine_build_dir

DUMPS = os.path.join(engine_build_dir("mysql"), "dumps")   # the server mounts build/ at /build


def dump(dataset):
    cfg = yaml.safe_load(open(os.path.join(ROOT, "datasets", dataset, "dataset.yaml"), encoding="utf-8"))
    schema = cfg["database"]
    # keyed by database: an `append: true` dataset adds tables to another dataset's database, and
    # the dump is of the database as it stands, whichever dataset asked for it
    host_dir = os.path.join(DUMPS, schema)
    if os.path.exists(host_dir):
        shutil.rmtree(host_dir)
    os.makedirs(os.path.dirname(host_dir), exist_ok=True)
    started = time.time()
    # mysqlsh needs the directory to not exist; it creates it itself
    script = (f"util.dump_schemas(['{schema}'], '/build/mysql/dumps/{schema}', "
              f"{{'showProgress': False, 'compression': 'zstd', 'threads': 4}})")
    # --no-defaults: mysqlsh reads my.cnf's [client] section and rejects default-character-set,
    # which the MySQL Shell record already flagged as a difference from the mysql client.
    # Run the shell as the host user (over TCP, since the socket is only reachable by uid 999; on a
    # rootless engine that user is container root, container_engine.host_user says why) so
    # the dump files land owned by the caller instead of by the container's mysql user.
    out = db.run(["docker", "exec", "-u", container_engine.host_user(),
                  "-e", "HOME=/build",          # mysqlsh needs a writable home for its state dir
                  db.NAME,
                  "mysqlsh", "--no-defaults", f"root:{db.PW}@127.0.0.1:3306", "--py", "-e", script])
    if out.returncode != 0:
        sys.exit(f"dump failed:\n{out.stdout}\n{out.stderr}")
    files = sorted(f for f in os.listdir(host_dir))
    digest = hashlib.sha256()
    total = 0
    for name in files:
        path = os.path.join(host_dir, name)
        digest.update(name.encode())
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        total += os.path.getsize(path)
    manifest = {"dataset": dataset, "database": schema, "files": len(files),
                "bytes": total, "sha256": digest.hexdigest(),
                "seconds": round(time.time() - started, 2)}
    with open(os.path.join(DUMPS, f"{schema}.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print(f"  . dumped {schema}: {len(files)} files, {total:,} bytes, sha256 {digest.hexdigest()[:12]}")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("datasets", nargs="+")
    a = ap.parse_args(argv)
    db.start()
    for name in a.datasets:
        dump(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())


def complete(schema, tables=()):
    """True when the database's dump finished and holds every named table: a dump taken before an
    `append: true` dataset was loaded lacks that dataset's tables and must be taken again."""
    host_dir = os.path.join(DUMPS, schema)
    if not os.path.exists(os.path.join(host_dir, "@.done.json")):
        return False
    return all(os.path.exists(os.path.join(host_dir, f"{schema}@{t}.json")) for t in tables)
