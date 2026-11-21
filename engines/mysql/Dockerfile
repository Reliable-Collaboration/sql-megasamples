# syntax=docker/dockerfile:1.29.0@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183
# sql-megasamples-mysql: MySQL LTS with sample databases baked into the data directory.
# The builder initialises a data directory, loads each configured dataset from its MySQL Shell dump,
# creates the accounts and the provenance registry, and shuts down cleanly; the final stage carries
# only that directory. Build context: the repository root, filtered by .dockerignore; the dumps and
# registry come from build/mysql/image/, which `megasamples image` fills with exactly the datasets
# being baked. See ARCHITECTURE.md section 4.
ARG MYSQL_IMAGE=sql-megasamples-mysql-base:9.7.4-shell-9.7.1

FROM ${MYSQL_IMAGE} AS builder
COPY engines/mysql/my.cnf /etc/mysql/conf.d/megasamples.cnf
COPY engines/mysql/init/ /build/init/
COPY build/mysql/image/registry.sql /build/init/10-registry.sql
COPY megasamples/mysql_templates.py megasamples/mysql_template_build.py build/mysql/image/copy-settings.json /build/init/
COPY build/mysql/image/dumps/ /build/mysql/dumps/
# The attribution has to travel with the data: several licences here require it inside any
# redistribution, and an image is a redistribution (ARCHITECTURE.md section 8).
# /docs, not /build: the builder's last act is `rm -rf /build`
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
RUN <<'SH'
set -eu
S=/var/run/mysqld/mysqld.sock
mysqld --initialize-insecure --user=mysql
# util.loadDump uses LOAD DATA LOCAL INFILE, so local_infile must be ON for the import.
mysqld --user=mysql --daemonize --skip-networking --local-infile=1 \
       --socket=$S --pid-file=/var/run/mysqld/mysqld.pid
for i in $(seq 1 60); do mysql -S $S -uroot -e 'SELECT 1' >/dev/null 2>&1 && break; sleep 1; done

mysql -S $S -uroot -e "ALTER INSTANCE DISABLE INNODB REDO_LOG"
for dir in /build/mysql/dumps/*/; do
  mysqlsh --no-defaults -S $S -uroot --no-password --py \
    -e "util.load_dump('${dir}', {'deferTableIndexes': 'all', 'threads': 4, 'showProgress': False, 'skipBinlog': True})"
done
mysql -S $S -uroot -e "ALTER INSTANCE ENABLE INNODB REDO_LOG"

# CONVERT_TZ() needs the time-zone tables, which the entrypoint would normally load; it never runs
# here because the shipped data directory is already initialised.
mysql_tzinfo_to_sql /usr/share/zoneinfo 2>/dev/null | mysql -S $S -uroot mysql

# Accounts LAST: 00-users.sql gives root@localhost a password, so everything after it must
# authenticate. Running it earlier fails the rest of the stage (found at P-03).
mysql -S $S -uroot < /build/init/00-users.sql
umask 077
printf '[client]\nuser=root\npassword=root\n' > /build/local.cnf
mysql --defaults-extra-file=/build/local.cnf -S $S < /build/init/10-registry.sql
cd /build/init
printf 'root\n' | mysqlsh --no-defaults -S $S -uroot --passwords-from-stdin --py \
    --file mysql_template_build.py copy-settings.json
mysqladmin --defaults-extra-file=/build/local.cnf -S $S shutdown
rm /var/lib/mysql/auto.cnf
rm -rf /build
SH

FROM ${MYSQL_IMAGE}
LABEL org.opencontainers.image.title="sql-megasamples-mysql" \
      org.opencontainers.image.description="MySQL 9.7 LTS preloaded with well-known sample databases (sql-megasamples)" \
      org.opencontainers.image.licenses="MIT AND BSD-3-Clause AND CC-BY-SA-3.0"
COPY engines/mysql/my.cnf /etc/mysql/conf.d/megasamples.cnf
COPY build/mysql/image/copy-mode.cnf /etc/mysql/conf.d/megasamples-copy-mode.cnf
COPY engines/mysql/entrypoint-wrapper.sh /usr/local/bin/entrypoint-wrapper.sh
COPY --from=builder --chown=mysql:mysql /var/lib/mysql /var/lib/mysql
COPY --from=builder /docs /usr/share/doc/megasamples
ENTRYPOINT ["entrypoint-wrapper.sh"]
EXPOSE 3306 33060
CMD ["mysqld"]
