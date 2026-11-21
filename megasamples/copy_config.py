"""The image-build configuration for templates, namespaces and their accounts."""

from dataclasses import dataclass

from megasamples import datasets, registry
from megasamples.copying import database_is_valid, prefix_is_valid

BUILTIN_SCHEMAS = {
    "information_schema", "mysql", "performance_schema", "sys", "pg_catalog",
    "postgres", "public", "template0", "template1", "sqlite_schema",
    "sqlite_master", "megasamples",
}
SERVICE_NAMES = {"postgres", "root", "admin", "demo", "mysql_root", "mysql_demo", "megasamples"}
# The roles engines/postgres/init/00-users.sql creates (tests/test_v1_service_role_names.py reads them there).
POSTGRES_ROLES = {"admin", "demo", "megasamples_read", "megasamples_write_routines", "megasamples_working_read",
                  "megasamples_working_write"}


@dataclass(frozen=True)
class Namespace:
    prefix: str
    owner: str
    max_copies: int


def overlaps(left, right):
    return left == right or left.startswith(right + "_") or right.startswith(left + "_")


def records(value, name):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{name} must be a list of mappings")
    return value


class CopySettings:
    def __init__(self, configuration, engine, selected):
        self.databases = registry.by_database(selected)
        definition = configuration.raw.get("engines", {}).get(engine) or {}
        selection = definition.get("templates", "core")
        if any(not database_is_valid(name) for name in self.databases):
            raise ValueError("a physical database name is invalid or longer than 33 bytes")
        if selection == "none":
            self.templates = []
        elif isinstance(selection, list):
            if any(not isinstance(name, str) or name not in self.databases for name in selection):
                raise ValueError(f"{engine} templates list must name installed physical databases")
            self.templates = list(dict.fromkeys(selection))
        elif isinstance(selection, str):
            bases = {datasets.load(dataset)["database"]
                     for dataset in datasets.select(selection, include_prerequisites=False)
                     if not datasets.load(dataset).get("append")}
            self.templates = [name for name in self.databases if name in bases]
        else:
            raise ValueError(f"invalid template selector for {engine}")

        copies = configuration.raw.get("copies", {})
        accounts = configuration.raw.get("accounts", {})
        if not isinstance(copies, dict) or not isinstance(accounts, dict):
            raise ValueError("copies and accounts must be mappings")
        self.namespaces = []
        self.foreign = []
        prefixes = []
        registered = BUILTIN_SCHEMAS | set(self.databases)
        registered |= set(registry.by_database(configuration.datasets()))
        registered |= {name + "_start" for name in registered}
        names = set(SERVICE_NAMES)

        def reserve_prefix(prefix):
            if (not prefix_is_valid(prefix)
                    or any(name == prefix or name.startswith(prefix + "_") for name in registered)
                    or any(overlaps(prior, prefix) for prior in prefixes)):
                raise ValueError(f"invalid or overlapping copy prefix {prefix!r}")
            if any(len(prefix) + len(name) + 14 > 63 for name in self.databases):
                raise ValueError("namespace and physical database would form a name longer than 63 bytes")
            prefixes.append(prefix)

        def reserve_account(name):
            # The PostgreSQL service's own roles: those initialisation creates, and every
            # megasamples_ name the generated DDL derives, would collide with its CREATE ROLE.
            if (not prefix_is_valid(name) or name in names or name.endswith("_start")
                    or name in POSTGRES_ROLES or name.startswith("megasamples_")):
                raise ValueError(f"invalid or duplicate account/key name {name!r}")
            names.add(name)

        for item in records(copies.get("namespaces", [{"prefix": "copy", "owner": "copier", "max_copies": 32}]),
                            "copies.namespaces"):
            prefix, owner, limit = item.get("prefix"), item.get("owner"), item.get("max_copies", 32)
            reserve_prefix(prefix)
            reserve_account(owner)
            if type(limit) is not int or limit < 1:
                raise ValueError("max_copies must be a positive integer")
            self.namespaces.append(Namespace(prefix, owner, limit))

        for item in records(copies.get("foreign", []), "copies.foreign"):
            prefix, demo_reads = item.get("prefix"), item.get("demo_reads", False)
            reserve_prefix(prefix)
            if type(demo_reads) is not bool:
                raise ValueError("demo_reads must be a boolean")
            self.foreign.append((prefix, demo_reads))

        self.readers, self.writers = {}, {}
        scopes = {"working", *(namespace.prefix for namespace in self.namespaces)}
        for key, available, result in (("readers", scopes, self.readers), ("writers", {"working"}, self.writers)):
            for item in records(accounts.get(key, []), f"accounts.{key}"):
                name, assigned = item.get("name"), item.get("scopes")
                reserve_account(name)
                if (not isinstance(assigned, list) or not assigned
                        or any(not isinstance(scope, str) or scope not in available for scope in assigned)):
                    raise ValueError(f"invalid {key} scopes for {name}")
                result[name] = tuple(dict.fromkeys(assigned))

        self.binary_log = (configuration.raw.get("engines", {}).get("mysql") or {}).get("binary_log", True)
        if type(self.binary_log) is not bool:
            raise ValueError("engines.mysql.binary_log must be a boolean")
