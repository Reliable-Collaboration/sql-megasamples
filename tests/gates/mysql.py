"""MySQL gate cases using SQL and stock clients."""

import re
from concurrent.futures import ThreadPoolExecutor

from clients import Client, kill_managed_client, managed_client, until
from native import ControlNotShown, checked, denied, require, same

SOURCE = "gate_work_start"
DEST = "gate_copy_x"
COPY_USER = "gate_owner"
DDL_GRANTS = (
    "SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX, REFERENCES, "
    "CREATE VIEW, SHOW VIEW, CREATE ROUTINE, ALTER ROUTINE, EXECUTE, TRIGGER, EVENT"
)
SCHEMA_DENIALS = {1044, 1142, 1143, 1227}


def value(target, sql, database=None, user="root", key="mysql"):
    return checked(target.mysql(sql, database, user, key))


def access_refused(result, codes=SCHEMA_DENIALS):
    match = re.search(r"ERROR (\d+) \(", result.stderr)
    require(result.returncode and match and int(match[1]) in codes,
            "the statement did not report the expected privilege refusal")


def table(target, database, *, key="mysql"):
    value(target, f"""
        CREATE DATABASE `{database}`;
        CREATE TABLE `{database}`.gate_data (id int PRIMARY KEY, payload varchar(40));
        INSERT INTO `{database}`.gate_data VALUES (1, 'one'), (2, 'two');
    """, key=key)


def read_only_error(result):
    require(result.returncode and re.search(r"ERROR .*read.only", result.stderr, re.I),
            "the statement did not report schema read-only mode")


def read_only_writes(target):
    table(target, SOURCE)
    value(target, f"""
        CREATE USER '{COPY_USER}'@'localhost';
        GRANT UPDATE, ALTER ON {SOURCE}.* TO '{COPY_USER}'@'localhost';
        ALTER DATABASE {SOURCE} READ ONLY = 1;
    """)
    statements = (f"UPDATE {SOURCE}.gate_data SET payload='changed'",
                  f"ALTER TABLE {SOURCE}.gate_data ADD COLUMN extra int")
    for user in (COPY_USER, "admin", "root"):
        for statement in statements:
            read_only_error(target.mysql(statement, user=user))
    value(target, f"ALTER DATABASE {SOURCE} READ ONLY = 0", user="admin")
    for statement in statements:
        value(target, statement, user="admin")


def concurrent_read_only_copies(target):
    table(target, SOURCE)
    value(target, f"ALTER DATABASE {SOURCE} READ ONLY = 1")
    copies = ("gate_copy_a", "gate_copy_b")
    for copy in copies:
        value(target, f"CREATE DATABASE {copy}; CREATE TABLE {copy}.gate_data LIKE {SOURCE}.gate_data")
    read_only_error(target.mysql(f"INSERT INTO {SOURCE}.gate_data VALUES (3, 'control')"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(value, target, f"INSERT INTO {copy}.gate_data SELECT * FROM {SOURCE}.gate_data")
            for copy in copies
        ]
        for job in jobs:
            job.result()
    expected = checksum(target, SOURCE)
    for copy in copies:
        same(checksum(target, copy), expected)


def checksum(target, database, *, key="mysql"):
    result = value(target, f"CHECKSUM TABLE `{database}`.gate_data EXTENDED", key=key)
    digest = result.split("\t")[-1]
    require(digest.isdecimal(), "table checksum was unavailable")
    return digest


def change_read_only(target):
    table(target, SOURCE)
    value(target, f"""
        CREATE USER '{COPY_USER}'@'localhost';
        GRANT SELECT ON {SOURCE}.* TO '{COPY_USER}'@'localhost';
        ALTER DATABASE {SOURCE} READ ONLY = 1;
    """)
    access_refused(target.mysql(f"ALTER DATABASE {SOURCE} READ ONLY = 0", user=COPY_USER))
    value(target, f"ALTER DATABASE {SOURCE} READ ONLY = 0", user="admin")
    value(target, f"UPDATE {SOURCE}.gate_data SET payload='open'", user="admin")


def escaped_underscore(target):
    for name in ("a_b", "axb"):
        table(target, name)
    value(target, r"""
        CREATE USER 'gate_reader'@'localhost';
        GRANT SELECT ON `a\_b`.* TO 'gate_reader'@'localhost';
    """)
    same(value(target, "SELECT count(*) FROM a_b.gate_data", user="gate_reader"), "2")
    access_refused(target.mysql("SELECT count(*) FROM axb.gate_data", user="gate_reader"))
    value(target, r"""
        REVOKE SELECT ON `a\_b`.* FROM 'gate_reader'@'localhost';
        GRANT SELECT ON `a_b`.* TO 'gate_reader'@'localhost';
    """)
    for name in ("a_b", "axb"):
        same(value(target, f"SELECT count(*) FROM {name}.gate_data", user="gate_reader"), "2")


def grant_namespace(target, account, prefix, key="mysql"):
    value(target, f"""
        CREATE USER '{account}'@'localhost';
        GRANT {DDL_GRANTS} ON `{prefix}\\_%`.* TO '{account}'@'localhost';
    """, key=key)


def scoped_owner(target):
    grant_namespace(target, COPY_USER, "copy")
    value(target, "CREATE USER 'gate_reader'@'localhost'")
    value(target, """
        CREATE DATABASE copy_x;
        CREATE TABLE copy_x.gate_data (id int);
        INSERT INTO copy_x.gate_data VALUES (1);
    """, user=COPY_USER)
    same(value(target, "SELECT id FROM copy_x.gate_data", user=COPY_USER), "1")
    access_refused(target.mysql("GRANT SELECT ON copy_x.* TO 'gate_reader'@'localhost'", user=COPY_USER))
    value(target, "DROP DATABASE copy_x", user=COPY_USER)

    for name in ("copyx", "gate_working", "gate_work_start", "other_x", "megasamples"):
        access_refused(target.mysql(f"CREATE DATABASE {name}", user=COPY_USER))
        if name != "megasamples":
            table(target, name)
        for statement in (f"ALTER DATABASE {name} CHARACTER SET latin1", f"DROP DATABASE {name}"):
            access_refused(target.mysql(statement, user=COPY_USER))
    value(target, r"GRANT SELECT ON `gate\_work\_start`.* TO 'gate_owner'@'localhost'")
    same(value(target, "SELECT count(*) FROM gate_work_start.gate_data", user=COPY_USER), "2")


def demo_grants(target):
    fixture_schemas = ("gate_working", "gate_work_start", "fa_x", "fb_x", "fax")
    for schema in fixture_schemas:
        table(target, schema)
    tables = ("gate_working.gate_data", "fa_x.gate_data", "fb_x.gate_data",
              "fax.gate_data", "mysql.user", "gate_work_start.gate_data")
    for name in tables:
        require(value(target, f"SELECT count(*) FROM {name}", user="demo").isdecimal(),
                "control without the narrowing did not read the expected table")
    value(target, r"""
        REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'demo'@'%';
        GRANT SELECT, SHOW VIEW ON `gate\_working`.* TO 'demo'@'%';
        GRANT SELECT ON megasamples.datasets TO 'demo'@'%';
        GRANT SELECT, SHOW VIEW ON `fa\_%`.* TO 'demo'@'%';
    """)
    account = "demo"
    for schema in ("gate_working", "fa_x"):
        same(value(target, f"SELECT count(*) FROM {schema}.gate_data", user=account), "2")
    for table_name in ("fb_x.gate_data", "fax.gate_data", "mysql.user", "gate_work_start.gate_data"):
        access_refused(target.mysql(f"SELECT count(*) FROM {table_name}", user=account))


def create_sql(target, db, kind, name, column, key):
    fields = value(target, f"SHOW CREATE {kind} {name}", db, key=key).split("\t")
    require(len(fields) > column, f"SHOW CREATE {kind} did not return a definition")
    return re.sub(r"\bDEFINER\s*=\s*`[^`]+`@`[^`]+`\s*", "", fields[column], flags=re.I)


def replay_into_copy(target):
    definitions = (
        ("TABLE", "gate_data", 1), ("TABLE", "gate_child", 1), ("TABLE", "gate_audit", 1),
        ("PROCEDURE", "gate_routine", 2), ("VIEW", "gate_view", 1),
        ("TRIGGER", "gate_trigger", 2), ("EVENT", "gate_event", 3),
    )
    for key, binlog in (("mysql", "1"), ("mysql_no_binlog", "0")):
        same(value(target, "SELECT @@global.log_bin", key=key), binlog)
        grant_namespace(target, COPY_USER, "gate_copy", key)
        value(target, f"""
            CREATE DATABASE {SOURCE};
            GRANT SELECT ON `gate\\_work\\_start`.* TO '{COPY_USER}'@'localhost';
            USE {SOURCE};
            CREATE TABLE gate_data (
                id int PRIMARY KEY, payload varchar(40),
                generated varchar(44) AS (concat(payload,'-gen')) STORED,
                FULLTEXT (payload)
            );
            CREATE TABLE gate_child (
                id int PRIMARY KEY, FOREIGN KEY (id) REFERENCES gate_data(id)
            );
            CREATE TABLE gate_audit (payload varchar(40));
            CREATE PROCEDURE gate_routine() SELECT payload FROM gate_data WHERE id=1;
            CREATE VIEW gate_view AS SELECT payload FROM gate_data WHERE id=1;
            CREATE TRIGGER gate_trigger AFTER INSERT ON gate_data FOR EACH ROW
                INSERT INTO gate_audit SELECT payload FROM gate_data WHERE id=NEW.id;
            CREATE EVENT gate_event ON SCHEDULE EVERY 1 DAY DISABLE
                DO INSERT INTO gate_audit SELECT payload FROM gate_data WHERE id=1;
            INSERT INTO gate_data (id,payload) VALUES (1,'initial');
            INSERT INTO gate_child VALUES (1);
            DELETE FROM gate_audit;
        """, key=key)
        replay = {
            name: create_sql(target, SOURCE, kind, name, column, key)
            for kind, name, column in definitions
        }
        value(target, f"""
            CREATE DATABASE {DEST};
            USE {DEST};
            SET FOREIGN_KEY_CHECKS=0;
            {replay['gate_data']};
            {replay['gate_child']};
            {replay['gate_audit']};
            INSERT INTO gate_data(id,payload) SELECT id,payload FROM {SOURCE}.gate_data;
            INSERT INTO gate_child SELECT * FROM {SOURCE}.gate_child;
            SET FOREIGN_KEY_CHECKS=1;
            {replay['gate_routine']};
            {replay['gate_view']};
            {replay['gate_trigger']};
            {replay['gate_event']};
        """, user=COPY_USER, key=key)
        same(checksum(target, DEST, key=key), checksum(target, SOURCE, key=key))
        value(target, f"UPDATE {SOURCE}.gate_data SET payload='source-only' WHERE id=1", key=key)
        for sql in ("SELECT payload FROM gate_view", "CALL gate_routine()"):
            same(value(target, sql, SOURCE, key=key), "source-only")
            same(value(target, sql, DEST, COPY_USER, key), "initial")
        value(target, "INSERT INTO gate_data(id,payload) VALUES (2,'copy-only')", DEST, COPY_USER, key)
        same(value(target, "SELECT payload FROM gate_audit", DEST, key=key), "copy-only")
        same(value(target, "SELECT COUNT(*) FROM gate_audit", SOURCE, key=key), "0")
        same(value(target, "SELECT generated FROM gate_data WHERE id=1", DEST, key=key), "initial-gen")
        same(value(target, """
            SELECT COUNT(*) FROM information_schema.statistics
            WHERE table_schema=DATABASE() AND table_name='gate_data' AND index_type='FULLTEXT'
        """, DEST, key=key), "1")
        denied(target.mysql("INSERT INTO gate_child VALUES (999)", DEST, COPY_USER, key), "1452")
        same(value(target, """
            SELECT STATUS FROM information_schema.events
            WHERE event_schema=DATABASE() AND event_name='gate_event'
        """, DEST, key=key), "DISABLED")


def named_lock_held_after_client_dies(target):
    sql = "SELECT GET_LOCK('dl077-g15a',0)"
    same(value(target, sql), "1")
    with managed_client(target, target.mysql_args()) as worker:
        same(worker.query(sql + ";"), "1")
        worker.send("SELECT SLEEP(12) AS dl077_long_query;")
        until(lambda: value(target, """
            SELECT COUNT(*) FROM information_schema.processlist
            WHERE info = 'SELECT SLEEP(12) AS dl077_long_query'
        """) == "1")
        kill_managed_client(target, target.container("mysql"))
        same(value(target, sql), "0")
        until(lambda: value(target, sql) == "1")


def drop_waits_for_transaction(target):
    table(target, "gate_drop")
    before = checksum(target, "gate_drop")
    with Client(target, target.mysql_args("gate_drop")) as client:
        client.send("START TRANSACTION;")
        same(client.query("SELECT count(*) FROM gate_data;"), "2")
        denied(target.mysql("SET SESSION lock_wait_timeout=2; DROP DATABASE gate_drop"), "1205")
        same(checksum(target, "gate_drop"), before)
    value(target, "DROP DATABASE gate_drop")


def marker_lifetime(target):
    event = "megasamples_copy_1234567890abcdef1234567890abcdef"
    observe = f"""
        SELECT STATUS FROM information_schema.events
        WHERE event_schema='copy_x' AND event_name='{event}';
    """
    create = f"""
        CREATE DATABASE copy_x;
        CREATE EVENT copy_x.{event} ON SCHEDULE EVERY 1 DAY DISABLE DO SELECT 1;
        CREATE TABLE copy_x.gate_data (id int PRIMARY KEY, payload varchar(40));
        INSERT INTO copy_x.gate_data VALUES (1,'one'),(2,'two');
    """
    for key, binlog in (("mysql", "1"), ("mysql_no_binlog", "0")):
        same(value(target, "SELECT @@global.log_bin", key=key), binlog)
        value(target, "SET GLOBAL event_scheduler = OFF", key=key)
        grant_namespace(target, COPY_USER, "copy", key)
        value(target, create, user=COPY_USER, key=key)
        same(value(target, observe, key=key), "DISABLED")
        target.restart(key, lambda: target.mysql("SELECT 1", key=key))
        same(value(target, observe, key=key), "DISABLED")
        before = checksum(target, "copy_x", key=key)
        within_second = value(target, """
            SET @second=UNIX_TIMESTAMP();
            DROP DATABASE copy_x;
            CREATE DATABASE copy_x;
            CREATE TABLE copy_x.gate_data (id int PRIMARY KEY, payload varchar(40));
            INSERT INTO copy_x.gate_data VALUES (1,'one'),(2,'two');
            SELECT @second = UNIX_TIMESTAMP();
        """, user=COPY_USER, key=key)
        if within_second != "1":
            raise ControlNotShown("the replacement did not finish within the same second")
        same(value(target, observe, key=key), "")
        same(checksum(target, "copy_x", key=key), before)


def writer_fixture(target):
    table(target, "gate_writer")
    value(target, r"""
        CREATE USER 'gate_writer'@'localhost';
        GRANT SELECT ON `gate\_writer`.* TO 'gate_writer'@'localhost';
        GRANT UPDATE ON `gate\_writer`.* TO 'gate_writer'@'localhost';
    """)


REVOKE_WRITER = r"REVOKE UPDATE ON `gate\_writer`.* FROM 'gate_writer'@'localhost'"
WRITE_ROW = "UPDATE gate_writer.gate_data SET payload='writer' WHERE id=1"


def revoke_and_end_sessions(target):
    writer_fixture(target)
    with Client(target, target.mysql_args("gate_writer", "gate_writer")) as writer:
        session = writer.query("SELECT CONNECTION_ID();")
        require(session.isdecimal(), "writer session identifier missing")
        writer.send(WRITE_ROW + ";")
        same(writer.query("SELECT payload FROM gate_data WHERE id=1;"), "writer")
        value(target, REVOKE_WRITER)
        writer.send(WRITE_ROW + "; SELECT payload FROM gate_data WHERE id=1;")
        after = writer.line()
        print(f"Existing connection after revoke: {after}")
        value(target, "KILL CONNECTION " + session)
    access_refused(target.mysql(WRITE_ROW, user="gate_writer"))


def revoke_survives_restart(target):
    writer_fixture(target)
    value(target, WRITE_ROW, user="gate_writer")
    value(target, REVOKE_WRITER)
    target.restart("mysql", lambda: target.mysql("SELECT 1"))
    access_refused(target.mysql(WRITE_ROW, user="gate_writer"))


CASES = {
    "G-10a": read_only_writes,
    "G-10b": concurrent_read_only_copies,
    "G-10c": change_read_only,
    "G-11a": escaped_underscore,
    "G-11b": scoped_owner,
    "G-11c": demo_grants,
    "G-13": replay_into_copy,
    "G-15a": named_lock_held_after_client_dies,
    "G-15b": drop_waits_for_transaction,
    "G-24m": marker_lifetime,
    "G-27a": revoke_and_end_sessions,
    "G-27b": revoke_survives_restart,
}


def locked_means_no_login(target):
    sql = "SELECT CURRENT_USER()"
    routes = (
        ("admin", "network", "admin@%"), ("admin", "published", "admin@%"),
        ("root", "network", "root@%"), ("root", "published", "root@%"),
        ("root", "socket", "root@localhost"),
    )
    for user, route, account in routes:
        result = target.mysql(sql) if route == "socket" else target.mysql_network(sql, user, route)
        same(checked(result), account)
    value(target, "ALTER USER 'admin'@'%', 'root'@'%', 'root'@'localhost' ACCOUNT LOCK")
    for user, route, _ in routes:
        result = target.mysql(sql) if route == "socket" else target.mysql_network(sql, user, route)
        denied(result, "3118")
    target.restart("mysql", lambda: target.mysql_network(sql, "demo", "network"))
    same(checked(target.mysql_network(sql, "demo", "network")), "demo@%")
    for user, route, _ in routes:
        result = target.mysql(sql) if route == "socket" else target.mysql_network(sql, user, route)
        denied(result, "3118")


CASES["G-35m"] = locked_means_no_login
