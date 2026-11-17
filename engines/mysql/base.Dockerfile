# Oracle's server image currently bundles Innovation Shell 26.10. Replace the
# complete Shell payload with 9.7.1 from a second immutable Oracle-built input.
FROM docker.io/library/mysql:9.7.4@sha256:df90258da46f6e7ff8574ff84f17618aba0765cac749928299c69fd4e7cb8ad8 AS shell-lts
# Shell links the CPython 3.13 ABI. Patch that runtime, including its native
# extensions and stdlib, without transplanting an incompatible Python minor.
RUN microdnf install -y gcc make tar gzip xz pkgconf-pkg-config zlib-devel openssl-devel bzip2-devel libffi-devel xz-devel readline-devel ncurses-devel libuuid-devel \
 && microdnf clean all
RUN curl -fL --retry 3 -o /tmp/sqlite.tar.gz https://sqlite.org/2026/sqlite-autoconf-3540100.tar.gz \
 && test "$(openssl dgst -sha3-256 /tmp/sqlite.tar.gz | awk '{print $NF}')" = b6ced585c750916b1052667239a12c25a7ff34e7f06e1e6e01ecb0427657d9c4 \
 && tar -xzf /tmp/sqlite.tar.gz -C /tmp \
 && cd /tmp/sqlite-autoconf-3540100 \
 && ./configure --prefix=/usr/lib/mysqlsh --enable-fts5 --disable-readline \
 && make -j4 && make install \
 && cp sqlite3.h /usr/share/doc/mysql-shell/SQLite-3.54.1.h
RUN curl -fL --retry 3 -o /tmp/python.tar.xz https://www.python.org/ftp/python/3.13.18/Python-3.13.18.tar.xz \
 && echo 'abb0102e6d4ae027509bcb82327d9dd85515b44a3ba8ad538cfc5e9847029f68  /tmp/python.tar.xz' | sha256sum -c - \
 && tar -xJf /tmp/python.tar.xz -C /tmp \
 && mv /usr/lib/mysqlsh/lib/python3.13/site-packages /tmp/shell-site-packages \
 && rm -rf /usr/lib/mysqlsh/lib/python3.13 /usr/lib/mysqlsh/include/python3.13 /usr/lib/mysqlsh/lib/python313.zip \
 && rm -f /usr/lib/mysqlsh/libpython3.13.so* /usr/lib/mysqlsh/lib/libpython3.13.so* \
 && cd /tmp/Python-3.13.18 \
 && CPPFLAGS=-I/usr/lib/mysqlsh/include \
    LDFLAGS='-L. -L/usr/lib/mysqlsh/lib -Wl,-rpath,/usr/lib/mysqlsh -Wl,-rpath,/usr/lib/mysqlsh/lib' \
    PKG_CONFIG_PATH=/usr/lib/mysqlsh/lib/pkgconfig \
    ./configure --prefix=/usr/lib/mysqlsh --enable-shared --with-ensurepip=no --disable-test-modules \
 && make -j4 libpython3.13.so \
 && cp libpython3.13.so.1.0 /usr/lib/mysqlsh/libpython3.13.so.1.0 \
 && make -j4 && make altinstall \
 && cp libpython3.13.so.1.0 /usr/lib/mysqlsh/libpython3.13.so.1.0 \
 && cp LICENSE /usr/share/doc/mysql-shell/Python-3.13.18.LICENSE \
 && cp -a /tmp/shell-site-packages/. /usr/lib/mysqlsh/lib/python3.13/site-packages/ \
 && readelf -d /usr/lib/mysqlsh/bin/python3.13 /usr/lib/mysqlsh/libpython3.13.so.1.0 /usr/lib/mysqlsh/lib/python3.13/lib-dynload/_sqlite3*.so > /usr/share/doc/mysql-shell/runtime-elf.txt \
 && ! grep -E '(RPATH|RUNPATH).*/tmp' /usr/share/doc/mysql-shell/runtime-elf.txt \
 && mysqlsh --no-defaults --py -e 'import platform,sqlite3,ssl,bz2,lzma,ctypes; assert platform.python_version() == "3.13.18"; assert sqlite3.sqlite_version == "3.54.1"; print(platform.python_version(),sqlite3.sqlite_version,ssl.OPENSSL_VERSION)' \
 && rm -rf /tmp/sqlite* /tmp/Python* /tmp/python.tar.xz /tmp/shell-site-packages
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
 && mysqlsh --no-defaults --py -e 'import platform,sqlite3,ssl,bz2,lzma,ctypes; assert platform.python_version() == "3.13.18"; assert sqlite3.sqlite_version == "3.54.1"; print(platform.python_version(),sqlite3.sqlite_version,ssl.OPENSSL_VERSION)' \
 && ! ldd /usr/bin/mysqlsh | grep 'not found'
# Preserve the existing stack's fresh-volume and cold-backup behavior.
VOLUME ["/var/lib/mysql"]
