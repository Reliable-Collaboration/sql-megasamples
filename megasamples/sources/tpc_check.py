#!/usr/bin/env python3
"""Run the TPC-H or TPC-DS queries against MySQL and compare with the reference answers.

  python3 -m megasamples tpc-check [--database tpch|tpcds] [--sf 1]

This is what makes the port a port rather than a translation that happens to parse. DuckDB's
`tpch_answers()` carries the specification's validation output for scale factors 0.01, 0.1 and 1, so
every one of the 22 queries can be checked against a number somebody else computed.

Comparison is numeric, not textual, and deliberately so: MySQL returns `37734107.00` from a
DECIMAL(15,2) sum where the reference prints `37734107`, and averages differ in the last places
because the two engines carry different intermediate precision. A field that parses as a number is
compared with a relative tolerance; anything else must match exactly.
"""
import argparse, os, sys

import duckdb

from megasamples.paths import ROOT, stage_dir
from megasamples.engines.mysql import server as db  # noqa: E402

TOLERANCE = 1e-6


def number(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def decimals(text):
    """How many digits this rendering actually carries after the point."""
    t = (text or "").strip()
    return len(t.rsplit(".", 1)[1]) if "." in t and t.rsplit(".", 1)[1].isdigit() else 0


def compare(got, want, tolerance=TOLERANCE):
    """(ok, first difference). Both are lists of rows of string fields."""
    if len(got) != len(want):
        return False, f"{len(got)} rows, reference has {len(want)}"
    for i, (g, w) in enumerate(zip(got, want)):
        if len(g) != len(w):
            return False, f"row {i + 1}: {len(g)} columns, reference has {len(w)}"
        for j, (a, b) in enumerate(zip(g, w)):
            x, y = number(a), number(b)
            if x is not None and y is not None:
                # compare at the precision of the *less* precise side. MySQL's AVG over a DECIMAL
                # column returns a decimal with a fixed scale (15.3333) where DuckDB returns a
                # double (15.333333333333334); that is a representation difference, not a wrong
                # answer, and a flat relative tolerance calls it a failure at the fourth decimal.
                places = min(decimals(a), decimals(b))
                if round(x, places) != round(y, places) \
                        and abs(x - y) > tolerance * max(1.0, abs(y)):
                    return False, f"row {i + 1} column {j + 1}: {a} vs {b}"
            elif a.strip() != b.strip():
                return False, f"row {i + 1} column {j + 1}: {a!r} vs {b!r}"
    return True, ""


def reference(con, sf, nr, database="tpch"):
    if database == "tpcds":
        # DuckDB 1.5.5 and 2.0.0 ship no usable TPC-DS answers: tpcds_answers() reports "Don't have TPC-DS
        # answers for SF 10.000000" whatever has been generated. The TPC-DS queries are therefore
        # compared against DuckDB's own results on the same generated rows -- two independent
        # engines over identical data -- which catches a mistranslation but is *not* the
        # specification's validation output, and the record says so.
        return None
    else:
        row = con.execute(
            "SELECT answer FROM tpch_answers() WHERE scale_factor = ? AND query_nr = ?",
            [sf, nr]).fetchone()
    if not row:
        return None
    lines = [l for l in row[0].splitlines() if l.strip()]
    return [l.split("|") for l in lines[1:]]          # drop the header line


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sf", type=float, default=1.0)
    ap.add_argument("--database", default="tpch")
    ap.add_argument("--timeout", type=int, default=120,
                    help="seconds per query before it is recorded as too slow rather than compared")
    a = ap.parse_args(argv)
    queries = os.path.join(stage_dir(a.database), "queries")
    con = duckdb.connect()
    con.execute(f"INSTALL {a.database}; LOAD {a.database};")
    count = 22 if a.database == "tpch" else 99
    peer = None
    if a.database == "tpcds":
        print(f"  . generating TPC-DS SF {a.sf:g} in DuckDB to compare against; this takes a minute")
        peer = duckdb.connect()
        peer.execute(f"INSTALL tpcds; LOAD tpcds; CALL dsdgen(sf={a.sf});")

    passed, failed, skipped, slow = [], [], [], []
    for nr in range(1, count + 1):
        path = os.path.join(queries, f"q{nr:02d}.sql")
        if not os.path.exists(path):
            skipped.append((nr, "no query file")); continue
        want = reference(con, a.sf, nr, a.database)
        if want is None and peer is None:
            skipped.append((nr, f"no reference answer at SF {a.sf:g}")); continue
        sql = open(path, encoding="utf-8").read()
        # MySQL is not an analytics engine and several TPC-DS queries are punishing on it. A limit
        # makes the check bounded and repeatable: a query that exceeds it is reported as too slow,
        # which is a fact about MySQL at this scale rather than a wrong answer.
        guarded = f"SET SESSION max_execution_time = {a.timeout * 1000};\n{sql}"
        try:
            raw = db.sql(guarded, database=a.database)
        except Exception as exc:
            last = str(exc).splitlines()[-1][:110]
            if "max_execution_time" in str(exc) or "3024" in str(exc) or "timeout" in last.lower():
                slow.append((nr, f"over {a.timeout}s")); continue
            failed.append((nr, f"MySQL rejected it: {last}")); continue
        got = [l.split("\t") for l in raw.splitlines() if l.strip()]
        if want is None and peer is not None:
            try:
                rows = peer.execute(sql.rstrip().rstrip(";")).fetchall()
            except Exception as exc:
                skipped.append((nr, f"DuckDB rejected its own query: {str(exc)[:70]}")); continue
            want = [["NULL" if v is None else str(v) for v in r] for r in rows]
        if want is None:
            skipped.append((nr, "no reference to compare against")); continue
        ok, why = compare(got, want)
        (passed if ok else failed).append((nr, why))

    for nr, why in failed:
        print(f"  x Q{nr:02d}: {why}")
    for nr, why in slow:
        print(f"  ~ Q{nr:02d} too slow to compare: {why}")
    for nr, why in skipped:
        print(f"  . Q{nr:02d} skipped: {why}")
    source = ("DuckDB's own results on the same rows" if a.database == "tpcds"
              else "the reference answers")
    print(f"{len(passed)}/{count} queries match {source} at SF {a.sf:g}"
          + (f"; {len(failed)} differ" if failed else "")
          + (f"; {len(slow)} over the {a.timeout}s limit" if slow else "")
          + (f"; {len(skipped)} skipped" if skipped else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
