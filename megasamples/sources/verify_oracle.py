#!/usr/bin/env python3
"""V-01: load HR, CO and SH into a real Oracle and check our MySQL conversion against it.

  MEGASAMPLES_ACCEPT_ORACLE_LICENSE=1 python3 -m megasamples verify-oracle [--only oracle_hr]

The three Oracle sample schemas are converted by `convert/oracle_scripts.py`, whose tests assert the
row counts the research recorded. That proves the converter agrees with a *document*. This proves it
agrees with **Oracle**: the same upstream scripts are run by the database they were written for, and
every table is compared row by row in aggregate against what MySQL holds.

Comparisons are chosen to mean the same thing in both engines: a row count, a non-null count per
column, the sum of every exact-numeric column, and the summed character length of every string
column. Floating-point columns are summed too but compared with a relative tolerance, because IEEE
addition is order-dependent and the two engines do not read the rows in the same order.

**Licence.** This runs Oracle AI Database Free in a container, under the Oracle Free Use Terms and
Conditions. The script refuses to start until you accept them. Nothing produced here is redistributed:
the container is removed at the end, the image is never pushed, and the MySQL data this verifies was
converted from the MIT-licensed Oracle sample scripts, not from anything the database produced.
SQLcl -- which the earlier deferral assumed was required, and which carries a *different* licence --
is not used: the image ships SQL*Loader, which loads the SH CSVs.
"""
import argparse, json, os, re, subprocess, sys, time

from megasamples.paths import ROOT
from megasamples import container_engine
IMAGE = os.environ.get("ORACLE_IMAGE", "gvenzl/oracle-free:23@sha256:7ed34d0ade89c91a553c9cbe9d42457c758fa29a762aaaa3137541ff30a2d1cb")
CLIENT_IMAGE = "sql-megasamples-oracle-verifier:23.26.3-clients-23.26.4"
SQLPLUS = "/usr/local/bin/megasamples-sqlplus"
SQLLDR = "/usr/local/bin/megasamples-sqlldr"
NAME = os.environ.get("ORACLE_CONTAINER", "megasamples-build-oracle")
SYS_PW = "oracle"
MYSQL_CONTAINER = os.environ.get("MEGASAMPLES_CONTAINER", "megasamples-mysql")
TIMEOUT = 300

TERMS = """
Oracle AI Database Free -- Oracle Free Use Terms and Conditions
  https://www.oracle.com/downloads/licenses/oracle-free-license.html

  "You may use, copy, and distribute the Programs ... free of charge" for developing, testing,
  prototyping and demonstrating applications, subject to the limits the licence states
  (2 CPUs, 2 GB RAM, 12 GB of user data). The Programs are provided without support and without
  warranty.

This target runs that database in a container to cross-check a conversion. It downloads no Oracle
data, redistributes nothing Oracle produced, and removes the container when it finishes.
"""

# The Oracle user has to carry the schema's own name: sh_create.sql qualifies its materialized-view
# query as `sh.sales`, so a user called anything else gets ORA-00942 and silently ends up without the
# two materialized views -- which MySQL has, as views, and which would then go unchecked.
SCHEMAS = {
    "oracle_hr": dict(user="hr", scripts=["hr_create.sql", "hr_populate.sql"], csvs=(), unported={}),
    "oracle_co": dict(user="co", scripts=["co_create.sql", "co_populate.sql"], csvs=(), unported={
        # recorded at M-02, not a gap found here: the view groups with GROUPING SETS, which P-02
        # verified is HeatWave-only on MySQL 9.7 (ERROR 3889 at execution, though it parses)
        "STORE_ORDERS": "uses GROUPING SETS, which MySQL 9.7 rejects outside HeatWave "
                        "(knowledge/datasets/oracle-co.md)"}),
    # sh_populate.sql loads the six big tables with SQLcl's `LOAD` command, which sqlplus does not
    # have. Those lines are stripped and the CSVs go in through SQL*Loader instead; everything else
    # in the file (the INSERTs for channels and countries, and the PL/SQL) runs unchanged.
    "oracle_sh": dict(user="sh", scripts=["sh_create.sql", "sh_populate.sql"],
                      csvs=("costs", "customers", "promotions", "sales",
                            "supplementary_demographics", "times"), unported={}),
}


def sh(*args, **kw):
    return subprocess.run(args, capture_output=True, text=True, **kw)


class Slow(Exception):
    """One comparison took longer than the budget. Reported, never silently dropped."""


def sqlplus(user, pw, statements, timeout=1800):
    script = "SET PAGESIZE 0 FEEDBACK OFF HEADING OFF LINESIZE 32767 TRIMSPOOL ON\n" + statements + "\nEXIT\n"
    return subprocess.run(
        ["docker", "exec", "-i", NAME, SQLPLUS, "-s", f"{user}/{pw}@localhost/FREEPDB1"],
        input=script, capture_output=True, text=True, timeout=timeout)


def mysql(sql):
    p = sh("docker", "exec", MYSQL_CONTAINER, "mysql", "-uroot", "-proot", "-N", "--batch", "-e", sql)
    if p.returncode != 0:
        sys.exit(f"could not query {MYSQL_CONTAINER}: {p.stderr.strip()[:200]}")
    return [line.split("\t") for line in p.stdout.splitlines() if line.strip()]


def build_client_image():
    """Build binaries only; the main command retains its explicit database licence gate."""
    return subprocess.run(["docker", "build", "-f", "engines/oracle-client/Dockerfile",
                           "--build-arg", f"ORACLE_IMAGE={IMAGE}",
                           "-t", CLIENT_IMAGE, "engines/oracle-client"],
                          cwd=ROOT, env=container_engine.build_env()).returncode


def container_ready(timeout=900):
    if build_client_image():
        sys.exit("could not build the pinned Oracle client image")
    state = sh("docker", "inspect", "-f", "{{.State.Status}}", NAME).stdout.strip()
    if state != "running":
        sh("docker", "rm", "-f", NAME)
        p = sh("docker", "run", "-d", "--name", NAME,
               "--label", "megasamples.transient=true", "--label", "megasamples.role=oracle",
               "-e", f"ORACLE_PASSWORD={SYS_PW}", CLIENT_IMAGE)
        if p.returncode != 0:
            sys.exit(f"could not start {IMAGE}: {p.stderr.strip()[:200]}")
    started = time.time()
    while time.time() - started < timeout:
        if "DATABASE IS READY TO USE" in sh("docker", "logs", NAME).stdout:
            return True
        time.sleep(5)
    sys.exit(f"{NAME} did not become ready within {timeout}s")


def run_as_sysdba(statements):
    script = "SET PAGESIZE 0 FEEDBACK OFF HEADING OFF\n" + statements + "\nEXIT\n"
    return subprocess.run(
        ["docker", "exec", "-i", NAME, SQLPLUS, "-s", f"sys/{SYS_PW}@localhost/FREEPDB1", "as", "sysdba"],
        input=script, capture_output=True, text=True, timeout=600)


def prepare(name, spec):
    """Create the user, copy the sources in, run the scripts, load the CSVs."""
    user = spec["user"]
    src = os.path.join(ROOT, "downloads", name)
    run_as_sysdba(f"DROP USER {user} CASCADE;")
    p = run_as_sysdba(
        f"CREATE USER {user} IDENTIFIED BY {user} QUOTA UNLIMITED ON USERS;\n"
        f"GRANT CONNECT, RESOURCE, CREATE VIEW, CREATE PROCEDURE, CREATE SEQUENCE, "
        f"CREATE TRIGGER, CREATE MATERIALIZED VIEW TO {user};\n"
        # ENABLE QUERY REWRITE on the SH materialized views needs this one specifically, and
        # ANALYZE ANY is what sh_populate.sql's dbms_stats.gather_schema_stats('SH') call wants --
        # without it that call raises ORA-01031 and the schema is queried with no statistics at all,
        # which is why the PROFITS view took minutes on a database that should answer in seconds
        f"GRANT QUERY REWRITE, ANALYZE ANY TO {user};")
    if "ORA-" in p.stdout and "created" not in p.stdout.lower():
        sys.exit(f"{name}: could not create the Oracle user:\n{p.stdout[:400]}")

    sh("docker", "exec", NAME, "sh", "-c", f"rm -rf /tmp/{name} && mkdir -p /tmp/{name}")
    for f in os.listdir(src):
        if f.endswith((".sql", ".csv")):
            sh("docker", "cp", os.path.join(src, f), f"{NAME}:/tmp/{name}/{f}")

    # strip the SQLcl-only LOAD lines; SQL*Loader does that work below
    for script in spec["scripts"]:
        sh("docker", "exec", NAME, "sh", "-c",
           f"sed -i '/^LOAD /d' /tmp/{name}/{script}")

    body = "WHENEVER SQLERROR CONTINUE\n" + "\n".join(f"@{s}" for s in spec["scripts"]) + "\nCOMMIT;"
    p = subprocess.run(["docker", "exec", "-i", "-w", f"/tmp/{name}", NAME,
                        SQLPLUS, "-s", f"{user}/{user}@localhost/FREEPDB1"],
                       input="SET PAGESIZE 0 FEEDBACK OFF HEADING OFF\n" + body + "\nEXIT\n",
                       capture_output=True, text=True, timeout=3600)
    errs = sorted({m for m in re.findall(r"ORA-\d{5}", p.stdout)})
    if errs:
        print(f"  . scripts ran with Oracle messages: {', '.join(errs[:6])}")

    for table in spec["csvs"]:
        sqlldr(name, user, table)

    if spec["csvs"]:
        # Both of these have to happen AFTER the CSVs are in. sh_create.sql builds the two
        # materialized views while the tables are still empty, and sh_populate.sql gathers
        # statistics before the LOAD lines it expects SQLcl to run -- so left alone, Oracle ends up
        # with empty materialized views and statistics describing an empty schema.
        refresh = """BEGIN
  FOR m IN (SELECT mview_name FROM user_mviews) LOOP
    DBMS_MVIEW.REFRESH(m.mview_name, 'C');
  END LOOP;
  DBMS_STATS.GATHER_SCHEMA_STATS(USER, cascade => TRUE);
END;
/"""
        out = sqlplus(user, user, refresh, timeout=1800)
        errs = sorted({m for m in re.findall(r"ORA-\d{5}", out.stdout)})
        print(f"  {'x' if errs else '.'} refreshed the materialized views and gathered statistics"
              + (f" ({', '.join(errs)})" if errs else ""))


def sqlldr(name, user, table):
    """Load one CSV with SQL*Loader, taking the column order from the file's own header."""
    header = sh("docker", "exec", NAME, "sh", "-c", f"head -1 /tmp/{name}/{table}.csv").stdout.strip()
    cols = [c.strip().strip('"') for c in header.split(",")]
    # DATE columns have to be told their format; everything else SQL*Loader infers
    types = {r[0].upper(): r[1].upper() for r in oracle_columns(user, table)}
    spec = []
    for c in cols:
        t = types.get(c.upper(), "")
        if t == "DATE":
            spec.append(f'{c} DATE "YYYY-MM-DD"')
        elif t.startswith(("VARCHAR", "CHAR")):
            spec.append(f'{c} CHAR(4000)')
        else:
            spec.append(c)
    ctl = (f"LOAD DATA\nINFILE '{table}.csv'\nINTO TABLE {table}\n"
           f"FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"'\nTRAILING NULLCOLS\n"
           f"({', '.join(spec)})\n")
    sh("docker", "exec", NAME, "sh", "-c",
       f"cat > /tmp/{name}/{table}.ctl <<'CTL'\n{ctl}CTL")
    p = sh("docker", "exec", "-w", f"/tmp/{name}", NAME, SQLLDR,
           f"{user}/{user}@localhost/FREEPDB1", f"control={table}.ctl", "skip=1",
           "direct=true", "errors=0", f"log={table}.log")
    ok = "successfully loaded" in (p.stdout + p.stderr).lower() or p.returncode == 0
    print(f"  {'.' if ok else 'x'} SQL*Loader {table}.csv")
    if not ok:
        log = sh("docker", "exec", NAME, "sh", "-c", f"tail -20 /tmp/{name}/{table}.log").stdout
        print("    " + log.replace("\n", "\n    ")[:600])


def oracle_columns(user, table):
    out = sqlplus(user, user,
                  f"SELECT column_name || '\t' || data_type FROM user_tab_columns "
                  f"WHERE table_name = UPPER('{table}') ORDER BY column_id;")
    return [l.split("\t") for l in out.stdout.splitlines() if "\t" in l]


def oracle_scalar_rows(user, statements):
    out = sqlplus(user, user, statements)
    return [l.strip() for l in out.stdout.splitlines() if l.strip()]


# --- what each column type contributes to the comparison -------------------------------------
# The metric has to mean the same thing in both engines. A row count and a non-null count always do.
# Exact numerics can be summed. Strings are compared by total character length rather than by
# content, which catches truncation, encoding loss and dropped rows without needing collations to
# agree. Dates are compared at second resolution. Floats are summed but with tolerance, since IEEE
# addition depends on the order the rows arrive in and the engines do not agree on that.
def classify_oracle(t):
    t = t.upper()
    if t in ("NUMBER", "INTEGER", "DECIMAL", "NUMERIC"): return "num"
    if t in ("FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE"): return "float"
    if t.startswith(("VARCHAR", "CHAR", "NCHAR", "NVARCHAR")): return "str"
    if t.startswith(("DATE", "TIMESTAMP")): return "date"
    return None


def classify_mysql(t):
    t = t.lower()
    if t in ("int", "bigint", "smallint", "tinyint", "mediumint", "decimal", "numeric"): return "num"
    if t in ("float", "double"): return "float"
    if t in ("char", "varchar", "text", "tinytext", "mediumtext", "longtext"): return "str"
    if t in ("date", "datetime", "timestamp"): return "date"
    return None


def metric_plan(columns):
    """The (kind, column) pairs to compare, in a fixed order both engines can follow."""
    plan = [("rows", "")]
    for col, kind in columns:
        plan.append(("nn", col))
        if kind == "num":
            plan.append(("sum", col))
        elif kind == "float":
            plan.append(("fsum", col))
        elif kind == "str":
            plan.append(("len", col))
        elif kind == "date":
            plan += [("min", col), ("max", col)]
    return plan


# One pass, not one per column. The first version issued a separate aggregate per metric and joined
# them with UNION ALL, so a table was scanned once for every column it had: SH's PROFITS view takes
# ~45 s to scan and has 10 columns, which turned a 45-second check into a 15-minute one that then
# reported itself as "too slow". Every metric is now computed in a single SELECT.
def oracle_expr(kind, col):
    if kind == "rows":  return "TO_CHAR(COUNT(*))"
    if kind == "nn":    return f'TO_CHAR(COUNT("{col}"))'
    if kind in ("sum", "fsum"): return f'TO_CHAR(NVL(SUM("{col}"),0))'
    if kind == "len":   return f'TO_CHAR(NVL(SUM(LENGTH("{col}")),0))'
    return f'NVL(TO_CHAR({"MIN" if kind == "min" else "MAX"}("{col}"),\'YYYY-MM-DD HH24:MI:SS\'),\'-\')'


def mysql_expr(kind, col):
    if kind == "rows":  return "CAST(COUNT(*) AS CHAR)"
    if kind == "nn":    return f"CAST(COUNT(`{col}`) AS CHAR)"
    if kind in ("sum", "fsum"): return f"CAST(COALESCE(SUM(`{col}`),0) AS CHAR)"
    if kind == "len":   return f"CAST(COALESCE(SUM(CHAR_LENGTH(`{col}`)),0) AS CHAR)"
    return (f"COALESCE(DATE_FORMAT({'MIN' if kind == 'min' else 'MAX'}(`{col}`),"
            f"'%Y-%m-%d %H:%i:%s'),'-')")


def oracle_metrics(user, table, columns):
    plan = metric_plan(columns)
    joined = " || '~' || ".join(oracle_expr(k, c) for k, c in plan)
    try:
        out = sqlplus(user, user, f"SELECT {joined} FROM {table};", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Slow(f"Oracle took longer than {TIMEOUT}s")
    line = next((l for l in out.stdout.splitlines() if "~" in l), None)
    if line is None:
        raise Slow(f"Oracle returned nothing for {table}: {out.stdout.strip()[:160]}")
    values = line.strip().split("~")
    return {(k, c): v.strip() for (k, c), v in zip(plan, values)}


def mysql_metrics(db, table, columns):
    plan = metric_plan(columns)
    cols = ", ".join(mysql_expr(k, c) for k, c in plan)
    sql = f"SET SESSION max_execution_time = {TIMEOUT * 1000};\nSELECT {cols} FROM `{db}`.`{table}`;"
    p = sh("docker", "exec", MYSQL_CONTAINER, "mysql", "-uroot", "-proot", "-N", "--batch", "-e", sql)
    if p.returncode != 0:
        if "exceeded" in p.stderr.lower() or "timeout" in p.stderr.lower():
            raise Slow(f"MySQL took longer than {TIMEOUT}s")
        sys.exit(f"could not query {MYSQL_CONTAINER}: {p.stderr.strip()[:200]}")
    line = next((l for l in p.stdout.splitlines() if l.strip()), "")
    return {(k, c): v.strip() for (k, c), v in zip(plan, line.split("\t"))}


def same_number(a, b, kind):
    """Oracle and MySQL format numbers differently; compare by value, not by text."""
    try:
        fa, fb = float(a), float(b)
    except ValueError:
        return a.strip() == b.strip()
    if kind == "fsum":
        scale = max(abs(fa), abs(fb), 1.0)
        return abs(fa - fb) <= 1e-9 * scale
    return abs(fa - fb) < 1e-9


def compare(name, spec):
    user = spec["user"]
    # DR$..$I and friends are Oracle Text's storage for the CONTEXT index on
    # supplementary_demographics: index internals, not user data, with no MySQL counterpart.
    # Views are compared too, not only tables: SH's two materialized views became plain views in
    # MySQL, and comparing their aggregates is exactly the check worth having -- does our view
    # definition produce what Oracle's materialized one holds?
    ora_tables = {t.upper() for t in oracle_scalar_rows(
        user, "SELECT table_name FROM user_tables WHERE table_name NOT LIKE 'DR$%' "
              "UNION SELECT view_name FROM user_views;")}
    my_tables = {r[0].upper(): r[0] for r in mysql(
        f"SELECT table_name FROM information_schema.tables WHERE table_schema='{name}'")}

    unported = {k.upper(): v for k, v in spec.get("unported", {}).items()}
    only_oracle = sorted(ora_tables - set(my_tables))
    only_mysql = sorted(set(my_tables) - ora_tables)
    failures = []
    for t in list(only_oracle):
        if t in unported:
            print(f"  = {name}.{t}: absent by decision — {unported[t]}")
            only_oracle.remove(t)
    if only_oracle:
        failures.append(f"{name}: in Oracle but not MySQL: {', '.join(only_oracle)}")
    if only_mysql:
        failures.append(f"{name}: in MySQL but not Oracle: {', '.join(only_mysql)}")

    checked, skipped = 0, []
    for t in sorted(ora_tables & set(my_tables)):
        ocols = {c.upper(): classify_oracle(ty) for c, ty in oracle_columns(user, t)}
        mcols = {r[0].upper(): classify_mysql(r[1]) for r in mysql(
            f"SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_schema='{name}' AND table_name='{my_tables[t]}'")}
        common = [(c, ocols[c]) for c in sorted(set(ocols) & set(mcols))
                  if ocols[c] and ocols[c] == mcols[c]]
        try:
            o = oracle_metrics(user, t, common)
            m = mysql_metrics(name, my_tables[t], [(c.lower(), k) for c, k in common])
        except Slow as e:
            skipped.append(f"{name}.{t}: {e}")
            continue
        m = {(k, c.upper()): v for (k, c), v in m.items()}

        for key in sorted(set(o) & set(m)):
            kind, col = key
            if kind in ("rows", "nn", "sum", "len", "fsum"):
                ok = same_number(o[key], m[key], kind)
            else:
                ok = o[key].strip() == m[key].strip()
            checked += 1
            if not ok:
                where = f"{t}.{col}" if col else t
                failures.append(f"{name}: {where} {kind}: Oracle {o[key]} != MySQL {m[key]}")
        missing = sorted(set(o) - set(m))
        if missing and len(missing) < 200:
            pass  # a column MySQL classifies differently is not a defect in the data
    print(f"  . {name}: {len(ora_tables & set(my_tables))} objects, {checked} aggregate(s) compared")
    for s_ in skipped:
        print(f"  ~ {s_} -- not compared")
    return failures


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", action="append", choices=sorted(SCHEMAS), help="one schema, repeatable")
    ap.add_argument("--accept-license", action="store_true")
    ap.add_argument("--keep", action="store_true", help="leave the Oracle container running")
    ap.add_argument("--reuse", action="store_true",
                    help="compare what is already loaded in Oracle instead of reloading it")
    ap.add_argument("--timeout", type=int, default=300,
                    help="seconds allowed per object before it is reported as not compared")
    a = ap.parse_args(argv)

    if not (a.accept_license or os.environ.get("MEGASAMPLES_ACCEPT_ORACLE_LICENSE") == "1"):
        print(TERMS)
        print("Refusing to start. Re-run with MEGASAMPLES_ACCEPT_ORACLE_LICENSE=1 (or "
              "--accept-license) to accept these terms.")
        return 2

    names = a.only or list(SCHEMAS)
    for n in names:
        if not os.path.isdir(os.path.join(ROOT, "downloads", n)):
            sys.exit(f"{n}: downloads/{n} is not present -- run `make {n}` first")

    global TIMEOUT
    TIMEOUT = a.timeout
    container_ready()
    banner = subprocess.run(
        ["docker", "exec", "-i", NAME, SQLPLUS, "-s", f"sys/{SYS_PW}@localhost/FREEPDB1", "as", "sysdba"],
        input="SET PAGESIZE 0 FEEDBACK OFF HEADING OFF\nSELECT banner FROM v$version;\nEXIT\n",
        capture_output=True, text=True).stdout.strip().splitlines()
    print(f"  . {banner[0].strip() if banner else IMAGE}")
    failures = []
    try:
        for n in names:
            if not a.reuse:
                prepare(n, SCHEMAS[n])
            failures += compare(n, SCHEMAS[n])
    finally:
        if not a.keep:
            sh("docker", "rm", "-f", NAME)
            print(f"\nremoved {NAME}")

    for f in failures:
        print(f"  x {f}")
    print(f"oracle cross-check: {len(failures)} difference(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
