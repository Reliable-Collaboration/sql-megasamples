"""Shared server copy operations that hold one session through each change."""

from datetime import datetime
import json
from uuid import uuid4

from megasamples.copying import CopyError, IDENTITY, LABEL, database_is_valid

COPY_TAG = "megasamples-copy/1"
SERVICE_TAG = "megasamples-service/1"


class ServerCopies:
    recovery_identity = None

    def server_error(self, failure):
        """Map a driver error to section 3.3's exit codes, keeping the identity a caller recovers by."""
        action = self.args.action
        identity = self.recovery_identity or getattr(self.args, "identity", None)
        if action == "create" and self.recovery_identity:
            return CopyError(8, "create-unsettled", "database copy did not finish", identity)
        if action in ("renew", "release") and self.recovery_identity:
            return CopyError(8, "lease-unsettled", "lease update did not finish", identity)
        if self.connection_lost(failure):
            return CopyError(8, "connection-lost", "server connection closed during the copy command", identity)
        return CopyError(1, "internal", "copy command failed unexpectedly", identity)

    def load(self, name):
        row = self.one(f"SELECT record FROM {self.ledger} WHERE name=%s", (name,))
        if row is None:
            return None
        record = row[0]
        try:
            if isinstance(record, str):
                record = json.loads(record)
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

    def result(self, name, row, state):
        row = row or {}
        return {"name": name, "identity": row.get("identity"), "engine": self.engine,
                "database": row.get("database"), "prefix": self.prefix, "label": row.get("label"),
                "state": state, "revision": row.get("revision"), "lease_until": row.get("lease_until"),
                "endpoint": {"host": self.args.host, "port": self.port}, "owner": self.owner,
                "template": row.get("template"), "version": self.version, "proof": row.get("proof")}

    def inspect(self, name, *, label=None):
        with self.lock(name) as acquired:
            row = self.load(name)
            if label is not None and (row is None or row["label"] != label):
                return None
            return self.result(name, row, self.state(name, row) if acquired else "changing")

    def show(self):
        return self.inspect(self.args.name)

    def list(self):
        rows = [self.inspect(name, label=self.args.label) for name in self.names()]
        return {"copies": [row for row in rows if row is not None]}

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
                    duplicate, total = self.reservation_counts(label)
                    if duplicate:
                        raise CopyError(5, "label-in-use", "label already belongs to a copy")
                    if total >= self.limit:
                        raise CopyError(5, "limit", "namespace is at its copy limit")
                    row = {
                        "tag": COPY_TAG, "name": name, "identity": identity, "prefix": self.prefix,
                        "label": label, "database": database, "phase": "reserved", "revision": 1,
                        "lease_until": self.lease_end(self.args.lease), "template": template,
                    }
                    # From here a reply can be lost after the row is durable: keep the identity.
                    self.recovery_identity = identity
                    self.insert(row)
                return self.create_reserved(row, strategy)

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
            lease = self.lease_end(seconds)
            self.recovery_identity = row["identity"]
            return self.result(name, self.change(row, lease_until=lease), "ready")

    def renew(self):
        return self.update_lease(self.args.lease)

    def release(self):
        return self.update_lease(0)

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
        selected_copies = [self.inspect(name) for name in self.names()]
        if not self.args.dry_run:
            for selected in selected_copies:
                if selected["state"] == "not-exclusive":
                    raise CopyError(5, "not-exclusive", "another account can replace the copy", selected["identity"])
        for selected in selected_copies:
            name = selected["name"]
            with self.lock(name) as acquired:
                row = self.load(name) if acquired else None
                if not acquired or row is None:
                    reason = "changing" if not acquired else selected["state"]
                elif (row["identity"], row["revision"]) != (selected["identity"], selected["revision"]):
                    reason = "changed"
                else:
                    reason = self.state(name, row)
                    if reason == "not-exclusive" and not self.args.dry_run:
                        raise CopyError(8 if removed else 5, "not-exclusive",
                                        "another account can replace the copy", row["identity"])
                    # A proven `dropping` copy whose lease has ended is the sweep's to finish (2.2).
                    if reason in ("ready", "dropping") and not self.expired(row):
                        reason = "leased"
                    if reason in ("ready", "dropping", "stale", "gone"):
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
