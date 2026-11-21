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
    refuse() { printf '%s\n' "$1" >&2; exit 1; }
    # Only this image's own server, named or by its path; then always by name, so the upstream
    # entrypoint drops to postgres and the password setup below runs for it too.
    [[ "$(realpath -- "$(command -v "$1")")" == "$(realpath -- "$(command -v postgres)")" ]] ||
        refuse 'the megasamples image runs only its own postgres server'
    set -- postgres "${@:2}"
    if [ "$(id -u)" = "0" ]; then
        # The repair the upstream entrypoint makes, made before the server is asked anything.
        find "$PGDATA" \! -user postgres -exec chown postgres '{}' + 2>/dev/null || true
        chmod 700 "$PGDATA" || :
    fi
    as_postgres() { if [ "$(id -u)" = "0" ]; then gosu postgres "$@"; else "$@"; fi; }
    certify_directory() {   # certify_directory LAUNCH-ARGUMENTS...: the directory that launch would open
        local directory
        directory=$(as_postgres postgres "$@" -C data_directory) ||
            refuse 'the megasamples image could not read the server configuration'
        [[ "$(realpath -m -- "$directory")" == "$(realpath -m -- "$PGDATA")" ]] ||
            refuse 'the megasamples image refuses a data directory other than PGDATA'
    }
    certify_libraries() {   # certify_libraries LAUNCH-ARGUMENTS...: the preload that launch would use
        local libraries
        libraries=$(as_postgres postgres "$@" -C shared_preload_libraries) ||
            refuse 'the megasamples image could not read the server configuration'
        [[ $libraries != *'"'* ]] || refuse 'the megasamples image refuses a quoted preload entry'
        printf '%s\n' "$libraries" | tr ',' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' | grep -qx read_policy ||
            refuse 'the megasamples image refuses a server without the read_policy library'
    }
    certify_directory "${@:2}"
    marker="$PGDATA/megasamples-read-policy"
    if [[ ! -f "$marker" || -L "$marker" || $(<"$marker") != 1 ]]; then
        printf '%s\n' 'PostgreSQL data has no compatible megasamples read policy' >&2
        exit 1
    fi
    certify_libraries "${@:2}"
    if [ -n "${POSTGRES_PASSWORD:-}${DEMO_PASSWORD:-}${ADMIN_PASSWORD:-}" ]; then
        # The password setup's private start reads the files alone, without these arguments: it
        # must be certified too (Sol round 4, P2-1).
        certify_directory
        certify_libraries
    fi
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
