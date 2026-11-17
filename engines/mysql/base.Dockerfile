# Oracle's server image currently bundles Innovation Shell 26.10. Replace the
# complete Shell payload with 9.7.1 from a second immutable Oracle-built input.
FROM docker.io/library/mysql:9.7.4@sha256:df90258da46f6e7ff8574ff84f17618aba0765cac749928299c69fd4e7cb8ad8 AS shell-lts
FROM container-registry.oracle.com/mysql/community-server:9.7.4@sha256:cb9cfddeccbbd9922bf927cd67bdb58067b357a1fc75d132988d1f5cc4cb17bb
USER root
RUN rpm -e --nodeps mysql-shell \
 && ln -s /entrypoint.sh /usr/local/bin/docker-entrypoint.sh \
 && mkdir -p /etc/mysql/conf.d \
 && printf '\n!includedir /etc/mysql/conf.d/\n' >> /etc/my.cnf
COPY --from=shell-lts /usr/bin/mysqlsh /usr/bin/mysql-secret-store-login-path /usr/bin/mysql-secret-store-secret-service /usr/bin/
COPY --from=shell-lts /usr/lib/mysqlsh /usr/lib/mysqlsh
COPY --from=shell-lts /usr/share/mysqlsh /usr/share/mysqlsh
COPY --from=shell-lts /usr/share/doc/mysql-shell /usr/share/doc/mysql-shell
RUN mysql --version | grep -F '9.7.4' \
 && mysqlsh --version | grep -F '9.7.1' \
 && mysqlsh --no-defaults --py -e 'import sys; print(sys.version)' \
 && ! ldd /usr/bin/mysqlsh | grep 'not found'
# Preserve the existing stack's fresh-volume and cold-backup behavior.
VOLUME ["/var/lib/mysql"]
