#!/usr/bin/env python3
"""Load TPC-C through sysbench-tpcc, in the loader image.

  python3 -m megasamples tpcc-load [--warehouses 1] [--threads 1]

This dataset is the one exception to the project's "identical row counts and checksums" rule, and
the exception is measured rather than assumed: two loads with the same `--rand-seed` and the same
thread count produce **different data in eight of the nine tables**. Only `new_orders` matches, and
that one is derived structurally. So this script asserts the specification's W=1 cardinalities,
which are stable, and does not pin content digests, which are not.

`order_line` is excluded from even the count assertion: TPC-C specifies 5 to 15 lines per order at
random, so its cardinality is a range rather than a number.
"""
import argparse, os, subprocess, sys

from megasamples.paths import ROOT
from megasamples.engines.mysql import server as db  # noqa: E402

IMAGE = os.environ.get("LOADER_IMAGE", "sql-megasamples-loader:dev")
# per warehouse, from the specification; order_line is deliberately absent
CARDINALITY = {"warehouse": 1, "district": 10, "customer": 30000, "history": 30000,
               "orders": 30000, "new_orders": 9000}
FIXED = {"item": 100000, "stock": 100000}          # not scaled by warehouse count


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--warehouses", type=int, default=1)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args(argv)

    db.start()
    db.sql("DROP DATABASE IF EXISTS `tpcc`; CREATE DATABASE `tpcc`")
    # Connector/C 3.4 verifies remote TLS peers by default. The throwaway build
    # server has a generated local certificate. Share only its network namespace
    # and use its loopback, which Connector/C treats as local, without globally
    # disabling peer verification or exposing another published port.
    cmd = (f"cd /opt/sysbench-tpcc && ./tpcc.lua --mysql-host=127.0.0.1 --mysql-user=root "
           f"--mysql-password={db.PW} --mysql-db=tpcc --threads={a.threads} --tables=1 "
           f"--scale={a.warehouses} --use_fk=0 --db-driver=mysql --rand-seed={a.seed} prepare")
    print(f"  . loading {a.warehouses} warehouse(s) with sysbench-tpcc in {IMAGE}")
    p = subprocess.run(["docker", "run", "--rm",
                        "--network", f"container:{db.NAME}",
                        "--label", "megasamples.transient=true",
                        "--label", "megasamples.role=loader", IMAGE, "sh", "-c", cmd],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"sysbench-tpcc failed:\n{(p.stderr or p.stdout)[-500:]}\n"
                 f"Build the loader image first: make loader-image")

    problems = []
    for table, per in CARDINALITY.items():
        got = int(db.rows(f"SELECT COUNT(*) FROM `tpcc`.`{table}1`")[0][0])
        want = per * a.warehouses
        print(f"  . {table + '1':<14}{got:>10,}" + ("" if got == want else f"   expected {want:,}"))
        if got != want:
            problems.append(f"{table}: {got} rows, the specification says {want}")
    for table, want in FIXED.items():
        got = int(db.rows(f"SELECT COUNT(*) FROM `tpcc`.`{table}1`")[0][0])
        print(f"  . {table + '1':<14}{got:>10,}" + ("" if got == want else f"   expected {want:,}"))
        if got != want:
            problems.append(f"{table}: {got} rows, the specification says {want}")
    lines = int(db.rows("SELECT COUNT(*) FROM `tpcc`.`order_line1`")[0][0])
    orders = CARDINALITY["orders"] * a.warehouses
    print(f"  . {'order_line1':<14}{lines:>10,}   5-15 per order, so between "
          f"{orders * 5:,} and {orders * 15:,}")
    if not orders * 5 <= lines <= orders * 15:
        problems.append(f"order_line: {lines} rows, outside 5-15 per order")
    mb = db.rows("SELECT ROUND(SUM(data_length+index_length)/1048576,1) FROM "
                 "information_schema.tables WHERE table_schema='tpcc'")[0][0]
    print(f"  . tpcc is {mb} MB in InnoDB")
    print("  ! no content digests are pinned for this dataset: two loads with the same seed differ "
          "in eight of nine tables (knowledge/datasets/tpc-c.md)")
    if problems:
        sys.exit("cardinalities do not match the specification:\n  " + "\n  ".join(problems))


if __name__ == "__main__":
    main()
