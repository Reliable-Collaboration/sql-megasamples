"""Generate the PostgreSQL image's copy namespace and account SQL."""

from pathlib import Path


def stage_roles(context, settings):
    lines = [
        "CREATE TABLE copy_namespaces (prefix text PRIMARY KEY, owner name NOT NULL, "
        "max_copies integer NOT NULL);",
        "CREATE TABLE copy_service (singleton boolean PRIMARY KEY CHECK (singleton), "
        "tag text NOT NULL, volume text NOT NULL);",
        "GRANT SELECT ON copy_namespaces, copy_service TO PUBLIC;",
    ]
    for item in settings.namespaces:
        prefix, owner = item.prefix, item.owner
        marker = f"megasamples_copy_{prefix}_owner"
        reader = f"megasamples_copy_{prefix}_read"
        ledger = f"copy_ledger_{prefix}"
        lines += [
            f'CREATE ROLE "{marker}";',
            f'CREATE ROLE "{reader}";',
            f'CREATE ROLE "{owner}" LOGIN CREATEDB;',
            f'GRANT megasamples_read TO "{reader}" WITH INHERIT TRUE, SET FALSE;',
            f'GRANT megasamples_read, megasamples_write_routines, "{marker}" TO "{owner}" WITH INHERIT TRUE, SET FALSE;',
            f"INSERT INTO copy_namespaces VALUES ('{prefix}', '{owner}', {item.max_copies});",
            f'CREATE TABLE "{ledger}" (name text PRIMARY KEY, record jsonb NOT NULL);',
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{ledger}" TO "{owner}", admin;',
            f'GRANT EXECUTE ON FUNCTION pg_catalog.pg_try_advisory_lock(bigint), '
            f'pg_catalog.pg_advisory_unlock(bigint) TO "{owner}";',
        ]
    for accounts, mode in ((settings.readers, "read"), (settings.writers, "write")):
        for account, scopes in accounts.items():
            lines.append(f'CREATE ROLE "{account}" LOGIN;')
            for scope in scopes:
                group = f"megasamples_working_{mode}" if scope == "working" else f"megasamples_copy_{scope}_read"
                lines.append(f'GRANT "{group}" TO "{account}" WITH INHERIT TRUE, SET FALSE;')
    (Path(context) / "copy-roles.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")
