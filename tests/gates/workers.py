"""Reset crossing gates using raw session roles and native clients."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack

from clients import Client, kill_managed_client, managed_client, until
from mysql import checksum, value as mysql_value
from native import checked, denied, require, same
from postgres import value as pg_value


def pg_worker_isolated(target):
    archive_source = "gate_image_source"
    working = "gate_working"
    first, second = "gate_working__new_01234567", "gate_working__new_89abcdef"
    model = "CREATE TABLE gate_data (id int PRIMARY KEY, marker text)"
    digest = "SELECT md5(string_agg(id::text || ':' || marker, ',' ORDER BY id)) FROM gate_data"
    reference = "postgres_reference"
    for db, marker, key in ((archive_source, "baked", reference), (working, "working", "postgres")):
        pg_value(target, f"CREATE DATABASE {db} TEMPLATE template0", key=key)
        pg_value(target, f"{model}; INSERT INTO gate_data VALUES (1,'{marker}')", db, key=key)
    archive = target.pg_restore_archive(archive_source, reference)
    expected = pg_value(target, digest, working)
    baked = pg_value(target, digest, archive_source, key=reference)
    oid_query = "SELECT oid FROM pg_database WHERE datname='{}'"

    pg_value(target, """
        CREATE TABLE gate_operations (operation int PRIMARY KEY, phase text, oid oid);
    """, "megasamples")
    lock = "SELECT pg_try_advisory_lock(260077)"
    with managed_client(target, target.psql_args("megasamples"), "coordinator") as coordinator:
        same(coordinator.query(lock + ";"), "t")
        coordinator.send("INSERT INTO gate_operations VALUES (1,'building',NULL);")
        same(coordinator.query("SELECT phase FROM gate_operations WHERE operation=1;"), "building")
        coordinator.send(f"CREATE DATABASE {first} TEMPLATE template0;")
        first_oid = coordinator.query(oid_query.format(first) + ";")
        require(first_oid.isdecimal(), "first transient was not created")
        coordinator.send(f"UPDATE gate_operations SET oid={first_oid} WHERE operation=1;")
        same(coordinator.query("SELECT phase FROM gate_operations WHERE operation=1;"), "building")
        pg_value(target, model, first)

        with Client(target, target.psql_args(first)) as barrier, ThreadPoolExecutor(max_workers=3) as pool:
            barrier.send("BEGIN; LOCK TABLE gate_data IN ACCESS EXCLUSIVE MODE;")
            same(barrier.query("SELECT 1;"), "1")
            restore = pool.submit(
                target.podman, "exec", "-i", "-e", "PGAPPNAME=dl077-image-worker",
                target.container("postgres"), "pg_restore", "-U", "postgres",
                "--data-only", "--exit-on-error", "-d", first,
                stdin=archive, show_input=False, timeout=120,
            )
            until(lambda: pg_value(target, f"""
                SELECT count(*) FROM pg_stat_activity WHERE datname='{first}'
                AND application_name='dl077-image-worker' AND state='active'
                AND wait_event_type='Lock';
            """) == "1")
            kill_managed_client(target, target.container("postgres"), "coordinator")

            def reconcile():
                with Client(target, target.psql_args("megasamples")) as session:
                    until(lambda: session.query(lock + ";") == "t")
                    same(session.query("SELECT phase FROM gate_operations WHERE operation=1;"), "building")
                    session.send("UPDATE gate_operations SET phase='rolled-back' WHERE operation=1;")
                    same(session.query("SELECT phase FROM gate_operations WHERE operation=1;"), "rolled-back")

            def try_admit():
                with Client(target, target.psql_args("megasamples")) as session:
                    until(lambda: session.query(lock + ";") == "t")
                    unsettled = session.query("SELECT count(*) FROM gate_operations WHERE phase='building';")
                    if unsettled != "0":
                        same(session.query("SELECT pg_advisory_unlock(260077);"), "t")
                        return False
                    session.send(f"CREATE DATABASE {second} TEMPLATE template0;")
                    return bool(session.query(oid_query.format(second) + ";"))

            first_try = pool.submit(try_admit)
            reconciliation = pool.submit(reconcile)
            reconciliation.result(timeout=25)
            if not first_try.result(timeout=25):
                require(try_admit(), "second admission did not create a separate transient")
            barrier.send("COMMIT;")
            checked(restore.result(timeout=120))
    same(pg_value(target, digest, working), expected)
    same(pg_value(target, digest, first), baked)
    same(pg_value(target, oid_query.format(first)), first_oid)
    other_oid = pg_value(target, oid_query.format(second))
    require(other_oid.isdecimal() and other_oid != first_oid, "second transient reused the first OID")

    checked(target.podman(
        "exec", "-i", target.container("postgres"), "pg_restore", "-U", "postgres",
        "--clean", "--if-exists", "--exit-on-error", "-d", working, stdin=archive, show_input=False,
    ))
    same(pg_value(target, digest, working), baked)
    require(baked != expected, "restoring into the working database did not change its checksum")


def lock_statement(name):
    return f"SELECT GET_LOCK('{name}',0)"


def mysql_worker_second_statement(db):
    return f"""
        SELECT IF(EXISTS(SELECT 1 FROM megasamples.gate_operations
                         WHERE target='{db}' AND epoch=1),
                  1, JSON_EXTRACT('invalid epoch', '$'))
    """.strip()


def mysql_operation_fixture(target):
    mysql_value(target, """
        CREATE TABLE megasamples.gate_operations (
            target varchar(48) PRIMARY KEY, phase varchar(30), epoch int
        );
        CREATE USER 'gate_reset_writer'@'localhost';
    """)


def mysql_scenario(target, name, interval, fault):
    mysql_value(target, f"""
        CREATE DATABASE {name};
        CREATE TABLE {name}.gate_data (id int PRIMARY KEY, payload varchar(40));
        INSERT INTO {name}.gate_data VALUES (1,'working');
        GRANT SELECT, UPDATE ON {name}.* TO 'gate_reset_writer'@'localhost';
    """)
    coordinator_lock, worker_lock = (f"{name}-{role}" for role in ("coordinator", "worker"))
    fenced = mysql_worker_second_statement(name)
    dump = f"""
        DROP DATABASE {name};
        CREATE DATABASE {name};
        CREATE TABLE {name}.gate_data (id int PRIMARY KEY, payload varchar(40));
        INSERT INTO {name}.gate_data VALUES (1,'image');
    """
    phase = f"SELECT phase FROM megasamples.gate_operations WHERE target='{name}'"

    with ExitStack() as stack:
        coordinator = stack.enter_context(managed_client(target, target.mysql_args(), "coordinator"))
        worker = stack.enter_context(managed_client(target, target.mysql_args(), "worker"))
        same(coordinator.query(lock_statement(coordinator_lock) + ";"), "1")
        worker_connection = worker.query("SELECT CONNECTION_ID();")
        require(worker_connection.isdecimal(), "worker session identifier missing")
        coordinator.send(f"INSERT INTO megasamples.gate_operations VALUES ('{name}','started',1);")
        expected_phase = "started"
        same(coordinator.query(phase + ";"), expected_phase)
        if interval >= 2:
            coordinator.send(f"REVOKE UPDATE ON {name}.* FROM 'gate_reset_writer'@'localhost';")
            coordinator.send(f"UPDATE megasamples.gate_operations SET phase='excluding' WHERE target='{name}';")
            expected_phase = "excluding"
        if interval >= 3:
            coordinator.send(f"UPDATE megasamples.gate_operations SET phase='loading' WHERE target='{name}';")
            same(coordinator.query(phase + ";"), "loading")
            expected_phase = "loading"
            same(worker.query(lock_statement(worker_lock) + ";"), "1")
            same(worker.query(fenced + ";"), "1")
            if interval == 3:
                worker.send(dump.rsplit("INSERT", 1)[0])
                worker.send(f"INSERT INTO {name}.gate_data SELECT 1,'image' WHERE SLEEP(30)=0;")
                until(lambda: mysql_value(target, f"""
                    SELECT count(*) FROM information_schema.processlist
                    WHERE id={worker_connection}
                      AND info LIKE 'INSERT INTO {name}.gate_data%SLEEP(30)%'
                """) == "1")
            else:
                worker.send(dump)
                same(worker.query(f"SELECT payload FROM {name}.gate_data WHERE id=1;"), "image")
                same(worker.query(f"SELECT RELEASE_LOCK('{worker_lock}');"), "1")
        if interval == 5:
            coordinator.send(f"UPDATE megasamples.gate_operations SET phase='loaded' WHERE target='{name}';")
            expected_phase = "loaded"
        same(coordinator.query(phase + ";"), expected_phase)

        print(f"interval {interval}, fault {fault}", flush=True)
        container = target.container("mysql")
        if fault == "restart":
            target.restart("mysql", lambda: target.mysql("SELECT 1"))
        else:
            kill_managed_client(target, container, fault)
            eliminated = coordinator_lock if fault == "coordinator" else worker_lock
            if fault == "worker" and interval == 3:
                # A server may continue a statement after its client is gone.
                with Client(target, target.mysql_args()) as lookup:
                    until(lambda: lookup.query(f"SELECT IS_FREE_LOCK('{eliminated}');") == "1", seconds=45)
            else:
                until(lambda: mysql_value(target, f"SELECT IS_FREE_LOCK('{eliminated}')") == "1")

        def try_both(session):
            first = session.query(lock_statement(coordinator_lock) + ";")
            if first == "1":
                second = session.query(lock_statement(worker_lock) + ";")
                return second == "1"
            same(first, "0")
            return False

        other_live = fault == "worker" or (fault == "coordinator" and interval == 3)
        with Client(target, target.mysql_args()) as admission:
            same(try_both(admission), not other_live)
            if not other_live:
                same(admission.query(phase + ";"), expected_phase)
                require(expected_phase not in ("done", "failed", "rolled-back"), "expected unsettled row")
        with Client(target, target.mysql_args()) as reconciliation:
            same(try_both(reconciliation), not other_live)
            if not other_live:
                reconciliation.send(f"UPDATE megasamples.gate_operations SET epoch=2 WHERE target='{name}';")
                same(reconciliation.query(f"SELECT epoch FROM megasamples.gate_operations WHERE target='{name}';"), "2")
        if other_live:
            return

    before = checksum(target, name)
    lock = lock_statement(worker_lock) + ";\n"
    denied(target.mysql(lock + fenced + ";\n" + dump), "3141")
    same(checksum(target, name), before)
    mysql_value(target, lock + dump)
    same(mysql_value(target, f"SELECT payload FROM {name}.gate_data WHERE id=1"), "image")


def mysql_workers_exclude(target):
    mysql_operation_fixture(target)
    for interval in range(1, 6):
        for fault in ("coordinator", "worker", "restart"):
            mysql_scenario(target, f"gate_reset_{interval}_{fault}", interval, fault)


CASES = {"G-26p": pg_worker_isolated, "G-26m": mysql_workers_exclude}
