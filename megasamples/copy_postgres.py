"""PostgreSQL copies. The session that fences DDL also writes the ledger."""

from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import json
import math
import os
import time
from uuid import uuid4

from megasamples.copying import CopyError, IDENTITY, LABEL, copy_name_is_valid, database_is_valid, prefix_is_valid

COPY_TAG = "megasamples-copy/1"
TEMPLATE_TAG = "megasamples-template/1 "
SERVICE_TAG = "megasamples-service/1"


class PostgresCopies:
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
        except errors.Error:
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

    def load(self, name):
        row = self.one(f"SELECT record FROM {self.ledger} WHERE name=%s", (name,))
        if row is None:
            return None
        record = row[0]
        try:
            if (record["tag"] != COPY_TAG or record["name"] != name
                    or not IDENTITY.fullmatch(record["identity"])
                    or not LABEL.fullmatch(record["label"])
                    or not database_is_valid(record["database"]) or record["prefix"] != self.prefix
                    or name != f"{self.prefix}_{record['database']}_{record['identity'][:12]}"
                    or type(record["revision"]) is not int or record["revision"] < 1
                    or datetime.fromisoformat(record["lease_until"]).tzinfo is None):
                raise ValueError("invalid record")
        except (KeyError, TypeError, ValueError):
            raise CopyError(5, "format-unknown", "copy record cannot be interpreted") from None
        return record

    def change(self, row, **changes):
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
        return [name for (name,) in rows if copy_name_is_valid(name)]

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

    def result(self, name, row, state):
        row = row or {}
        return {"name": name, "identity": row.get("identity"), "engine": "postgres",
                "database": row.get("database"), "prefix": self.prefix, "label": row.get("label"),
                "state": state, "revision": row.get("revision"), "lease_until": row.get("lease_until"),
                "endpoint": {"host": self.args.host, "port": self.port}, "owner": self.owner,
                "template": row.get("template"), "version": self.version, "proof": row.get("proof")}

    def inspect(self, name):
        with self.lock(name) as acquired:
            row = self.load(name)
            return self.result(name, row, self.state(name, row) if acquired else "changing")

    def show(self):
        return self.inspect(self.args.name)

    def list(self):
        rows = [self.inspect(name) for name in self.names()]
        return {"copies": [row for row in rows if self.args.label is None or row["label"] == self.args.label]}

    def source(self):
        database = self.args.name
        source = self.object(database + "_start")
        if not source or source[2] is None or not source[2].startswith(TEMPLATE_TAG) or source[3] or not source[4]:
            raise CopyError(4, "no-template", "this database has no registered template")
        try:
            data = json.loads(source[2][len(TEMPLATE_TAG):])
            if data["database"] != database or data["strategy"] not in ("wal_log", "file_copy"):
                raise ValueError("invalid template")
            return data["strategy"], {"build": data["build"], "digest": data["digest"]}
        except (TypeError, KeyError, ValueError):
            raise CopyError(5, "format-unknown", "template registration cannot be read") from None

    def create(self):
        strategy, template = self.source()
        database, label = self.args.name, self.args.label
        while True:
            identity = uuid4().hex
            name = f"{self.prefix}_{database}_{identity[:12]}"
            with self.lock(name) as acquired:
                if not acquired:
                    continue
                with self.lock("namespace/" + self.prefix, wait=5) as admission:
                    if not admission:
                        raise CopyError(6, "busy", "namespace reservation is busy")
                    if self.load(name) is not None or self.object(name):
                        continue
                    duplicate, total = self.one(
                        f"SELECT count(*) FILTER (WHERE record->>'label'=%s), count(*) FROM {self.ledger}",
                        (label,),
                    )
                    if duplicate:
                        raise CopyError(5, "label-in-use", "label already belongs to a copy")
                    if total >= self.limit:
                        raise CopyError(5, "limit", "namespace is at its copy limit")
                    row = {
                        "tag": COPY_TAG, "name": name, "identity": identity, "prefix": self.prefix,
                        "label": label, "database": database, "phase": "reserved", "revision": 1,
                        "lease_until": self.lease_end(self.args.lease), "template": template,
                    }
                    self.connection.execute(f"INSERT INTO {self.ledger} (name, record) VALUES (%s,%s::jsonb)",
                                            (name, json.dumps(row)))
                try:
                    return self.create_reserved(row, strategy)
                except self.errors.Error:
                    raise CopyError(8, "create-unsettled", "database copy did not finish", identity) from None

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

    def ensure_identity(self, row):
        if row is None or row.get("identity") != self.args.identity:
            raise CopyError(5, "identity", "copy identity does not match", self.args.identity)

    def update_lease(self, seconds):
        name = self.args.name
        with self.lock(name) as acquired:
            if not acquired:
                raise CopyError(6, "busy", "copy is changing", self.args.identity)
            row = self.load(name)
            self.ensure_identity(row)
            if self.state(name, row) != "ready":
                raise CopyError(5, "state", "copy is not ready", self.args.identity)
            return self.result(name, self.change(row, lease_until=self.lease_end(seconds)), "ready")

    def renew(self):
        return self.update_lease(self.args.lease)

    def release(self):
        return self.update_lease(0)

    def remove(self, row, state, wait=0):
        name, identity = row["name"], row["identity"]
        try:
            if state in ("ready", "dropping"):
                if self.state(name, row) != state:
                    raise CopyError(5, "inconsistent", "database identity changed", identity)
                if state != "dropping":
                    row = self.change(row, phase="dropping")
                deadline = time.monotonic() + wait
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
            self.connection.execute(f"DELETE FROM {self.ledger} WHERE name=%s", (name,))
        except self.errors.Error:
            raise CopyError(8, "drop-unsettled", "database removal did not finish", identity) from None
        return self.result(name, row, "gone")

    def drop(self):
        name, identity = self.args.name, self.args.identity
        with self.lock(name, self.args.wait) as acquired:
            if not acquired:
                raise CopyError(6, "busy", "copy is changing", identity)
            row = self.load(name)
            state = self.state(name, row)
            if row is None and state == "gone":
                return self.result(name, None, "gone")
            self.ensure_identity(row)
            if state not in ("ready", "dropping", "stale", "gone"):
                raise CopyError(5, state, "copy is kept", identity)
            return self.remove(row, state, self.args.wait)

    def sweep(self):
        removed, kept = [], []
        for name in self.names():
            selected = self.inspect(name)
            with self.lock(name) as acquired:
                row = self.load(name) if acquired else None
                if not acquired or row is None:
                    reason = "changing" if not acquired else selected["state"]
                elif (row["identity"], row["revision"]) != (selected["identity"], selected["revision"]):
                    reason = "changed"
                else:
                    reason = self.state(name, row)
                    if reason == "ready" and not self.expired(row):
                        reason = "leased"
                    if reason in ("ready", "stale", "gone"):
                        if self.args.dry_run:
                            removed.append(selected)
                        else:
                            try:
                                removed.append(self.remove(row, reason))
                            except CopyError as error:
                                if error.status != 6:
                                    raise
                                kept.append({"copy": selected, "reason": "busy"})
                        continue
                kept.append({"copy": selected, "reason": reason})
        return {"removed": removed, "kept": kept}


@contextmanager
def open_postgres(args, password):
    import psycopg

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
