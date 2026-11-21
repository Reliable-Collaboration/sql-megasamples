"""PostgreSQL copies. The session that fences DDL also writes the ledger."""

from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import math
import os
import time

from megasamples.copying import CopyError, prefix_is_valid
from megasamples.copy_server import COPY_TAG, SERVICE_TAG, ServerCopies

TEMPLATE_TAG = "megasamples-template/1 "


class PostgresCopies(ServerCopies):
    engine = "postgres"

    def __init__(self, connection, args, errors):
        self.connection = connection
        self.args = args
        self.errors = errors
        self.warnings = []
        self.port = args.port or 5432
        try:
            service = self.one("SELECT tag, volume FROM copy_service WHERE singleton")
            self.version = self.one("SHOW server_version")[0]
            self.owner = self.one("SELECT current_user")[0]
            self.namespaces = self.all("SELECT prefix, max_copies FROM copy_namespaces WHERE owner=current_user")
        except errors.Error as failure:
            if self.connection_lost(failure):
                # Only reads have run: nothing changed, and the caller keeps the identity it named.
                raise CopyError(3, "connection", "server connection closed while reading copy metadata",
                                getattr(args, "identity", None)) from None
            raise CopyError(5, "format-unknown", "service copy metadata cannot be read") from None
        if service is None or service[0] != SERVICE_TAG or not service[1]:
            raise CopyError(5, "unidentified-volume", "service copy volume is unqualified")
        self.volume = service[1]
        if hasattr(args, "prefix"):
            self.prefix = args.prefix
        else:
            self.prefix = next((prefix for prefix, _limit in self.namespaces
                                if args.name.startswith(prefix + "_")), None)
        limits = dict(self.namespaces)
        if not prefix_is_valid(self.prefix) or self.prefix not in limits:
            raise CopyError(5, "namespace", "account does not own this namespace")
        self.limit = limits[self.prefix]
        self.ledger = 'public."copy_ledger_' + self.prefix + '"'

    def all(self, sql, params=()):
        return self.connection.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.connection.execute(sql, params).fetchone()

    def connection_lost(self, error):
        return self.connection.closed or self.connection.broken or (error.sqlstate or "").startswith("08")

    @contextmanager
    def lock(self, name, wait=0):
        lock_id = int.from_bytes(hashlib.sha256(("megasamples/copy/" + name).encode()).digest()[:8],
                                 "big", signed=True)
        deadline = time.monotonic() + wait
        acquired = self.one("SELECT pg_catalog.pg_try_advisory_lock(%s::bigint)", (lock_id,))[0]
        while not acquired and time.monotonic() < deadline:
            time.sleep(min(0.1, max(0, deadline - time.monotonic())))
            acquired = self.one("SELECT pg_catalog.pg_try_advisory_lock(%s::bigint)", (lock_id,))[0]
        try:
            yield acquired
        finally:
            if acquired and not self.connection.closed and not self.connection.broken:
                self.one("SELECT pg_catalog.pg_advisory_unlock(%s::bigint)", (lock_id,))

    def change(self, row, **changes):
        self.wrote = True
        changed = {**row, **changes, "revision": row["revision"] + 1}
        self.connection.execute(f"UPDATE {self.ledger} SET record=%s::jsonb WHERE name=%s",
                                (json.dumps(changed), row["name"]))
        return changed

    def object(self, name):
        return self.one("""
            SELECT oid, pg_get_userbyid(datdba), shobj_description(oid, 'pg_database'),
                   datallowconn, datistemplate
            FROM pg_catalog.pg_database WHERE datname=%s
        """, (name,))

    def names(self):
        rows = self.all(f"""
            SELECT name FROM {self.ledger}
            UNION SELECT datname::text FROM pg_catalog.pg_database WHERE starts_with(datname::text,%s)
            ORDER BY 1
        """, (self.prefix + "_",))
        # Every object under the prefix is listed; one that is not of the copy form is unmanaged.
        return [name for (name,) in rows]

    def lease_end(self, seconds):
        return (self.one("SELECT statement_timestamp()")[0] + timedelta(seconds=seconds)).isoformat()

    def expired(self, row):
        return self.one("SELECT statement_timestamp() >= %s::timestamptz", (row["lease_until"],))[0]

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
        if obj[:3] != (row.get("proof", {}).get("oid"), self.owner, COPY_TAG + " " + row["identity"]):
            return "inconsistent"
        return phase

    def source(self):
        database = self.args.name
        source = self.object(database + "_start")
        if source and source[2] and source[2].startswith("megasamples-template/") \
                and not source[2].startswith(TEMPLATE_TAG):
            raise CopyError(5, "format-unknown", "template registration has an unsupported version")
        if not source or source[2] is None or not source[2].startswith(TEMPLATE_TAG) or source[3] or not source[4]:
            raise CopyError(4, "no-template", "this database has no registered template")
        try:
            data = json.loads(source[2][len(TEMPLATE_TAG):])
            if data["database"] != database or data["strategy"] not in ("wal_log", "file_copy"):
                raise ValueError("invalid template")
            return data["strategy"], {"build": data["build"], "digest": data["digest"]}
        except (TypeError, KeyError, ValueError):
            raise CopyError(5, "format-unknown", "template registration cannot be read") from None

    def reservation_counts(self, label):
        return self.one(f"SELECT count(*) FILTER (WHERE record->>'label'=%s), count(*) FROM {self.ledger}",
                        (label,))

    def insert(self, row):
        self.wrote = True
        self.connection.execute(f"INSERT INTO {self.ledger} (name, record) VALUES (%s,%s::jsonb)",
                                (row["name"], json.dumps(row)))

    def create_reserved(self, row, strategy):
        name, identity = row["name"], row["identity"]
        row = self.change(row, phase="issuing")
        self.connection.execute(f'CREATE DATABASE "{name}" TEMPLATE "{row["database"]}_start" STRATEGY {strategy}')
        secure = self.one("""
            SELECT oid, pg_get_userbyid(datdba), datallowconn,
                NOT EXISTS (
                    SELECT FROM aclexplode(coalesce(datacl, acldefault('d',datdba)))
                    WHERE grantee=0 AND privilege_type IN ('CONNECT','TEMPORARY')
                )
            FROM pg_catalog.pg_database WHERE datname=%s
        """, (name,))
        if not secure or secure[1:] != (self.owner, True, True):
            raise CopyError(8, "create-unsettled", "database closure could not be confirmed", identity)
        self.connection.execute(f'COMMENT ON DATABASE "{name}" IS \'{COPY_TAG} {identity}\'')
        row = self.change(row, phase="created", proof={"oid": secure[0]})
        self.connection.execute(f'GRANT CONNECT ON DATABASE "{name}" TO "megasamples_copy_{self.prefix}_read"')
        return self.result(name, self.change(row, phase="ready"), "ready")

    def remove(self, row, state, deadline):
        name, identity = row["name"], row["identity"]
        try:
            if state in ("ready", "dropping"):
                if self.state(name, row) != state:
                    raise CopyError(5, "inconsistent", "database identity changed", identity)
                if state != "dropping":
                    row = self.change(row, phase="dropping")
                while True:
                    if self.state(name, row) != "dropping":
                        raise CopyError(8, "inconsistent", "database identity changed during drop", identity)
                    try:
                        self.connection.execute(f'DROP DATABASE "{name}"')
                    except self.errors.Error as error:
                        if error.sqlstate != "55006" or self.state(name, row) != "dropping":
                            raise
                        if time.monotonic() >= deadline:
                            if state == "ready":
                                self.change(row, phase="ready")
                            raise CopyError(6, "busy", "database is in use", identity) from None
                        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
                    else:
                        break
            self.wrote = True
            self.connection.execute(f"DELETE FROM {self.ledger} WHERE name=%s", (name,))
        except self.errors.Error:
            raise CopyError(8, "drop-unsettled", "database removal did not finish", identity) from None
        return self.result(name, row, "gone")


@contextmanager
def open_postgres(args, password):
    try:
        import psycopg
    except ImportError:
        # Psycopg's pure distribution loads the system's libpq; without it no engine is contacted.
        raise CopyError(3, "client-library",
                        "the PostgreSQL client needs libpq, which psycopg could not load") from None

    ambient = {key: os.environ.pop(key) for key in list(os.environ) if key.startswith("PG")}
    try:
        try:
            connection = psycopg.connect(host=args.host, port=args.port or 5432,
                                         user=args.user, password=password, dbname="megasamples",
                                         connect_timeout=math.ceil(args.connect_timeout or 10),
                                         passfile=os.devnull, autocommit=True)
        except psycopg.Error:
            raise CopyError(3, "connection", "server connection or sign-in was refused") from None
    finally:
        os.environ.update(ambient)
    with connection:
        yield PostgresCopies(connection, args, psycopg)
