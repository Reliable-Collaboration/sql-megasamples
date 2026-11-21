# syntax=docker/dockerfile:1.29.0@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183
# sql-megasamples-postgres: PostgreSQL with sample databases baked into its cluster.
# The builder initialises a cluster at the image's own PGDATA, creates the accounts and the
# provenance registry, loads each configured database from the port files (schema, data, indexes,
# constraints), and stops cleanly; the final stage carries only that cluster. The context is the
# repository root filtered by .dockerignore; build/postgres/image/ holds exactly the databases being
# baked. See ARCHITECTURE.md section 4.
ARG POSTGRES_IMAGE=docker.io/library/postgres:18.7-trixie@sha256:2ea8630df176ad090ec92136dee850397c5af8781e4bcf2e4162593691c61bbc

# Compile only inside the image build, against the exact server headers.
FROM ${POSTGRES_IMAGE} AS policy-build
USER root
RUN apt-get update && apt-get install -y --no-install-recommends gcc make postgresql-server-dev-18="$PG_VERSION" && rm -rf /var/lib/apt/lists/*
COPY engines/postgres/read-policy/ /src/
RUN make -C /src && make -C /src install

FROM ${POSTGRES_IMAGE} AS builder
COPY engines/postgres/init/00-users.sql engines/postgres/init/20-grants.sql /build/init/
COPY build/postgres/image/ /build/databases/
COPY NOTICE.md LICENSES.md CATALOGUE.md README.md /docs/
COPY engines/images.lock.yaml /docs/images.lock.yaml
COPY datasets/ /build/datasets/
RUN set -eu; \
    mkdir -p /docs/datasets; \
    for d in /build/datasets/*/; do \
        n=$(basename "$d"); \
        [ -f "$d/LICENSE" ] && cp "$d/LICENSE" "/docs/datasets/$n.LICENSE"; \
        [ -f "$d/PROVENANCE.md" ] && cp "$d/PROVENANCE.md" "/docs/datasets/$n.PROVENANCE.md"; \
        true; \
    done
USER postgres
RUN <<'SH'
#!/bin/bash
set -euo pipefail
export PGDATA
# initdb with the image's own settings: the entrypoint's defaults for encoding and locale
initdb --username=postgres --pwfile=<(printf 'root\n') --encoding=UTF8 --locale=C.UTF-8 >/dev/null
# what the official entrypoint appends when it initialises a cluster, and never does on a baked one:
# clients on the network authenticate with scram-sha-256 (the image's own loopback stays trusted)
printf 'host all all all scram-sha-256\n' >> "$PGDATA/pg_hba.conf"
# loading tuned for a one-off bulk load into a throwaway server; the shipped cluster keeps the
# image's stock postgresql.conf, since these are unsafe settings for a running database
pg_ctl -w -o "-c listen_addresses='' -c fsync=off -c synchronous_commit=off -c full_page_writes=off -c maintenance_work_mem=512MB -c max_wal_size=4GB -c wal_level=minimal -c max_wal_senders=0" start >/dev/null
psql -v ON_ERROR_STOP=1 -q -f /build/init/00-users.sql postgres
for d in /build/databases/*/; do
  name=$(basename "$d")
  echo "== $name"
  # admin owns the database and everything loaded into it, so the account the consoles call "full
  # access" can alter and drop what it sees; the loopback of this private server is trusted
  psql -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE \"$name\" OWNER admin TEMPLATE template0 ENCODING 'UTF8'" postgres
  psql -U admin -v ON_ERROR_STOP=1 -q -f "$d/schema.sql" "$name"
  while IFS=$'\t' read -r table file cols; do
    psql -U admin -v ON_ERROR_STOP=1 -q -c "\\copy \"$table\" ($cols) FROM '$d/data/$file' WITH (FORMAT text)" "$name"
  done < "$d/data/tables.tsv"
  psql -U admin -v ON_ERROR_STOP=1 -q -f "$d/indexes.sql" "$name"
  psql -U admin -v ON_ERROR_STOP=1 -q -f "$d/constraints.sql" "$name"
  psql -U admin -v ON_ERROR_STOP=1 -q -f "$d/routines.sql" "$name"
  psql -U admin -v ON_ERROR_STOP=1 -q -f "$d/views.sql" "$name"
  psql -U admin -v ON_ERROR_STOP=1 -q -f "$d/triggers.sql" "$name"
  psql -U admin -v ON_ERROR_STOP=1 -q -c "ANALYZE" "$name"
  psql -v ON_ERROR_STOP=1 -q -f /build/init/20-grants.sql "$name"
done
psql -v ON_ERROR_STOP=1 -q -f /build/databases/registry.sql megasamples
pg_ctl -w -m fast stop >/dev/null
SH
# Apply security policy after loading so policy changes reuse the bulk-load layer.
COPY --from=policy-build /usr/lib/postgresql/18/lib/read_policy.so /usr/lib/postgresql/18/lib/read_policy.so
COPY --from=policy-build /usr/share/postgresql/18/extension/read_policy* /usr/share/postgresql/18/extension/
COPY engines/postgres/init/10-read-profile.sql engines/postgres/init/15-read-views.sql engines/postgres/init/read-routine-names.sql /build/init/
RUN <<'SH'
#!/bin/bash
set -euo pipefail
pg_ctl -w -o "-c listen_addresses=''" start >/dev/null
# Harden every database and both future-database templates. template0 is opened
# privately for this pass, then returned to its original nonconnectable state.
psql -v ON_ERROR_STOP=1 -q -c 'ALTER DATABASE template0 ALLOW_CONNECTIONS true' postgres
while IFS= read -r db; do
  psql -v ON_ERROR_STOP=1 -q -f /build/init/10-read-profile.sql "$db"
  psql -v ON_ERROR_STOP=1 -q -f /build/init/15-read-views.sql "$db"
done < <(psql -At -c 'SELECT datname FROM pg_database ORDER BY datname' postgres)
psql -v ON_ERROR_STOP=1 -q -c 'ALTER DATABASE template0 ALLOW_CONNECTIONS false' postgres
printf "shared_preload_libraries = 'read_policy'\n" >> "$PGDATA/postgresql.conf"
if [ -f /build/databases/copy-roles.sql ]; then
    psql -v ON_ERROR_STOP=1 -q -f /build/databases/copy-roles.sql megasamples
fi
pg_ctl -w -m fast stop >/dev/null
SH
# Keep the packaging pass separate so changing it does not invalidate the bulk-load cache.
COPY engines/postgres/init/30-template-grants.sql engines/postgres/init/40-register-template.sql engines/postgres/init/99-trim-wal.sql /build/init/
RUN <<'SH'
#!/bin/bash
set -euo pipefail
export PGDATA
# Reclaim the bulk loader's recycled WAL through PostgreSQL itself before packaging. A short,
# private restart with a small WAL budget lets CHECKPOINT remove unneeded segments; no WAL files
# are deleted by hand, and command-line settings leave the shipped configuration unchanged.
pg_ctl -w -o "-c listen_addresses='' -c max_wal_size=64MB -c min_wal_size=32MB -c wal_level=minimal -c max_wal_senders=0" start >/dev/null
if [ -f /build/databases/templates.list ]; then
    while IFS= read -r name; do
        psql -v ON_ERROR_STOP=1 -q -f /build/init/30-template-grants.sql "$name"
        psql -v ON_ERROR_STOP=1 -v working="$name" -v template="${name}_start" -q \
            -f /build/init/40-register-template.sql megasamples
        psql -v ON_ERROR_STOP=1 -q -f /build/init/20-grants.sql "$name"
    done < /build/databases/templates.list
fi
psql -v ON_ERROR_STOP=1 -q -f /build/init/99-trim-wal.sql postgres
pg_ctl -w -m fast stop >/dev/null
printf '1\n' > "$PGDATA/megasamples-read-policy"
SH
USER root
RUN rm -rf /build

FROM ${POSTGRES_IMAGE}
LABEL org.opencontainers.image.title="sql-megasamples-postgres" \
      org.opencontainers.image.description="PostgreSQL 18 preloaded with well-known sample databases (sql-megasamples)" \
      org.opencontainers.image.licenses="MIT AND BSD-3-Clause AND CC-BY-SA-3.0"
COPY --from=policy-build /usr/lib/postgresql/18/lib/read_policy.so /usr/lib/postgresql/18/lib/read_policy.so
COPY --from=policy-build /usr/share/postgresql/18/extension/read_policy* /usr/share/postgresql/18/extension/
COPY engines/postgres/entrypoint-wrapper.sh /usr/local/bin/entrypoint-wrapper.sh
COPY --from=builder --chown=postgres:postgres /var/lib/postgresql/18/docker /var/lib/postgresql/18/docker
RUN chmod 700 /var/lib/postgresql/18/docker
COPY --from=builder /docs /usr/share/doc/megasamples
ENTRYPOINT ["entrypoint-wrapper.sh"]
EXPOSE 5432
CMD ["postgres"]
