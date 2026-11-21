"""TCP copy contract against a disposable server provisioned by the native suite."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def server():
    target = os.environ.get("DL077_TCP_COPY_TARGET")
    if not target:
        pytest.skip("requires an explicitly provisioned isolated TCP target")
    path = Path(target)
    assert path.stat().st_uid == os.getuid() and not path.stat().st_mode & 0o077
    config = json.loads(path.read_text())
    assert config["host"] == "127.0.0.1"
    assert config["marker"].startswith("dl077-v1-tcp-")
    if config["engine"] == "postgres":
        import psycopg

        with psycopg.connect(
            host=config["host"], port=config["port"], dbname="megasamples", user=config["owner"],
            password=Path(config["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
        ) as connection:
            observed = connection.execute("SHOW cluster_name").fetchone()[0]
        assert observed == config["marker"]
    elif config["engine"] == "mysql":
        import pymysql

        with pymysql.connect(
            host=config["host"], port=config["port"], database="megasamples", user=config["owner"],
            password=Path(config["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT marker FROM test_fixture_marker")
                assert cursor.fetchone() == (config["marker"],)
    return config


def removed_names(reply):
    return [item["name"] for item in reply["result"]["removed"]]


def copy_command(server, *args, status=0, stdin=False, fault=None, volume_read=True):
    password = Path(server["password_file"]).read_text() if stdin else None
    password_args = ["--password-stdin"] if stdin else ["--password-file", server["password_file"]]
    cli = ["-m", "megasamples", "copy"]
    if fault:
        cli = [str(Path(__file__).parent / "gates" / "dl077_copy_fault.py"), server["engine"], *fault]
    result = subprocess.run(
        [sys.executable, *cli, *args, "--host", server["host"],
         "--port", str(server["port"]), "--user", server["owner"], *password_args],
        input=password, text=True, capture_output=True, timeout=45,
    )
    canary = Path(server["password_file"]).read_text().strip()
    assert canary not in result.stdout + result.stderr
    assert result.returncode == status, result.stdout + result.stderr
    assert len(result.stdout.splitlines()) == 1
    reply = json.loads(result.stdout)
    # A command that stops before reading the service metadata cannot name the volume.
    assert reply["volume"] == (server["volume"] if volume_read else None) and reply["exit"] == status
    return reply


def native(server, sql, *, user=None, database="megasamples", parameters=()):
    auth = {"host": server["host"], "port": server["port"], "user": user or server["owner"],
            "password": Path(server["password_file"]).read_text().strip(), "connect_timeout": 5,
            "autocommit": True}
    if server["engine"] == "postgres":
        import psycopg
        with psycopg.connect(dbname=database, **auth) as connection:
            cursor = connection.execute(sql, parameters or None)
            return cursor.fetchall() if cursor.description else None
    import pymysql
    with pymysql.connect(database=database, **auth) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, parameters or None)
            return list(cursor.fetchall()) if cursor.description else None


def change_lock(server, name):
    """A second session holding the CLI's change lock for one copy name."""
    import hashlib
    if server["engine"] == "postgres":
        key = int.from_bytes(hashlib.sha256(("megasamples/copy/" + name).encode()).digest()[:8],
                             "big", signed=True)
        # The owner may only try the lock, as the CLI does; nothing else holds it here.
        return ("SELECT pg_catalog.pg_try_advisory_lock(%s::bigint)",
                "SELECT pg_catalog.pg_advisory_unlock(%s::bigint)", key)
    key = "megasamples:" + hashlib.sha256(name.encode()).hexdigest()[:48]
    return "SELECT GET_LOCK(%s, 10)", "SELECT RELEASE_LOCK(%s)", key


def session(server, database):
    password = Path(server["password_file"]).read_text().strip()
    if server["engine"] == "postgres":
        import psycopg
        return psycopg.connect(host=server["host"], port=server["port"], dbname=database,
                               user=server["owner"], password=password, connect_timeout=5, autocommit=True)
    import pymysql
    return pymysql.connect(host=server["host"], port=server["port"], database=database,
                           user=server["owner"], password=password, connect_timeout=5, autocommit=True)


def run_sql(connection, sql, parameters=()):
    if hasattr(connection, "execute"):
        cursor = connection.execute(sql, parameters or None)
        return cursor.fetchall() if cursor.description else None
    with connection.cursor() as cursor:
        cursor.execute(sql, parameters or None)
        return cursor.fetchall() if cursor.description else None


def hold_busy(server, name):
    """Keep a copy busy for its engine: a connected session, or an open metadata lock."""
    connection = session(server, name)
    if server["engine"] == "mysql":
        run_sql(connection, "BEGIN")
        run_sql(connection, "SELECT * FROM artist LIMIT 1")
    return connection


def test_drop_wait_is_one_deadline_across_the_lock_and_the_removal(server):
    import threading
    import time
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "deadline")["result"]
    target, proof = engine + ":" + row["name"], ("--identity", row["identity"])
    take, give, key = change_lock(server, row["name"])
    holder, busy = session(server, "megasamples"), hold_busy(server, row["name"])
    # PostgreSQL's DROP DATABASE itself waits up to five seconds for sessions to leave before it
    # refuses, so each of its attempts costs five seconds: a lock held 5 s within a 12 s wait ends at
    # the attempt that passes 12 s (about 15 s), not at a fresh 12 s budget (about 20 s). MySQL's
    # engine wait is the session's lock_wait_timeout, so 2 s within 4 s ends at about 4 s, not 6 s.
    held, wait, low, high = (5, 12, 12, 17.5) if engine == "postgres" else (2, 4, 3.5, 5.5)
    try:
        assert run_sql(holder, take, (key,))[0][0] in (1, True)
        threading.Timer(held, run_sql, (holder, give, (key,))).start()
        started = time.monotonic()
        reply = copy_command(server, "drop", target, *proof, "--wait", str(wait), status=6)
        elapsed = time.monotonic() - started
        assert reply["error"]["code"] == "busy"
        assert low <= elapsed < high, elapsed
        assert copy_command(server, "show", target)["result"]["state"] == "ready"
    finally:
        busy.close()
        holder.close()
    assert copy_command(server, "drop", target, *proof)["result"]["state"] == "gone"


def test_mysql_drop_honours_an_explicit_wait_beyond_five_seconds(server):
    import threading
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    row = copy_command(server, "create", "mysql:chinook", "--prefix", "copy", "--label", "longwait")["result"]
    target, proof = "mysql:" + row["name"], ("--identity", row["identity"])
    busy = hold_busy(server, row["name"])
    try:
        threading.Timer(7, busy.close).start()
        assert copy_command(server, "drop", target, *proof, "--wait", "15")["result"]["state"] == "gone"
    finally:
        copy_command(server, "drop", target, *proof)


def test_drop_refuses_a_copy_whose_proof_changed(server):
    engine = server["engine"]
    admin = {"user": "dl077_fixture_admin"}
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "proof")["result"]
    name, proof = row["name"], ("--identity", row["identity"])
    target = engine + ":" + name
    if engine == "postgres":
        comment = 'COMMENT ON DATABASE "{}" IS \'megasamples-copy/1 {}\''
        native(server, comment.format(name, "0" * 32), **admin)
        restore = comment.format(name, row["identity"])
        exists = ("SELECT count(*) FROM pg_database WHERE datname=%s", "postgres")
    else:
        native(server, f"DROP EVENT `{name}`.`megasamples_copy_{row['identity']}`", **admin)
        restore = (f"CREATE EVENT `{name}`.`megasamples_copy_{row['identity']}` ON SCHEDULE AT "
                   "CURRENT_TIMESTAMP + INTERVAL 1 YEAR ON COMPLETION PRESERVE DISABLE DO SELECT 1")
        exists = ("SELECT count(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", "megasamples")
    try:
        assert copy_command(server, "show", target)["result"]["state"] == "inconsistent"
        assert copy_command(server, "drop", target, *proof, status=5)["error"]["code"] == "inconsistent"
        copy_command(server, "release", target, *proof, status=5)
        swept = copy_command(server, "sweep", engine, "--prefix", "copy")["result"]
        assert not any(item["name"] == name for item in swept["removed"])
        assert native(server, exists[0], user=admin["user"], database=exists[1], parameters=(name,))[0][0] == 1
    finally:
        native(server, restore, **admin)
    assert copy_command(server, "drop", target, *proof)["result"]["state"] == "gone"


def test_mysql_declared_reader_is_not_an_outside_grant(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    readers = native(server, "SELECT User FROM mysql.db WHERE User='reader_b'", user="dl077_fixture_admin",
                     database="mysql")
    if not readers:
        pytest.skip("requires an image built with the declared copy reader reader_b")
    reply = copy_command(server, "create", "mysql:chinook", "--prefix", "copy", "--label", "declared")
    target = "mysql:" + reply["result"]["name"]
    proof = ("--identity", reply["result"]["identity"])
    try:
        assert reply["result"]["state"] == "ready" and reply["warnings"] == []
        shown = copy_command(server, "show", target)
        assert shown["result"]["state"] == "ready" and shown["warnings"] == []
    finally:
        copy_command(server, "drop", target, *proof)


def test_sweep_keeps_a_copy_renewed_after_its_selection(server):
    """T-15's invariant across the selection and the removal: identity and revision, and the lease read again."""
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "renewed")["result"]
    target, proof = engine + ":" + row["name"], ("--identity", row["identity"])
    try:
        copy_command(server, "release", target, *proof)
        swept = copy_command(server, "sweep", engine, "--prefix", "copy",
                             fault=("renew-first", row["name"] + ":" + row["identity"]))["result"]
        assert row["name"] not in removed_names({"result": swept})
        assert any(item["copy"]["name"] == row["name"] and item["reason"] in ("changed", "leased")
                   for item in swept["kept"])
        shown = copy_command(server, "show", target)["result"]
        assert shown["state"] == "ready" and shown["revision"] == row["revision"] + 2
    finally:
        copy_command(server, "drop", target, *proof)


def ledger(server):
    return native(server, "SELECT name, record FROM copy_ledger_copy ORDER BY name",
                  user="dl077_fixture_admin")


def test_lost_connection_during_metadata_is_exit_3_with_the_identity(server):
    """Astra round 2, 7: nothing was written before the metadata read, so 3 promises truthfully."""
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "metadata")["result"]
    target, proof = engine + ":" + row["name"], ("--identity", row["identity"])
    try:
        reply = copy_command(server, "renew", target, *proof, "--lease", "7d", status=3, fault=("metadata", "-"),
                             volume_read=False)
        assert reply["error"]["code"] == "connection" and reply["error"]["identity"] == row["identity"]
        assert copy_command(server, "show", target)["result"]["revision"] == row["revision"]
    finally:
        copy_command(server, "drop", target, *proof)


@pytest.mark.parametrize("command", ["renew", "list"])
def test_lost_connection_before_any_write_is_exit_3_past_initialisation(server, command):
    """Sol round 3, P2-5: a disconnect while reading a copy's record, before any write, changed nothing."""
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "read" + command)["result"]
    target, proof = engine + ":" + row["name"], ("--identity", row["identity"])
    try:
        args = (("renew", target, *proof, "--lease", "7d") if command == "renew"
                else ("list", engine, "--prefix", "copy"))
        reply = copy_command(server, *args, status=3, fault=("load", "before"))
        assert reply["error"]["code"] == "connection"
        if command == "renew":
            assert reply["error"]["identity"] == row["identity"]
        assert copy_command(server, "show", target)["result"]["revision"] == row["revision"]
    finally:
        copy_command(server, "drop", target, *proof)


def test_sweep_that_stops_after_a_removal_reports_what_it_removed(server):
    """Astra round 2, 3 / Fable round 2, 4: exit 8 with the completed removals and where it stopped."""
    engine = server["engine"]
    admin = {"user": "dl077_fixture_admin"}
    first, second = (copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", label)["result"]
                     for label in ("partiala", "partialb"))
    for row in (first, second):
        copy_command(server, "release", engine + ":" + row["name"], "--identity", row["identity"])
    removed_first, kept_second = sorted((first, second), key=lambda row: row["name"])
    try:
        reply = copy_command(server, "sweep", engine, "--prefix", "copy", status=8,
                             fault=("corrupt-after-first", kept_second["name"]))
        assert reply["error"]["code"] == "format-unknown"
        assert reply["error"]["identity"] == kept_second["identity"]
        assert removed_names(reply) == [removed_first["name"]]
        assert any(item["copy"]["name"] == kept_second["name"] for item in reply["result"]["kept"])
    finally:
        name = kept_second["name"]
        database = "postgres" if engine == "postgres" else "megasamples"
        quote = '"' if engine == "postgres" else "`"
        native(server, f"DROP DATABASE IF EXISTS {quote}{name}{quote}", database=database, **admin)
        native(server, "DELETE FROM copy_ledger_copy WHERE name=%s", parameters=(name,), **admin)
        copy_command(server, "drop", engine + ":" + removed_first["name"], "--identity", removed_first["identity"])


def two_released(server, *labels):
    engine = server["engine"]
    rows = [copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", label)["result"]
            for label in labels]
    for row in rows:
        copy_command(server, "release", engine + ":" + row["name"], "--identity", row["identity"])
    return sorted(rows, key=lambda row: row["name"])


def discard(server, row):
    engine = server["engine"]
    admin = {"user": "dl077_fixture_admin"}
    database = "postgres" if engine == "postgres" else "megasamples"
    quote = '"' if engine == "postgres" else "`"
    native(server, f"DROP DATABASE IF EXISTS {quote}{row['name']}{quote}", database=database, **admin)
    native(server, "DELETE FROM copy_ledger_copy WHERE name=%s", parameters=(row["name"],), **admin)


def test_dry_run_that_meets_an_unreadable_record_changes_nothing_and_says_so(server):
    """Opus round 3, 2: a dry run removes nothing, so its refusal is 5, never 8."""
    engine = server["engine"]
    first, second = two_released(server, "dryfirst", "drysecond")
    try:
        reply = copy_command(server, "sweep", engine, "--prefix", "copy", "--dry-run", status=5,
                             fault=("corrupt-before-recheck", second["name"]))
        assert reply["error"]["code"] == "format-unknown" and reply["result"] is None
        assert copy_command(server, "show", engine + ":" + first["name"])["result"]["revision"] == first["revision"] + 1
    finally:
        discard(server, second)
        copy_command(server, "drop", engine + ":" + first["name"], "--identity", first["identity"])


def test_sweep_after_a_busy_rollback_reports_the_change(server):
    """Sol round 3, P2-4 / Opus round 3, 2: a busy rollback advanced a revision, so a later refusal is 8."""
    engine = server["engine"]
    first, second = two_released(server, "busyfirst", "busysecond")
    busy = hold_busy(server, first["name"])
    try:
        reply = copy_command(server, "sweep", engine, "--prefix", "copy", status=8,
                             fault=("corrupt-before-recheck", second["name"]))
        assert reply["error"]["code"] == "format-unknown"
        assert removed_names(reply) == []
        assert {"name": first["name"], "reason": "busy"} in [
            {"name": item["copy"]["name"], "reason": item["reason"]} for item in reply["result"]["kept"]]
    finally:
        busy.close()
        discard(server, second)
        copy_command(server, "drop", engine + ":" + first["name"], "--identity", first["identity"])


def test_sweep_whose_unlock_fails_lists_its_removal_once(server):
    """Sol round 3, P2-4: a copy removed is reported removed, and never also kept."""
    engine = server["engine"]
    first, second = two_released(server, "unlockfirst", "unlocksecond")
    try:
        reply = copy_command(server, "sweep", engine, "--prefix", "copy", status=8, fault=("unlock-fails", "-"))
        assert removed_names(reply) == [first["name"]]
        assert first["name"] not in [item["copy"]["name"] for item in reply["result"]["kept"]]
    finally:
        for row in (first, second):
            copy_command(server, "drop", engine + ":" + row["name"], "--identity", row["identity"])


def test_drop_losing_its_connection_at_the_proof_read_is_exit_3(server):
    """Sol round 4, P2-5: the removal's own proof read comes before any write."""
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "proofread")["result"]
    target, proof = engine + ":" + row["name"], ("--identity", row["identity"])
    try:
        reply = copy_command(server, "drop", target, *proof, status=3, fault=("state-second", "-"))
        assert reply["error"]["code"] == "connection" and reply["error"]["identity"] == row["identity"]
        shown = copy_command(server, "show", target)["result"]
        assert (shown["state"], shown["revision"]) == ("ready", row["revision"])
    finally:
        copy_command(server, "drop", target, *proof)


def test_a_confirmed_removal_whose_ledger_row_remains_is_reported_removed(server):
    """Sol round 4, P2-4: the engine dropped the copy; only its ledger row is unsettled."""
    engine = server["engine"]
    first, second = two_released(server, "forgetfirst", "forgetsecond")
    admin = {"user": "dl077_fixture_admin"}
    try:
        reply = copy_command(server, "sweep", engine, "--prefix", "copy", status=8, fault=("forget-fails", "-"))
        assert reply["error"]["code"] == "drop-unsettled" and reply["error"]["identity"] == first["identity"]
        removed = {item["name"]: item for item in reply["result"]["removed"]}
        assert removed[first["name"]]["state"] == "gone" and removed[first["name"]]["ledger"] == "unsettled"
        assert first["name"] not in [item["copy"]["name"] for item in reply["result"]["kept"]]
        assert copy_command(server, "show", engine + ":" + first["name"])["result"]["state"] == "gone"
        single = copy_command(server, "drop", engine + ":" + second["name"], "--identity", second["identity"],
                              status=8, fault=("forget-fails", "-"))
        assert single["error"]["code"] == "drop-unsettled" and single["result"]["state"] == "gone"
        assert single["result"]["ledger"] == "unsettled"
    finally:
        for row in (first, second):
            copy_command(server, "drop", engine + ":" + row["name"], "--identity", row["identity"])
        native(server, "DELETE FROM copy_ledger_copy WHERE name IN (%s, %s)",
               parameters=(first["name"], second["name"]), **admin)


def test_create_refuses_a_namespace_whose_records_it_cannot_read(server):
    """Astra round 2, 4: admission validates the namespace's records first and writes nothing."""
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "newer")["result"]
    if engine == "postgres":
        change = "jsonb_set(record, '{tag}', '\"megasamples-copy/99\"')"
    else:
        change = "JSON_SET(record, '$.tag', 'megasamples-copy/99')"
    native(server, f"UPDATE copy_ledger_copy SET record={change} WHERE name=%s", parameters=(row["name"],))
    try:
        before = ledger(server)
        reply = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "admitted", status=5)
        assert reply["error"]["code"] == "format-unknown"
        assert ledger(server) == before
    finally:
        native(server, f"UPDATE copy_ledger_copy SET record=JSON_SET(record, '$.tag', 'megasamples-copy/1') WHERE name=%s"
               if engine == "mysql" else
               "UPDATE copy_ledger_copy SET record=jsonb_set(record, '{tag}', '\"megasamples-copy/1\"') WHERE name=%s",
               parameters=(row["name"],))
        copy_command(server, "drop", engine + ":" + row["name"], "--identity", row["identity"])


def test_postgres_newer_template_registration_is_unsupported_not_missing(server):
    """Astra round 2, 4: a newer template tag is format-unknown (5), not no-template (4)."""
    if server["engine"] != "postgres":
        pytest.skip("requires the PostgreSQL fixture")
    admin = {"user": "dl077_fixture_admin", "database": "postgres"}
    comment = native(server, "SELECT shobj_description(oid, 'pg_database') FROM pg_database "
                             "WHERE datname='chinook_start'", **admin)[0][0]
    newer = comment.replace("megasamples-template/1 ", "megasamples-template/2 ", 1)
    native(server, "COMMENT ON DATABASE chinook_start IS '" + newer.replace("'", "''") + "'", **admin)
    try:
        reply = copy_command(server, "create", "postgres:chinook", "--prefix", "copy", "--label", "newertpl", status=5)
        assert reply["error"]["code"] == "format-unknown" and reply["error"]["identity"] is None
        assert copy_command(server, "list", "postgres", "--prefix", "copy", "--label", "newertpl")["result"]["copies"] == []
    finally:
        native(server, "COMMENT ON DATABASE chinook_start IS '" + comment.replace("'", "''") + "'", **admin)


def test_busy_drop_promises_only_what_it_wrote(server):
    """Astra round 2, 8: lock contention changes nothing; an already-dropping copy stays dropping."""
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy", "--label", "busyscope")["result"]
    name, target, proof = row["name"], engine + ":" + row["name"], ("--identity", row["identity"])
    take, give, key = change_lock(server, name)
    holder = session(server, "megasamples")
    try:
        assert run_sql(holder, take, (key,))[0][0] in (1, True)
        reply = copy_command(server, "drop", target, *proof, status=6)
        assert reply["error"]["code"] == "busy"
        run_sql(holder, give, (key,))
        shown = copy_command(server, "show", target)["result"]
        assert (shown["state"], shown["revision"]) == ("ready", row["revision"])
        if engine == "postgres":
            change = "jsonb_set(record, '{phase}', '\"dropping\"')"
        else:
            change = "JSON_SET(record, '$.phase', 'dropping')"
        native(server, f"UPDATE copy_ledger_copy SET record={change} WHERE name=%s", parameters=(name,))
        busy = hold_busy(server, name)
        try:
            copy_command(server, "drop", target, *proof, "--wait", "1", status=6)
            shown = copy_command(server, "show", target)["result"]
            assert (shown["state"], shown["revision"]) == ("dropping", row["revision"])
        finally:
            busy.close()
    finally:
        holder.close()
    assert copy_command(server, "drop", target, *proof)["result"]["state"] == "gone"


def test_a_name_never_made_shows_gone(server):
    """Fable 14 / Astra round 2, 12: one state name for neither a row nor an object."""
    engine = server["engine"]
    shown = copy_command(server, "show", engine + ":copy_chinook_000000000000")["result"]
    assert shown["state"] == "gone" and shown["identity"] is None


def test_mysql_namespace_owner_is_confined_to_its_pattern(server):
    """T-9 with G-11b and G-11c's cases through the built image, as the namespace owner."""
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    import pymysql
    connection = session(server, "megasamples")
    try:
        for sql in ("CREATE DATABASE copyx_outside", "CREATE DATABASE copy",
                    "CREATE DATABASE chinook_other", "DROP DATABASE chinook",
                    "INSERT INTO chinook.artist SELECT * FROM chinook.artist LIMIT 0",
                    "ALTER DATABASE chinook_start READ ONLY = 0",
                    "GRANT SELECT ON `copy\\_%`.* TO 'reader_b'@'%'",
                    "CREATE USER 'copy_made'@'%'"):
            with pytest.raises(pymysql.err.MySQLError):
                run_sql(connection, sql)
        run_sql(connection, "CREATE DATABASE copy_scratch_confinement")
        run_sql(connection, "DROP DATABASE copy_scratch_confinement")
    finally:
        connection.close()


def test_server_inventory_reports_unmanaged_names(server):
    engine = server["engine"]
    admin = {"user": "dl077_fixture_admin"}
    native(server, "CREATE DATABASE copy_scratch", **admin)
    try:
        listed = copy_command(server, "list", engine, "--prefix", "copy", stdin=True)["result"]["copies"]
        assert ("copy_scratch", "unmanaged") in [(row["name"], row["state"]) for row in listed]
        swept = copy_command(server, "sweep", engine, "--prefix", "copy", "--dry-run")["result"]
        assert any(item["copy"]["name"] == "copy_scratch" and item["reason"] == "unmanaged"
                   for item in swept["kept"])
    finally:
        native(server, "DROP DATABASE copy_scratch", **admin)


def test_server_sweep_recovers_expired_dropping_copy(server):
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy",
                       "--label", "dropping")["result"]
    name = row["name"]
    target = engine + ":" + name
    identity = ("--identity", row["identity"])
    copy_command(server, "release", target, *identity)
    if engine == "postgres":
        change = "jsonb_set(record, '{phase}', '\"dropping\"')"
    else:
        change = """JSON_SET(record, '$.phase', 'dropping')"""
    native(server, f"UPDATE copy_ledger_copy SET record={change} WHERE name=%s", parameters=(name,))
    try:
        assert copy_command(server, "show", target)["result"]["state"] == "dropping"
        preview = copy_command(server, "sweep", engine, "--prefix", "copy", "--dry-run")["result"]
        assert any(item["name"] == name for item in preview["removed"])
        assert copy_command(server, "show", target)["result"]["state"] == "dropping"
        swept = copy_command(server, "sweep", engine, "--prefix", "copy")["result"]
        assert any(item["name"] == name for item in swept["removed"])
        assert copy_command(server, "show", target)["result"]["state"] == "gone"
    finally:
        copy_command(server, "drop", target, *identity)


@pytest.mark.parametrize("when", ["before", "after"])
def test_lost_reservation_reply_retains_the_issued_identity(server, when):
    engine = server["engine"]
    label = "lost" + when
    reply = copy_command(server, "create", engine + ":chinook", "--prefix", "copy",
                         "--label", label, status=8, fault=("insert", when))
    error = reply["error"]
    assert error["code"] == "create-unsettled" and len(error["identity"]) == 32
    rows = copy_command(server, "list", engine, "--prefix", "copy", "--label", label)["result"]["copies"]
    if when == "before":
        assert rows == []
    else:
        assert [(row["identity"], row["state"]) for row in rows] == [(error["identity"], "stale")]
        copy_command(server, "drop", engine + ":" + rows[0]["name"], "--identity", error["identity"])


@pytest.mark.parametrize("when", ["before", "after"])
def test_lost_lease_reply_retains_the_supplied_identity(server, when):
    engine = server["engine"]
    row = copy_command(server, "create", engine + ":chinook", "--prefix", "copy",
                       "--label", "renew" + when)["result"]
    target = engine + ":" + row["name"]
    identity = ("--identity", row["identity"])
    try:
        reply = copy_command(server, "renew", target, *identity, "--lease", "7d", status=8,
                             fault=("change", when))
        assert reply["error"]["identity"] == row["identity"]
        latest = copy_command(server, "show", target)["result"]
        assert latest["revision"] == row["revision"] + (when == "after")
    finally:
        copy_command(server, "drop", target, *identity)


def test_postgres_copy_lifecycle_on_tcp(server):
    if server["engine"] != "postgres":
        pytest.skip("requires the PostgreSQL fixture")

    def command(*args, status=0):
        result = subprocess.run(
            [sys.executable, "-m", "megasamples", "copy", *args, "--host", server["host"],
             "--port", str(server["port"]), "--user", server["owner"],
             "--password-file", server["password_file"]],
            text=True, capture_output=True, timeout=45,
        )
        assert result.returncode == status, result.stdout + result.stderr
        assert len(result.stdout.splitlines()) == 1
        document = json.loads(result.stdout)
        assert document["volume"] == server["volume"]
        assert document["exit"] == status
        return document

    created = command("create", "postgres:chinook", "--prefix", "copy", "--label", "first")["result"]
    target = "postgres:" + created["name"]
    identity = ("--identity", created["identity"])
    assert created["state"] == "ready"
    assert command("show", target)["result"]["proof"]["oid"] > 0
    assert command("list", "postgres", "--prefix", "copy", "--label", "first")["result"]["copies"] == [created]
    command("renew", target, *identity, "--lease", "7d")
    assert created["name"] not in removed_names(command("sweep", "postgres", "--prefix", "copy"))
    command("release", target, *identity)
    assert created["name"] in removed_names(command("sweep", "postgres", "--prefix", "copy", "--dry-run"))
    assert command("show", target)["result"]["state"] == "ready"
    assert created["name"] in removed_names(command("sweep", "postgres", "--prefix", "copy"))
    command("drop", target, *identity)

    second = command("create", "postgres:chinook", "--prefix", "copy", "--label", "second")["result"]
    target = "postgres:" + second["name"]
    identity = ("--identity", second["identity"])
    import psycopg

    with psycopg.connect(
        host=server["host"], port=server["port"], dbname=second["name"], user=server["owner"],
        password=Path(server["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
    ) as session:
        session.execute("CREATE TABLE busy_probe (i int)")
        session.execute("INSERT INTO busy_probe VALUES (42)")
        session.commit()
        command("drop", target, *identity, status=6)
        assert session.execute("SELECT i FROM busy_probe").fetchone() == (42,)
        restored = command("show", target)["result"]
        assert restored["state"] == "ready" and restored["revision"] == second["revision"] + 2
        command("release", target, *identity)
        # The dry run reports the sweep's selection; only the removal learns that the engine
        # refuses it while a session is connected (design 2.2 and 3.1, as narrowed).
        preview = command("sweep", "postgres", "--prefix", "copy", "--dry-run")["result"]
        assert second["name"] in [item["name"] for item in preview["removed"]]
        sweep = command("sweep", "postgres", "--prefix", "copy")["result"]
        assert second["name"] not in [item["name"] for item in sweep["removed"]]
        assert any(item["copy"]["name"] == second["name"] and item["reason"] == "busy"
                   for item in sweep["kept"])
        assert command("show", target)["result"]["state"] == "ready"
        assert session.execute("SELECT i FROM busy_probe").fetchone() == (42,)
    assert command("drop", target, *identity)["result"]["state"] == "gone"


def test_mysql_copy_withholding_precedes_a_reservation(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    connection = ["--host", server["host"], "--port", str(server["port"]), "--user", server["owner"],
                  "--password-file", server["password_file"]]
    for database, code in (("replay_trigger", "not-replayable"), ("replay_func", "not-replayable"),
                           ("oracle_hr", "dependency-group"), ("unknown_database", "no-template")):
        result = subprocess.run(
            [sys.executable, "-m", "megasamples", "copy", "create", "mysql:" + database,
             "--prefix", "copy", "--label", "withheld", *connection],
            text=True, capture_output=True, timeout=20,
        )
        assert result.returncode == 4, result.stdout + result.stderr
        document = json.loads(result.stdout)
        assert document["error"]["code"] == code
        assert document["error"]["identity"] is None
    listed = subprocess.run(
        [sys.executable, "-m", "megasamples", "copy", "list", "mysql", "--prefix", "copy", *connection],
        text=True, capture_output=True, timeout=20,
    )
    assert listed.returncode == 0, listed.stdout + listed.stderr
    assert [row for row in json.loads(listed.stdout)["result"]["copies"] if row["label"] == "withheld"] == []


def test_mysql_copy_lifecycle_and_schema_replay(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    import pymysql

    def command(*args, status=0):
        result = subprocess.run(
            [sys.executable, "-m", "megasamples", "copy", *args, "--host", server["host"],
             "--port", str(server["port"]), "--user", server["owner"],
             "--password-file", server["password_file"]],
            text=True, capture_output=True, timeout=45,
        )
        assert result.returncode == status, result.stdout + result.stderr
        assert len(result.stdout.splitlines()) == 1
        document = json.loads(result.stdout)
        assert document["volume"]
        return document

    row = command("create", "mysql:sample", "--prefix", "copy", "--label", "fixture")["result"]
    assert row["state"] == "ready"
    target = "mysql:" + row["name"]
    identity = ("--identity", row["identity"])
    command("show", target)
    command("list", "mysql", "--prefix", "copy", "--label", "fixture")
    command("renew", target, *identity, "--lease", "7d")
    assert row["name"] not in removed_names(command("sweep", "mysql", "--prefix", "copy"))
    with pymysql.connect(
        host=server["host"], port=server["port"], database=row["name"], user=server["owner"],
        password=Path(server["password_file"]).read_text().rstrip("\n"), connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM v2")
            assert cursor.fetchall() == ((0,), (42,))
            cursor.execute("INSERT INTO parent VALUES (51)")
            cursor.execute("SELECT id FROM v2 ORDER BY id")
            assert cursor.fetchall() == ((0,), (42,), (51,))
            cursor.execute("SELECT id FROM sample_start.v2")
            assert cursor.fetchall() == ((0,), (42,))
            cursor.execute("CALL read_value()")
            assert cursor.fetchall() == ((0,), (42,), (51,))
            while cursor.nextset():
                pass
            # Round 9: the copy's program reads the copy, through `1--1` and a comment before the dot.
            cursor.execute("CALL read_lexed()")
            assert cursor.fetchall() == ((2, 0), (2, 42), (2, 51))
            while cursor.nextset():
                pass
            with pytest.raises(pymysql.IntegrityError):
                cursor.execute("INSERT INTO child (id, parent_id) VALUES (2,999)")
            cursor.execute("SELECT STATUS FROM information_schema.EVENTS WHERE EVENT_NAME=%s AND EVENT_SCHEMA=%s",
                           (row["proof"]["event"], row["name"]))
            assert cursor.fetchone() == ("DISABLED",)
            cursor.execute("SELECT amount FROM child")
            assert cursor.fetchone() == (84,)
            cursor.execute("SELECT DEFINER, STATUS, EVENT_DEFINITION FROM information_schema.EVENTS "
                           "WHERE EVENT_NAME='read_event' AND EVENT_SCHEMA=%s", (row["name"],))
            definer, event_status, definition = cursor.fetchone()
            assert definer == server["owner"] + "@%" and event_status == "DISABLED"
            assert row["name"] in definition and "sample_start" not in definition
            bodies = native(server, "SELECT ROUTINE_SCHEMA, ROUTINE_DEFINITION FROM information_schema.ROUTINES "
                            "WHERE ROUTINE_NAME='read_lexed' AND ROUTINE_SCHEMA IN (%s, %s, %s)",
                            user="dl077_fixture_admin", parameters=("sample", "sample_start", row["name"]))
            bodies = {schema: body for schema, body in bodies}
            assert "1--1" in bodies["sample"] and "/* gap */" in bodies["sample"], bodies["sample"]
            for schema in ("sample_start", row["name"]):
                assert f"`{schema}` /* gap */ .parent" in bodies[schema], (schema, bodies[schema])
            # Astra round 2, 5: each stored program keeps the SQL mode its source was created with.
            # Read as the fixture's administrator: the owner holds no routine privilege on the template.
            # Each program has its own mode, and the event its own time zone (Sol and Opus round 3).
            for source in ("sample", "sample_start", row["name"]):
                modes = native(server, """
                    SELECT (SELECT SQL_MODE FROM information_schema.ROUTINES
                            WHERE ROUTINE_SCHEMA=%s AND ROUTINE_NAME='read_value'),
                           (SELECT SQL_MODE FROM information_schema.EVENTS
                            WHERE EVENT_SCHEMA=%s AND EVENT_NAME='read_event'),
                           (SELECT TIME_ZONE FROM information_schema.EVENTS
                            WHERE EVENT_SCHEMA=%s AND EVENT_NAME='read_event')
                """, user="dl077_fixture_admin", parameters=(source, source, source))[0]
                assert tuple(modes) == ("ONLY_FULL_GROUP_BY,STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION",
                                        "STRICT_TRANS_TABLES,NO_ZERO_DATE", "+05:30"), source
    command("release", target, *identity)
    assert row["name"] in removed_names(command("sweep", "mysql", "--prefix", "copy", "--dry-run"))
    assert row["name"] in removed_names(command("sweep", "mysql", "--prefix", "copy"))
    command("drop", target, *identity)


def test_mysql_copy_replacement_grant_refuses_sweep(server):
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    admin = {"user": "dl077_fixture_admin"}
    native(server, "CREATE USER 'outside_reader'@'%' ACCOUNT LOCK", **admin)
    native(server, r"GRANT DROP ON `copy\_%`.* TO 'outside_reader'@'%'", **admin)
    reply = copy_command(server, "create", "mysql:chinook", "--prefix", "copy", "--label", "outside")
    row = reply["result"]
    target = "mysql:" + row["name"]
    proof = ("--identity", row["identity"])
    try:
        assert row["state"] == "not-exclusive" and reply["warnings"]
        shown = copy_command(server, "show", target)
        assert shown["result"] == row and shown["warnings"] == reply["warnings"]
        listed = copy_command(server, "list", "mysql", "--prefix", "copy", "--label", "outside")
        assert listed["result"]["copies"] == [row] and listed["warnings"] == reply["warnings"]
        assert copy_command(server, "drop", target, *proof, status=5)["error"]["code"] == "not-exclusive"
        assert copy_command(server, "sweep", "mysql", "--prefix", "copy", status=5)["error"]["code"] == "not-exclusive"
        native(server, r"REVOKE DROP ON `copy\_%`.* FROM 'outside_reader'@'%'", **admin)
        native(server, f"GRANT SELECT ON `{row['name']}`.`artist` TO 'outside_reader'@'%'", **admin)
        shown = copy_command(server, "show", target)
        assert shown["result"]["state"] == "ready"
        assert any(warning["account"] == "outside_reader@%" for warning in shown["warnings"])
        assert copy_command(server, "drop", target, *proof)["result"]["state"] == "gone"
    finally:
        native(server, "DROP USER 'outside_reader'@'%'", **admin)
        copy_command(server, "drop", target, *proof)


def test_postgres_create_keeps_a_copy_the_hook_left_open(server):
    """T-7 through copy create: the CLI's own closure check, and the read grant made last."""
    if server["engine"] != "postgres" or os.environ.get("DL077_PG_UNCLOSED_FAULT") != "1":
        pytest.skip("requires a PostgreSQL image built with tests/gates/faults/pg-fallback.patch")
    admin = {"user": "dl077_fixture_admin"}
    reply = copy_command(server, "create", "postgres:chinook", "--prefix", "copy", "--label", "unclosed", status=8)
    assert reply["error"]["code"] == "create-unsettled"
    identity = reply["error"]["identity"]
    rows = copy_command(server, "list", "postgres", "--prefix", "copy", "--label", "unclosed")["result"]["copies"]
    assert [(row["identity"], row["state"]) for row in rows] == [(identity, "interrupted")]
    name = rows[0]["name"]
    try:
        opened, comment, readers = native(server, """
            SELECT EXISTS (SELECT FROM aclexplode(coalesce(datacl, acldefault('d', datdba)))
                           WHERE grantee = 0 AND privilege_type = 'CONNECT'),
                   shobj_description(oid, 'pg_database'),
                   (SELECT count(*) FROM aclexplode(coalesce(datacl, acldefault('d', datdba)))
                    WHERE grantee = 'megasamples_copy_copy_read'::regrole)
            FROM pg_database WHERE datname = %s
        """, database="postgres", parameters=(name,), **admin)[0]
        assert opened and comment is None and readers == 0
        swept = copy_command(server, "sweep", "postgres", "--prefix", "copy")["result"]
        assert {"name": name, "reason": "interrupted"} in [
            {"name": item["copy"]["name"], "reason": item["reason"]} for item in swept["kept"]]
        assert copy_command(server, "drop", "postgres:" + name, "--identity", identity,
                            status=5)["error"]["code"] == "interrupted"
    finally:
        native(server, f'DROP DATABASE IF EXISTS "{name}"', database="postgres", **admin)
        native(server, "DELETE FROM copy_ledger_copy WHERE name=%s", parameters=(name,), **admin)


def test_mysql_create_that_fails_verification_is_interrupted_and_kept(server):
    """Fable 10: the count and checksum step, and the interrupted outcome after a failed step."""
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    admin = {"user": "dl077_fixture_admin"}
    reply = copy_command(server, "create", "mysql:sample", "--prefix", "copy", "--label", "shortfill",
                         status=8, fault=("short-fill", "-"))
    assert reply["error"]["code"] == "create-unsettled"
    identity = reply["error"]["identity"]
    rows = copy_command(server, "list", "mysql", "--prefix", "copy", "--label", "shortfill")["result"]["copies"]
    assert [(row["identity"], row["state"]) for row in rows] == [(identity, "interrupted")]
    name = rows[0]["name"]
    try:
        assert native(server, f"SELECT COUNT(*) FROM `{name}`.parent", **admin)[0][0] == 1
        swept = copy_command(server, "sweep", "mysql", "--prefix", "copy")["result"]
        assert {"name": name, "reason": "interrupted"} in [
            {"name": item["copy"]["name"], "reason": item["reason"]} for item in swept["kept"]]
        assert copy_command(server, "drop", "mysql:" + name, "--identity", identity,
                            status=5)["error"]["code"] == "interrupted"
        assert native(server, "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
                      parameters=(name,), **admin)[0][0] == 1
    finally:
        native(server, f"DROP DATABASE IF EXISTS `{name}`", **admin)
        native(server, "DELETE FROM copy_ledger_copy WHERE name=%s", parameters=(name,), **admin)


def test_mysql_ansi_quotes_program_is_withheld_before_any_reservation(server):
    """Sol round 3, P3: double-quoted names are not rewritten, so ANSI_QUOTES programs are withheld."""
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    reply = copy_command(server, "create", "mysql:replay_ansi", "--prefix", "copy", "--label", "ansi", status=4)
    assert reply["error"]["code"] == "not-replayable" and "ANSI_QUOTES" in reply["error"]["message"]
    assert copy_command(server, "list", "mysql", "--prefix", "copy", "--label", "ansi")["result"]["copies"] == []


def test_mysql_no_backslash_escapes_program_is_withheld_before_any_reservation(server):
    """Sol round 4, P3-8: the schema rewrite tokenizes with backslash escapes, so this mode is withheld."""
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    reply = copy_command(server, "create", "mysql:replay_nobackslash", "--prefix", "copy", "--label", "nbe", status=4)
    assert reply["error"]["code"] == "not-replayable" and "NO_BACKSLASH_ESCAPES" in reply["error"]["message"]


def test_mysql_template_of_an_older_format_is_refused_before_any_reservation(server):
    """Opus round 3, 4: a template whose programs carry no recorded settings is format-unknown, exit 5."""
    if server["engine"] != "mysql":
        pytest.skip("requires the MySQL fixture")
    admin = {"user": "dl077_fixture_admin"}
    original = native(server, "SELECT metadata FROM template_ddl WHERE name='sample'", **admin)[0][0]
    metadata = json.loads(original)
    metadata["objects"] = [item["ddl"] if isinstance(item, dict) else item for item in metadata["objects"]]
    native(server, "UPDATE template_ddl SET metadata=%s WHERE name='sample'", parameters=(json.dumps(metadata),), **admin)
    try:
        reply = copy_command(server, "create", "mysql:sample", "--prefix", "copy", "--label", "older", status=5)
        assert reply["error"]["code"] == "format-unknown" and reply["error"]["identity"] is None
    finally:
        native(server, "UPDATE template_ddl SET metadata=%s WHERE name='sample'", parameters=(original,), **admin)


def test_mysql_template_size_uses_allocated_tablespace_bytes(server):
    if server["engine"] != "mysql" or "chinook_allocated_bytes" not in server:
        pytest.skip("requires the MySQL fixture with a file-allocation witness")
    rows = native(server, "SELECT JSON_EXTRACT(metadata,'$.bytes') FROM template_ddl WHERE name='chinook'")
    # Copying a sparse data directory into an image can change its block allocation.
    assert abs(int(rows[0][0]) - server["chinook_allocated_bytes"]) <= server["chinook_tablespaces"] * 4096
