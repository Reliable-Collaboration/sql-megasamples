"""Report PostgreSQL data directories that have no database (DL-119's detective control).

A caller's cancel, a resource error or a crash between CREATE DATABASE's file copy and its commit can
leave a directory under the data directory with no catalog row: no SQL reaches it, and it uses disk
until an administrator removes it (README) or the volume is next replaced. This reads the directories
first and the catalog second, inside the running container, and reports what has no row. A create
or a drop still in progress can appear once; a rerun settles it.
"""
import subprocess

LIST = r'''set -eu
cd "$PGDATA"
measure() {
  # A directory dropped since the glob is not an orphan; one still there that du cannot read is.
  if out=$(du -sk "$3" 2>/dev/null); then printf '%s %s %s %s\n' "$1" "$2" "${out%%[[:space:]]*}" "$3"
  elif [ -e "$3" ]; then printf 'unreadable %s\n' "$3"
  fi
}
for d in base/*; do
  [ -e "$d" ] || continue
  o=${d#base/}; case $o in *[!0-9]*) continue;; esac
  measure pg_default "$o" "$d"
done
for t in pg_tblspc/*; do
  [ -e "$t" ] || [ -L "$t" ] || continue
  s=${t#pg_tblspc/}
  # A tablespace whose location cannot be listed is not inspected: say so, never skip it quietly.
  if ! ls "$t"/ >/dev/null 2>&1 || ! ls "$t"/PG_*/ >/dev/null 2>&1; then printf 'unreadable %s\n' "$t"; continue; fi
  printf 'space %s\n' "$s"
  for d in "$t"/PG_*/*; do
    [ -d "$d" ] || continue
    o=${d##*/}; case $o in *[!0-9]*) continue;; esac
    measure "$s" "$o" "$d"
  done
done
'''


def _psql(container, sql):
    return subprocess.run(["docker", "exec", "-u", "postgres", container, "psql", "-XqAt", "-U", "postgres",
                           "-d", "postgres", "-c", sql], capture_output=True, text=True, timeout=120)


def scan(container):
    """Warnings for every data directory with no database; a last warning if the scan was incomplete."""
    incomplete = {"code": "orphan-scan-incomplete", "engine": "postgres"}
    try:
        listing = subprocess.run(["docker", "exec", "-u", "postgres", container, "sh", "-c", LIST],
                                 capture_output=True, text=True, timeout=300)
        catalog = _psql(container, "SELECT oid FROM pg_catalog.pg_database")
        spaces = _psql(container, "SELECT oid, spcname FROM pg_catalog.pg_tablespace")
    except (OSError, subprocess.SubprocessError):
        return [{**incomplete, "reason": "the scan could not run"}]
    oids = set(catalog.stdout.split())
    if listing.returncode or catalog.returncode or spaces.returncode or not oids:
        return [{**incomplete, "reason": "a directory, catalog or tablespace read failed"}]
    names = {"pg_default": "pg_default"}
    for line in spaces.stdout.splitlines():
        oid, _, name = line.partition("|") if "|" in line else line.partition(" ")
        names[oid] = name
    warnings = []
    inspected = {"1663", "1664"}   # pg_default and pg_global are base/ and global/
    for line in listing.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == "space":
            inspected.add(fields[1])
            continue
        if len(fields) != 4 or not fields[1].isdigit() or not fields[2].isdigit():
            return [{**incomplete, "reason": "a data directory could not be measured"}]
        space, oid, kib, path = fields
        if oid not in oids:
            warnings.append({"code": "orphan-directory", "engine": "postgres", "tablespace": names.get(space, space),
                             "oid": int(oid), "name": None, "path": path, "kib": int(kib)})
    if not set(names) - {"pg_default"} <= inspected:
        return [{**incomplete, "reason": "a tablespace's directories could not be listed"}]
    return warnings


def describe(warning):
    if warning["code"] == "orphan-scan-incomplete":
        return "postgres: the scan for data directories with no database could not complete"
    return (f"postgres: data directory {warning['path']} (tablespace {warning['tablespace']}, OID {warning['oid']}, "
            f"{warning['kib']} KiB) has no database; see the README before removing it")
