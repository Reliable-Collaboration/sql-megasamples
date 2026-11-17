# Oracle's server image currently bundles Innovation Shell 26.10. Replace the
# complete Shell payload with 9.7.1 from a second immutable Oracle-built input.
FROM docker.io/library/mysql:9.7.4@sha256:df90258da46f6e7ff8574ff84f17618aba0765cac749928299c69fd4e7cb8ad8 AS shell-lts
FROM container-registry.oracle.com/mysql/community-server:9.7.4@sha256:cb9cfddeccbbd9922bf927cd67bdb58067b357a1fc75d132988d1f5cc4cb17bb AS native-tools
RUN microdnf install -y cpio && microdnf clean all \
 && curl -fL --retry 3 -o /tmp/client.rpm https://repo.mysql.com/yum/mysql-9.7-community/el/9/x86_64/mysql-community-client-9.7.4-1.el9.x86_64.rpm \
 && echo '669fe797e36ee181ecfe2d46146f6db0fdd4ea422991d2c9c0150fc65d87f59e  /tmp/client.rpm' | sha256sum -c - \
 && mkdir /native-tools && cd /native-tools \
 && rpm2cpio /tmp/client.rpm | cpio -idmu './usr/bin/mysqlbinlog' './usr/bin/mysql_config_editor' './usr/share/doc/mysql-community-client/*'
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
COPY --from=shell-lts /usr/lib/mysql/plugins /usr/lib/mysql/plugins
COPY --from=native-tools /native-tools/usr/bin/mysqlbinlog /native-tools/usr/bin/mysql_config_editor /usr/bin/
COPY --from=native-tools /native-tools/usr/share/doc/mysql-community-client /usr/share/doc/mysql-community-client
COPY --from=shell-lts /usr/share/man/man1/mysqlsh.1.gz /usr/share/man/man1/mysqlsh.1.gz
# Shell's external binutils use the server's newest 9.7 patch, not older bundled copies.
RUN mkdir -p /usr/libexec/mysqlsh \
 && ln -sf /usr/bin/mysqlbinlog /usr/libexec/mysqlsh/mysqlbinlog \
 && ln -sf /usr/bin/mysql_config_editor /usr/libexec/mysqlsh/mysql_config_editor \
 && /usr/libexec/mysqlsh/mysqlbinlog --version | grep -F '9.7.4' \
 && /usr/libexec/mysqlsh/mysql_config_editor --version | grep -F '9.7.4' \
 && test -f /usr/lib/mysql/plugins/authentication_oci_client.so
RUN mysql --version | grep -F '9.7.4' \
 && mysqlsh --version | grep -F '9.7.1' \
 && mysqlsh --no-defaults --py -e 'import sys; print(sys.version)' \
 && ! ldd /usr/bin/mysqlsh | grep 'not found'
# Preserve the existing stack's fresh-volume and cold-backup behavior.
VOLUME ["/var/lib/mysql"]
