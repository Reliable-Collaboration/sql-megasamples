#!/bin/bash
# megasamples runtime hook for the PostgreSQL image. The cluster ships initialised, so the official
# entrypoint's password setup never runs; password overrides are applied here by starting the
# server privately, altering the roles, stopping it, and then handing over to the official entrypoint.
set -euo pipefail

if [[ ${1:-} == -* ]]; then
    set -- postgres "$@"
fi
if [[ $(basename -- "${1:-}") == postgres ]]; then
    # The marker below certifies PGDATA, and the hook exists only while read_policy is preloaded.
    # Ask the server itself what it would use, from every configuration file and option it reads
    # (setting names are case-insensitive, and postgresql.auto.conf persists ALTER SYSTEM).
    as_postgres() { if [ "$(id -u)" = "0" ]; then gosu postgres "$@"; else "$@"; fi; }
    refuse() { printf '%s\n' "$1" >&2; exit 1; }
    directory=$(as_postgres "$1" "${@:2}" -C data_directory) ||
        refuse 'the megasamples image could not read the server configuration'
    [[ "$(realpath -m -- "$directory")" == "$(realpath -m -- "$PGDATA")" ]] ||
        refuse 'the megasamples image refuses a data directory other than PGDATA'
    marker="$PGDATA/megasamples-read-policy"
    if [[ ! -f "$marker" || -L "$marker" || $(<"$marker") != 1 ]]; then
        printf '%s\n' 'PostgreSQL data has no compatible megasamples read policy' >&2
        exit 1
    fi
    libraries=$(as_postgres "$1" "${@:2}" -C shared_preload_libraries) ||
        refuse 'the megasamples image could not read the server configuration'
    printf '%s\n' "$libraries" | tr ',' '\n' | sed 's/^[[:space:]"]*//; s/[[:space:]"]*$//' | grep -qx read_policy ||
        refuse 'the megasamples image refuses a server without the read_policy library'
fi

if [ "${1:-}" = "postgres" ] && [ -n "${POSTGRES_PASSWORD:-}${DEMO_PASSWORD:-}${ADMIN_PASSWORD:-}" ]; then
    # the official entrypoint chowns PGDATA when it runs as root; do the same before the private start
    if [ "$(id -u)" = "0" ]; then
        find "$PGDATA" \! -user postgres -exec chown postgres '{}' + 2>/dev/null || true
        chmod 700 "$PGDATA" || :      # the server refuses a data directory that is not 0700 or 0750
        run_as() { gosu postgres "$@"; }
    else
        run_as() { "$@"; }
    fi
    sql_quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"; }
    run_as pg_ctl -D "$PGDATA" -w -o "-c listen_addresses=''" start >/dev/null
    {
        [ -n "${POSTGRES_PASSWORD:-}" ] && echo "ALTER USER postgres WITH PASSWORD $(sql_quote "$POSTGRES_PASSWORD");"
        [ -n "${DEMO_PASSWORD:-}" ]     && echo "ALTER USER demo WITH PASSWORD $(sql_quote "$DEMO_PASSWORD");"
        [ -n "${ADMIN_PASSWORD:-}" ]    && echo "ALTER USER admin WITH PASSWORD $(sql_quote "$ADMIN_PASSWORD");"
        true
    } | run_as psql -v ON_ERROR_STOP=1 -q postgres
    run_as pg_ctl -D "$PGDATA" -w -m fast stop >/dev/null
fi

# Only the passfile path reaches psql's environment; its contents remain owner-only.
umask 077
health_file=/run/megasamples-health.pgpass
{
    printf '*:*:*:demo:'
    printf '%s' "${DEMO_PASSWORD:-demo}" | sed 's/\\/\\\\/g; s/:/\\:/g'
    printf '\n'
} > "$health_file"
chmod 600 "$health_file"
unset POSTGRES_PASSWORD DEMO_PASSWORD ADMIN_PASSWORD

exec docker-entrypoint.sh "$@"
