"""MySQL session locks, marker proofs and logical copy replay."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import time

from megasamples.copying import CopyError, prefix_is_valid
from megasamples.copy_server import SERVICE_TAG, ServerCopies
from megasamples.mysql_templates import create_schema, objects_are_current, qualify, quote, replay


class MySQLCopies(ServerCopies):
    engine = "mysql"
    default_drop_wait = 5

    def __init__(self, connection, args, errors):
        self.connection = connection
        self.args = args
        self.errors = errors
        self.warnings = []
        self.port = args.port or 3306
        try:
            service = self.one("SELECT tag FROM megasamples.copy_service")
            self.version, self.volume, self.owner = self.one(
                "SELECT VERSION(), @@server_uuid, SUBSTRING_INDEX(CURRENT_USER(),'@',1)")
            limits = dict(self.all("SELECT prefix,max_copies FROM megasamples.copy_namespaces WHERE owner=%s",
                                   (self.owner,)))
        except errors.Error as failure:
            if self.connection_lost(failure):
                # Only reads have run: nothing changed, and the caller keeps the identity it named.
                raise CopyError(3, "connection", "server connection closed while reading copy metadata",
                                getattr(args, "identity", None)) from None
            raise CopyError(5, "format-unknown", "service copy metadata cannot be read") from None
        if service != (SERVICE_TAG,) or not self.volume:
            raise CopyError(5, "unidentified-volume", "service copy volume is unqualified")
        self.prefix = (args.prefix if hasattr(args, "prefix") else
                       next((prefix for prefix in limits if args.name.startswith(prefix + "_")), None))
        if not prefix_is_valid(self.prefix) or self.prefix not in limits:
            raise CopyError(5, "namespace", "account does not own this namespace")
        self.limit = limits[self.prefix]
        self.ledger = qualify("megasamples", "copy_ledger_" + self.prefix)

    def execute(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params or None)

    def all(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params or None)
            return cursor.fetchall()

    def one(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params or None)
            return cursor.fetchone()

    def connection_lost(self, error):
        return not self.connection.open or error.args[:1] in ((2006,), (2013,), (2055,))

    @contextmanager
    def lock(self, name, wait=0):
        key = "megasamples:" + hashlib.sha256(name.encode()).hexdigest()[:48]
        acquired = self.one("SELECT GET_LOCK(%s,%s)", (key, wait))[0] == 1
        try:
            yield acquired
        finally:
            if acquired and self.connection.open:
                self.one("SELECT RELEASE_LOCK(%s)", (key,))

    def lease_end(self, seconds):
        timestamp = self.one("SELECT UTC_TIMESTAMP(6)")[0].replace(tzinfo=timezone.utc)
        return (timestamp + timedelta(seconds=seconds)).isoformat()

    def expired(self, row):
        timestamp = self.one("SELECT UTC_TIMESTAMP(6)")[0].replace(tzinfo=timezone.utc)
        return timestamp >= datetime.fromisoformat(row["lease_until"])

    def reservation_counts(self, label):
        return self.one(f"SELECT count(CASE WHEN JSON_UNQUOTE(JSON_EXTRACT(record,'$.label'))=%s "
                        f"THEN 1 END), count(*) FROM {self.ledger}", (label,))

    def insert(self, row):
        self.wrote = True
        self.execute(f"INSERT INTO {self.ledger} (name,record) VALUES (%s,%s)",
                     (row["name"], json.dumps(row)))

    def change(self, row, **changes):
        self.wrote = True
        changed = {**row, **changes, "revision": row["revision"] + 1}
        self.execute(f"UPDATE {self.ledger} SET record=%s WHERE name=%s",
                     (json.dumps(changed), row["name"]))
        return changed

    def object(self, name):
        return self.one("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))

    def names(self):
        rows = self.all(f"""
            SELECT name FROM {self.ledger}
            UNION SELECT SCHEMA_NAME FROM information_schema.SCHEMATA
                  WHERE LEFT(SCHEMA_NAME,%s)=%s
            ORDER BY 1
        """, (len(self.prefix) + 1, self.prefix + "_"))
        # Every object under the prefix is listed; one that is not of the copy form is unmanaged.
        return [name for (name,) in rows]

    def source(self):
        row = self.one("SELECT reason,detail,metadata FROM megasamples.template_ddl WHERE name=%s",
                       (self.args.name,))
        if row is None:
            raise CopyError(4, "no-template", "this database has no offered template")
        if row[0] in ("no-template", "dependency-group", "too-large", "not-replayable"):
            raise CopyError(4, row[0], row[1])
        try:
            metadata = json.loads(row[2])
            if (metadata["tag"] != "megasamples-template/1" or metadata["database"] != self.args.name
                    or not objects_are_current(metadata["objects"])):
                raise ValueError("invalid template")
            return metadata, {"build": metadata["build"], "digest": metadata["digest"]}
        except (TypeError, KeyError, ValueError):
            raise CopyError(5, "format-unknown", "template registration cannot be read") from None

    def create_reserved(self, row, metadata):
        name, identity = row["name"], row["identity"]
        row = self.change(row, phase="issuing")
        marker = "megasamples_copy_" + identity
        try:
            create_schema(self.execute, name, metadata["charset"], metadata["collation"])
            self.execute(f"CREATE EVENT {qualify(name, marker)} "
                         "ON SCHEDULE AT CURRENT_TIMESTAMP + INTERVAL 1 YEAR "
                         "ON COMPLETION PRESERVE DISABLE DO SELECT 1")
            row = self.change(row, phase="created", proof={"event": marker})
            replay(self.execute, self.all, metadata, row["database"] + "_start", name, remove_definer=True)
            row = self.change(row, phase="ready")
            # Classified as show would: an outside grant that could replace it is not-exclusive.
            return self.result(name, row, self.state(name, row))
        except (self.errors.Error, KeyError, TypeError, ValueError):
            raise CopyError(8, "create-unsettled", "schema copy did not verify", identity) from None

    def other_grants(self, name):
        view = qualify("megasamples", "copy_grants_" + self.prefix)
        return self.all(f"SELECT User, Host, Db, Create_priv, Drop_priv FROM {view} WHERE copy_name=%s",
                        (name,))

    def state(self, name, row):
        obj = self.object(name)
        if row is None:
            return "unmanaged" if obj else "gone"
        phase = row["phase"]
        if phase in ("reserved", "issuing", "created"):
            return "interrupted" if obj or phase == "created" else "stale"
        if phase not in ("ready", "dropping"):
            return "unknown"
        if obj is None:
            return "gone"
        marker = "megasamples_copy_" + row["identity"]
        if row.get("proof") != {"event": marker}:
            return "inconsistent"
        grants = self.other_grants(name)
        for user, host, pattern, create, drop in grants:
            warning = {"code": "hand-made-grant", "name": name, "account": f"{user}@{host}", "pattern": pattern}
            if warning not in self.warnings:
                self.warnings.append(warning)
        if any(create == "Y" or drop == "Y" for _, _, _, create, drop in grants):
            return "not-exclusive"
        if self.one("SELECT STATUS FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s AND EVENT_NAME=%s",
                    (name, marker)) != ("DISABLED",):
            return "inconsistent"
        return phase

    def remove(self, row, state, deadline):
        name, identity = row["name"], row["identity"]
        try:
            if state in ("ready", "dropping"):
                current = self.state(name, row)
                if current != state:
                    raise CopyError(5, current, "schema is kept", identity)
                if state != "dropping":
                    row = self.change(row, phase="dropping")
                seconds = max(1, min(31_536_000, math.ceil(deadline - time.monotonic())))
                self.execute("SET SESSION lock_wait_timeout=%s", (seconds,))
                try:
                    self.execute(f"DROP DATABASE {quote(name)}")
                except self.errors.Error as failure:
                    if failure.args[0] == 1205 and self.state(name, row) == "dropping":
                        if state == "ready":
                            self.change(row, phase="ready")
                        raise CopyError(6, "busy", "schema is locked", identity) from None
                    raise
            self.wrote = True
            self.execute(f"DELETE FROM {self.ledger} WHERE name=%s", (name,))
        except self.errors.Error:
            raise CopyError(8, "drop-unsettled", "schema removal did not finish", identity) from None
        return self.result(name, row, "gone")


@contextmanager
def open_mysql(args, password):
    import pymysql

    try:
        connection = pymysql.connect(host=args.host, port=args.port or 3306, user=args.user,
                                     password=password, database="megasamples", autocommit=True,
                                     connect_timeout=math.ceil(args.connect_timeout or 10),
                                     charset="utf8mb4")
    except pymysql.Error:
        raise CopyError(3, "connection", "server connection or sign-in was refused") from None
    try:
        yield MySQLCopies(connection, args, pymysql)
    finally:
        # A connection the server closed cannot be closed again; that is not the command's outcome.
        if connection.open:
            connection.close()
