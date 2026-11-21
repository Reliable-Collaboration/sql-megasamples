"""Disk-pressure gates. The server's data filesystem must be a dedicated scratch mount."""

import contextlib
import re
import uuid

from mysql import table, value as mysql_value
from native import Unavailable, checked, require, same
from postgres import CHECKSUM, COPY, TEMPLATE, fixture, value as pg_value


@contextlib.contextmanager
def pressure(target, key, path, reserve_kib):
    container = target.container(key)
    name = ".dl077-fill-" + uuid.uuid4().hex
    result = target.podman(
        "exec", container, "sh", "-ec", """
        data=$1
        reserve=$2
        fill=$3
        [ "$data" != / ] && [ -d "$data" ] || exit 89
        test "$(stat -c %d "$data")" != "$(stat -c %d /)" || exit 89
        set -- $(df -Pk "$data" | awk 'NR == 2 { print $2, $4 }')
        [ "$#" = 2 ] && [ "$1" -le 2097152 ] || exit 89
        blocks=$(($2 - reserve))
        [ "$blocks" -gt 0 ] || exit 89
        set -C
        : > "$data/$fill"
        if command -v fallocate >/dev/null 2>&1; then
            fallocate -l "$((blocks * 1024))" "$data/$fill"
        else
            dd if=/dev/zero of="$data/$fill" bs=1024 count="$blocks" status=none
        fi
        df -Pk "$data"
        """, "dl077", path, str(reserve_kib), name,
    )
    if result.returncode == 89:
        raise Unavailable("engine data is not on a separate filesystem of at most 2 GiB")
    try:
        checked(result)
        yield
    finally:
        cleanup = target.podman("exec", container, "rm", "-f", f"{path}/{name}")
        require(cleanup.returncode == 0, "the server container was unavailable during filler cleanup")


def pg_fingerprint(target, key="postgres", exclude=()):
    catalog = pg_value(target, """
        SELECT datname, oid, datdba::regrole, datistemplate, datallowconn, datacl
        FROM pg_database ORDER BY datname
    """, key=key)
    cases = tuple(row.split("|")[0] for row in catalog.splitlines()
                  if row.split("|")[0] not in exclude)
    data = {}
    for row in catalog.splitlines():
        db, _, _, _, connected, _ = row.split("|", 5)
        if connected != "t" or db not in cases:
            continue
        data[db] = pg_value(target, r"""
            SELECT format(
                'SELECT %L, count(*), bit_xor(hashtextextended(t::text,0)),sum(hashtextextended(t::text,1)::numeric) FROM %I.%I t',
                nspname||'.'||relname, nspname, relname
            ) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE relkind='r' AND nspname NOT IN ('pg_catalog','information_schema')
                AND nspname NOT LIKE 'pg_%' ORDER BY nspname,relname \gexec
        """, db, key=key)
    return catalog, data


def mysql_fingerprint(target, key="mysql", exclude=()):
    schemas = mysql_value(target, """
        SELECT SCHEMA_NAME FROM information_schema.schemata
        WHERE SCHEMA_NAME NOT IN ('mysql','information_schema','performance_schema','sys')
        ORDER BY SCHEMA_NAME
    """, key=key).splitlines()
    data = {}
    for db in schemas:
        if db in exclude:
            continue
        require(re.fullmatch(r"[a-zA-Z0-9_]+", db), "unexpected schema identifier")
        rows = mysql_value(target, f"""
            SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.tables
            WHERE TABLE_SCHEMA='{db}' ORDER BY TABLE_NAME
        """, key=key)
        data[db] = {"objects": rows}
        for row in rows.splitlines():
            name, kind = row.split("\t")
            require(re.fullmatch(r"[a-zA-Z0-9_]+", name), "unexpected table identifier")
            if kind == "BASE TABLE":
                data[db][name] = mysql_value(target, f"CHECKSUM TABLE `{db}`.`{name}` EXTENDED", key=key)
    return data


def postgres_copy_pressure(target):
    key = "postgres_small"
    fixture(target, key=key, closed=False)
    pg_value(target, """
        INSERT INTO gate_data SELECT i, repeat(md5(i::text),4) FROM generate_series(3,300000) AS i;
        CHECKPOINT;
    """, TEMPLATE, key=key)
    template_hash = pg_value(target, CHECKSUM, TEMPLATE, key=key)
    pg_value(target, f"ALTER DATABASE {TEMPLATE} ALLOW_CONNECTIONS false", key=key)
    before = pg_fingerprint(target, key)
    path = checked(target.podman(
        "exec", target.container(key), "sh", "-ec", 'printf "%s" "$PGDATA"',
    ))
    failures = []
    for strategy, destination in (("WAL_LOG", COPY), ("FILE_COPY", COPY + "_file"),
                                  ("FILE_COPY", "gate__new_01234567")):
        statement = f"CREATE DATABASE {destination} TEMPLATE {TEMPLATE} STRATEGY {strategy}"
        pg_value(target, statement, key=key)
        same(pg_value(target, CHECKSUM, destination, key=key), template_hash)
        pg_value(target, f"DROP DATABASE {destination}", key=key)
        target.observed_control(f"{strategy} copied and matched the template with free space")

        with pressure(target, key, path, 2048):
            failed = target.pg(statement, key=key)
            ready = target.pg("SELECT 1", key=key)
            catalog = target.pg(f"SELECT count(*) FROM pg_database WHERE datname='{destination}'", key=key)
        try:
            require(failed.returncode, f"{destination} unexpectedly fit on the full volume")
            same(checked(ready), "1")
            same(checked(catalog), "0")
            same(pg_fingerprint(target, key), before)
        except AssertionError as error:
            failures.append(f"{strategy} {destination}: {error}")
            print(failures[-1], flush=True)

    pg_value(target, f"ALTER DATABASE {TEMPLATE} ALLOW_CONNECTIONS true", key=key)
    same(pg_value(target, CHECKSUM, TEMPLATE, key=key), template_hash)
    require(not failures, "; ".join(failures))


def mysql_big_table(target, key):
    table(target, "gate_start", key=key)
    table(target, "gate_working", key=key)
    mysql_value(target, """
        CREATE TABLE gate_start.bulk (id int PRIMARY KEY, payload varbinary(1024));
        INSERT INTO gate_start.bulk VALUES (1, RANDOM_BYTES(1024));
    """, key=key)
    for delta in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384):
        mysql_value(target, f"INSERT INTO gate_start.bulk SELECT id+{delta}, payload FROM gate_start.bulk", key=key)


def disk_error(result):
    require(result.returncode and re.search(r"no space left|is full|out of space|disk full", result.stderr, re.I),
            "the load did not report disk exhaustion")


def mysql_copy_pressure(target):
    key = "mysql_small"
    mysql_big_table(target, key)
    add = "INSERT INTO gate_copy.bulk SELECT * FROM gate_start.bulk"
    mysql_value(target, "CREATE DATABASE gate_copy; CREATE TABLE gate_copy.bulk LIKE gate_start.bulk", key=key)
    before = mysql_fingerprint(target, key, ("gate_copy",))
    with pressure(target, key, "/var/lib/mysql", 2048):
        disk_error(target.mysql(add, key=key))
        same(mysql_value(target, "SELECT 1", key=key), "1")
    same(mysql_fingerprint(target, key, ("gate_copy",)), before)
    mysql_value(target, add, key=key)
    for schema in ("gate_start", "gate_copy"):
        same(mysql_value(target, f"SELECT count(*) FROM {schema}.bulk", key=key), "32768")


def mysql_reset_pressure(target):
    key = "mysql_small"
    reference = "mysql_reference"
    mysql_big_table(target, reference)
    mysql_value(target, """
        CREATE TABLE gate_working.bulk LIKE gate_start.bulk;
        INSERT INTO gate_working.bulk SELECT * FROM gate_start.bulk;
        DROP TABLE gate_working.gate_data;
    """, key=reference)
    dump = target.mysql_dump(reference, "gate_working")
    prefix, first_insert, tail = dump.partition(b"INSERT INTO `bulk`")
    require(first_insert and b"DROP DATABASE" in prefix, "dump has no load boundary after the drop")
    load = b"\n".join(line for line in (first_insert + tail).splitlines()
                     if line.startswith(first_insert))
    table(target, "gate_working", key=key)
    table(target, "gate_other", key=key)
    mysql_value(target, """
        CREATE TABLE megasamples.gate_operations(phase varchar(20) PRIMARY KEY);
        INSERT INTO megasamples.gate_operations VALUES ('loading');
    """, key=key)
    checked(target.podman(*target.mysql_args(key=key), stdin=prefix, show_input=False))
    same(mysql_value(target, "SELECT count(*) FROM gate_working.bulk", key=key), "0")
    before = mysql_fingerprint(target, key, ("gate_working",))
    update = "UPDATE megasamples.gate_operations SET phase='done' WHERE phase='loading'"
    with pressure(target, key, "/var/lib/mysql", 2048):
        disk_error(target.podman(*target.mysql_args("gate_working", key=key),
                                 stdin=load + b"\n", show_input=False))
        checked(target.podman("exec", target.container(key), "df", "-Pk", "/var/lib/mysql"))
        phase_write = target.mysql(update, key=key)
        phase = mysql_value(target, "SELECT phase FROM megasamples.gate_operations", key=key)
        same(mysql_value(target, "SELECT 1", key=key), "1")
    after = mysql_fingerprint(target, key, ("gate_working",))
    if phase_write.returncode == 0:
        # Compare the other data independently of the observed change to the operation's row.
        del before["megasamples"]["gate_operations"]
        del after["megasamples"]["gate_operations"]
    same(after, before)
    checked(target.podman(*target.mysql_args(key=key), stdin=dump, show_input=False))
    image = mysql_value(target, "CHECKSUM TABLE gate_working.bulk EXTENDED", key=reference).split("\t")[1]
    same(mysql_value(target, "CHECKSUM TABLE gate_working.bulk EXTENDED", key=key).split("\t")[1], image)
    target.observed_control("reload with free space matched the reference checksum")
    require(phase_write.returncode != 0,
            f"the operation row update succeeded during disk exhaustion; phase read {phase!r}")
    disk_error(phase_write)
    same(phase, "loading")


CASES = {"G-9": postgres_copy_pressure, "G-17a": mysql_copy_pressure, "G-17b": mysql_reset_pressure}
