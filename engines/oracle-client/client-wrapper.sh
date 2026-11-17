#!/bin/sh
set -eu
case "${0##*/}" in
    megasamples-sqlplus) program=sqlplus ;;
    megasamples-sqlldr) program=sqlldr ;;
    *) echo 'Invoke as megasamples-sqlplus or megasamples-sqlldr' >&2; exit 2 ;;
esac
# Instant Client supplies its own libraries. Do not change the server's global
# ORACLE_HOME or library search path; the database's original bootstrap is separate.
unset ORACLE_HOME
export LD_LIBRARY_PATH="/opt/megasamples/instantclient${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "/opt/megasamples/instantclient/$program" "$@"
