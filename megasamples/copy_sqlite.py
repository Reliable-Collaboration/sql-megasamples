"""SQLite copy records, retained files and namespace locks."""

from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import time
from uuid import uuid4

from megasamples.copying import (
    CopyError, IDENTITY, LABEL, database_is_valid, expiry, now,
    prefix_is_valid,
)

MANIFEST = "megasamples-manifest/1"
SIDECAR = "megasamples-sidecar/1"
PREVIOUS_SIDECAR = "megasamples-sidecar/0"
PHASES = {"reserved", "issuing", "created", "ready", "dropping"}


def present(path):
    return os.path.lexists(path)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_directory(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise CopyError(5, "directory", "copy bookkeeping directory is not private")
    return True


def read_json(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("expected a regular file")
        return json.load(stream)


def publish_record(path, row, new=False):
    descriptor, temporary = tempfile.mkstemp(prefix=".record-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(row, stream, ensure_ascii=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if new:
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


@contextmanager
def locked(path, *, write=False, wait=0):
    flags = os.O_NOFOLLOW | os.O_NONBLOCK | (os.O_CREAT | os.O_RDWR if write else os.O_RDONLY)
    try:
        fd = os.open(path, flags, 0o600)
    except FileNotFoundError:
        if write:
            raise
        yield True
        return
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise CopyError(5, "lock", "copy lock is not a regular file")
        deadline = time.monotonic() + wait
        acquired = False
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.05))
        yield acquired
    finally:
        os.close(fd)


class SQLiteCopies:
    def __init__(self, args):
        self.args = args
        self.directory = Path(args.dir).resolve()
        self.templates = Path(args.templates).resolve()
        self.metadata = self.directory / ".megasamples"
        self.warnings = []
        try:
            manifest = read_json(self.templates / "templates.json")
            if not isinstance(manifest, dict) or manifest.get("tag") != MANIFEST:
                raise ValueError("invalid manifest tag")
            self.entries = {entry["name"]: entry for entry in manifest["templates"]}
            self.namespaces = manifest.get("namespaces", {"copy": 32})
            if (not isinstance(self.namespaces, dict)
                    or any(not prefix_is_valid(prefix) or type(limit) is not int or limit < 1
                           for prefix, limit in self.namespaces.items())):
                raise ValueError("invalid namespaces")
        except (KeyError, TypeError, ValueError, OSError):
            raise CopyError(5, "format-unknown", "template manifest cannot be read") from None
        if not self.directory.is_dir():
            raise CopyError(5, "directory", "copy directory does not exist")
        if getattr(args, "prefix", None) is not None and args.prefix not in self.namespaces:
            raise CopyError(5, "namespace", "copy namespace is not configured")
        private_directory(self.metadata)

    def writable(self):
        self.metadata.mkdir(mode=0o700, exist_ok=True)
        private_directory(self.metadata)
        sync_directory(self.directory)

    def sidecar(self, name):
        return self.metadata / (name + ".json")

    def final(self, name):
        return self.directory / (name + ".sqlite")

    def retained(self, row):
        return self.metadata / (row["identity"] + ".sqlite")

    def aside(self, row):
        return self.metadata / (row["identity"] + ".aside")

    def lock(self, name, **options):
        return locked(self.metadata / (name + ".lock"), **options)

    def load(self, name):
        try:
            row = read_json(self.sidecar(name))
        except FileNotFoundError:
            return None
        except (ValueError, OSError):
            raise CopyError(5, "format-unknown", "copy sidecar cannot be read") from None
        try:
            if (row["tag"] not in (SIDECAR, PREVIOUS_SIDECAR) or row["name"] != name
                    or not IDENTITY.fullmatch(row["identity"]) or not LABEL.fullmatch(row["label"])
                    or not database_is_valid(row["database"]) or row["prefix"] not in self.namespaces
                    or name != f"{row['prefix']}_{row['database']}_{row['identity'][:12]}"
                    or row["phase"] not in PHASES or type(row["revision"]) is not int
                    or row["revision"] < 1 or not datetime.fromisoformat(row["lease_until"]).tzinfo):
                raise ValueError("invalid record")
        except (KeyError, ValueError, TypeError):
            raise CopyError(5, "format-unknown", "copy sidecar cannot be interpreted") from None
        return row

    def update(self, row, **changes):
        after = {**row, **changes, "revision": row["revision"] + 1}
        publish_record(self.sidecar(row["name"]), after)
        return after

    def names(self, prefix):
        names = {file.stem for file in self.directory.glob(prefix + "_*.sqlite")}
        names.update(file.stem for file in self.metadata.glob(prefix + "_*.json"))
        return sorted(names)

    def namespace_for(self, name):
        for prefix in self.namespaces:
            if name.startswith(prefix + "_"):
                return prefix
        raise CopyError(5, "namespace", "copy name is outside the configured namespaces")

    def matches(self, path, row):
        try:
            chosen = path.lstat()
            kept = self.retained(row).lstat()
        except FileNotFoundError:
            return False
        return stat.S_ISREG(chosen.st_mode) and stat.S_ISREG(kept.st_mode) and os.path.samestat(chosen, kept)

    def state(self, name, row, *, explicit_drop=False):
        file = self.final(name)
        exists = present(file)
        if row is None:
            return "unmanaged" if exists else "gone"
        if row["tag"] == PREVIOUS_SIDECAR and not explicit_drop:
            return "previous-format"
        if row["phase"] in ("reserved", "issuing", "created"):
            return "interrupted" if exists or row["phase"] == "created" else "stale"
        aside = self.aside(row)
        if present(aside):
            return "dropping" if row["phase"] == "dropping" and not exists and self.matches(aside, row) else "inconsistent"
        if not exists:
            return "gone"
        if not self.matches(file, row):
            return "inconsistent"
        return row["phase"]

    def result(self, name, row, state):
        result = {"name": name, "identity": None, "engine": "sqlite", "database": None,
                  "prefix": self.namespace_for(name), "label": None, "state": state, "revision": None,
                  "lease_until": None, "endpoint": str(self.final(name)), "owner": None,
                  "template": None, "version": sqlite3.sqlite_version, "proof": None}
        if row is not None:
            for key in ("identity", "database", "prefix", "label", "revision", "lease_until", "template"):
                result[key] = row.get(key)
            result["proof"] = row.get("proof")
        return result

    def inspect(self, name):
        self.namespace_for(name)
        with self.lock(name) as acquired:
            row = self.load(name)
            state = self.state(name, row) if acquired else "changing"
            return self.result(name, row, state)

    def show(self):
        return self.inspect(self.args.name)

    def list(self):
        results = []
        for name in self.names(self.args.prefix):
            item = self.inspect(name)
            if self.args.label is None or item["label"] == self.args.label:
                results.append(item)
        return {"copies": results}

    def source(self):
        name = self.args.name + ".sqlite"
        entry = self.entries.get(name)
        if entry is None:
            raise CopyError(4, "no-template", "no template is offered for this database")
        digest = entry.get("sha256")
        size = entry.get("size")
        if (not isinstance(digest, str) or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
                or type(size) is not int or size < 0):
            raise CopyError(5, "format-unknown", "template manifest entry cannot be interpreted")
        return self.templates / name, entry

    def create(self):
        source, entry = self.source()
        self.writable()
        prefix, database = self.args.prefix, self.args.name
        # Acquire the candidate lock first and keep it through creation, while
        # the namespace lock covers just counting and reserving.
        while True:
            identity = uuid4().hex
            name = f"{prefix}_{database}_{identity[:12]}"
            with self.lock(name, write=True) as acquired:
                if not acquired:
                    continue
                with self.lock("namespace-" + prefix, write=True, wait=5) as admission:
                    if not admission:
                        raise CopyError(6, "busy", "namespace reservation is busy")
                    if (present(self.final(name)) or present(self.sidecar(name))
                            or self.adjacent(name)):
                        continue
                    rows = [self.load(existing) for existing in self.names(prefix)]
                    rows = [row for row in rows if row is not None]
                    if any(row["label"] == self.args.label for row in rows):
                        raise CopyError(5, "label-in-use", "label already belongs to a copy")
                    if len(rows) >= self.namespaces[prefix]:
                        raise CopyError(5, "limit", "namespace is at its copy limit")
                    row = {
                        "tag": SIDECAR, "name": name, "identity": identity,
                        "label": self.args.label, "database": database, "prefix": prefix,
                        "phase": "reserved", "revision": 1, "lease_until": expiry(self.args.lease),
                        "template": {"build": entry.get("build"), "digest": entry.get("registry_digest")},
                    }
                    try:
                        publish_record(self.sidecar(name), row, new=True)
                    except OSError:
                        if present(self.sidecar(name)):
                            raise CopyError(8, "create-unsettled", "reservation durability is uncertain", identity) from None
                        raise CopyError(5, "reservation", "copy reservation could not be written") from None
                try:
                    return self.create_reserved(row, source, entry)
                except (OSError, ValueError):
                    raise CopyError(8, "create-unsettled", "copy creation did not finish", identity) from None

    def create_reserved(self, row, source, entry):
        name = row["name"]
        row = self.update(row, phase="issuing")
        link = self.retained(row)
        with os.fdopen(os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as original:
            if not stat.S_ISREG(os.fstat(original.fileno()).st_mode):
                raise ValueError("template is not a regular file")
            digest = hashlib.sha256()
            size = 0
            with link.open("xb") as output:
                os.fchmod(output.fileno(), 0o600)
                while data := original.read(1024 * 1024):
                    digest.update(data)
                    size += output.write(data)
                output.flush()
                os.fsync(output.fileno())
        if size != entry["size"] or digest.hexdigest() != entry["sha256"]:
            raise ValueError("copy does not match manifest")
        sync_directory(self.metadata)
        os.link(link, self.final(name))
        sync_directory(self.directory)
        row = self.update(row, phase="created", proof={"retained": link.name})
        row = self.update(row, phase="ready")
        return self.result(name, row, "ready")

    def change_lease(self, seconds):
        name = self.args.name
        self.namespace_for(name)
        if not private_directory(self.metadata):
            raise CopyError(5, "identity", "copy identity does not match", self.args.identity)
        with self.lock(name, write=True) as acquired:
            if not acquired:
                raise CopyError(6, "busy", "copy is changing", self.args.identity)
            row = self.load(name)
            self.require_identity(row)
            if self.state(name, row) != "ready":
                raise CopyError(5, "state", "copy is not ready", self.args.identity)
            try:
                row = self.update(row, lease_until=expiry(seconds))
            except OSError:
                raise CopyError(8, "lease-unsettled", "lease update did not finish", self.args.identity) from None
            return self.result(name, row, "ready")

    def require_identity(self, row):
        if row is None or row["identity"] != self.args.identity:
            raise CopyError(5, "identity", "copy identity does not match", self.args.identity)

    def renew(self):
        return self.change_lease(self.args.lease)

    def release(self):
        return self.change_lease(0)

    def adjacent(self, name):
        final = str(self.final(name))
        return [suffix for suffix in ("-journal", "-wal", "-shm") if present(final + suffix)]

    def finish_drop(self, row, state):
        name, identity = row["name"], row["identity"]
        file, aside, retained = self.final(name), self.aside(row), self.retained(row)
        try:
            if state in ("ready", "dropping"):
                if row["phase"] != "dropping":
                    row = self.update(row, phase="dropping", aside=aside.name)
                if not present(aside):
                    os.rename(file, aside)
                    sync_directory(self.directory)
                    sync_directory(self.metadata)
                if not self.matches(aside, row) or present(file):
                    if not present(file):
                        try:
                            os.link(aside, file, follow_symlinks=False)
                        except FileExistsError:
                            pass
                        else:
                            sync_directory(self.directory)
                            aside.unlink()
                            sync_directory(self.metadata)
                    raise CopyError(8, "inconsistent", "file identity changed during drop", identity)
                aside.unlink()
                sync_directory(self.metadata)
            if present(aside):
                raise CopyError(8, "inconsistent", "file remains set aside", identity)
            retained.unlink(missing_ok=True)
            sync_directory(self.metadata)
            self.sidecar(name).unlink()
            sync_directory(self.metadata)
        except OSError:
            raise CopyError(8, "drop-unsettled", "copy removal did not finish", identity) from None
        for suffix in self.adjacent(name):
            self.warnings.append({"code": "adjacent-file", "name": name + ".sqlite" + suffix})
        return self.result(name, row, "gone")

    def drop(self):
        name, identity = self.args.name, self.args.identity
        self.namespace_for(name)
        if not private_directory(self.metadata) and not present(self.final(name)):
            return self.result(name, None, "gone")
        if not private_directory(self.metadata):
            raise CopyError(5, "unmanaged", "copy is unmanaged", identity)
        with self.lock(name, write=True, wait=self.args.wait) as acquired:
            if not acquired:
                raise CopyError(6, "busy", "copy is changing", identity)
            row = self.load(name)
            state = self.state(name, row, explicit_drop=True)
            if row is None and state == "gone":
                return self.result(name, None, "gone")
            self.require_identity(row)
            if state not in ("ready", "dropping", "stale", "gone"):
                raise CopyError(5, state, "copy is kept", identity)
            return self.finish_drop(row, state)

    def sweep(self):
        removed, kept = [], []
        selected = [self.inspect(name) for name in self.names(self.args.prefix)]
        for item in selected:
            name = item["name"]
            if item["state"] not in ("ready", "dropping", "stale", "gone"):
                kept.append({"copy": item, "reason": item["state"]})
                continue
            if item["state"] in ("ready", "dropping") and datetime.fromisoformat(item["lease_until"]) > now():
                kept.append({"copy": item, "reason": "leased"})
                continue
            if self.args.dry_run:
                removed.append(item)
                continue
            with self.lock(name, write=True) as acquired:
                try:
                    row = self.load(name) if acquired else None
                    if row is None or (row["identity"], row["revision"]) != (item["identity"], item["revision"]):
                        kept.append({"copy": item, "reason": "changed" if acquired else "changing"})
                        continue
                    state = self.state(name, row)
                    if state != item["state"]:
                        kept.append({"copy": item, "reason": state})
                        continue
                    if state in ("ready", "dropping") and datetime.fromisoformat(row["lease_until"]) > now():
                        kept.append({"copy": item, "reason": "leased"})
                        continue
                    removed.append(self.finish_drop(row, state))
                except CopyError as failure:
                    if not removed:
                        raise
                    error = CopyError(8, failure.code, str(failure), failure.identity or item["identity"])
                    error.result = {"removed": removed, "kept": kept + [{"copy": item, "reason": failure.code}]}
                    raise error from None
        return {"removed": removed, "kept": kept}
