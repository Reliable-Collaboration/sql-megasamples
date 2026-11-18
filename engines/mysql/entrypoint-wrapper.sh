#!/bin/bash
# megasamples runtime hook. The image ships an already-initialised data directory, so the official
# entrypoint's account setup never runs (it only fires on an empty datadir). Password overrides are
# therefore applied here, through a --init-file that mysqld reads at startup.
set -euo pipefail

if [ "${1:-}" = "mysqld" ] && [ -n "${MYSQL_ROOT_PASSWORD:-}${DEMO_PASSWORD:-}${ADMIN_PASSWORD:-}" ]; then
    init_file="$(mktemp /tmp/megasamples-init.XXXXXX.sql)"
    # The official entrypoint re-execs itself under `gosu mysql`, so the file must be readable by
    # that user and by nobody else: a root-owned 0600 file fails to open, and 0644 would leave the
    # passwords readable for the life of the container.
    install -m 0400 -o mysql -g mysql /dev/null "$init_file"
    trap 'rm -f "$init_file"' EXIT

    # Single-quote each password and double every backslash and quote inside it, so a password
    # containing either cannot break out of the statement.
    sql_quote() { printf "'%s'" "$(printf '%s' "$1" | sed "s/\\\\/\\\\\\\\/g; s/'/''/g")"; }

    {
        [ -n "${MYSQL_ROOT_PASSWORD:-}" ] && {
            echo "ALTER USER 'root'@'localhost' IDENTIFIED BY $(sql_quote "$MYSQL_ROOT_PASSWORD");"
            echo "ALTER USER 'root'@'%' IDENTIFIED BY $(sql_quote "$MYSQL_ROOT_PASSWORD");"; }
        [ -n "${DEMO_PASSWORD:-}" ]  && echo "ALTER USER 'demo'@'%' IDENTIFIED BY $(sql_quote "$DEMO_PASSWORD");"
        [ -n "${ADMIN_PASSWORD:-}" ] && echo "ALTER USER 'admin'@'%' IDENTIFIED BY $(sql_quote "$ADMIN_PASSWORD");"
        true
    } > "$init_file"

    set -- "$@" --init-file="$init_file"
fi

# Healthchecks run as the container owner. A private option file keeps the password
# out of both mysql's command line and its environment (including process listings).
umask 077
health_file=/run/megasamples-health.cnf
{
    printf '[client]\nuser=demo\npassword="'
    printf '%s' "${DEMO_PASSWORD:-demo}" | sed 's/\\/\\\\/g; s/"/\\"/g'
    printf '"\nhost=127.0.0.1\nprotocol=TCP\n'
} > "$health_file"
chmod 600 "$health_file"
unset MYSQL_ROOT_PASSWORD DEMO_PASSWORD ADMIN_PASSWORD

exec /usr/local/bin/docker-entrypoint.sh "$@"
