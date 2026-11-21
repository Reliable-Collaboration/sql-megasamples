# syntax=docker/dockerfile:1.29.0@sha256:572cebbc2b15e6f84c077742952674889cb63cd5e9b80abdffcbe587b6f19183
# Build the vendor's released SQLite rather than depending on a distribution package's version.
# Source and SHA3-256: https://sqlite.org/download.html, read 2026-11-16 18:44 UTC.
ARG ALPINE_IMAGE=alpine:3.24.4@sha256:f59abe656b692d901e184be3445e084786602108599d2a51d229c0f5a48c71bf
FROM ${ALPINE_IMAGE} AS builder
RUN apk add --no-cache build-base curl openssl
RUN set -eu; \
    curl -fSL https://sqlite.org/2026/sqlite-autoconf-3540100.tar.gz -o /tmp/sqlite.tar.gz; \
    test "$(openssl dgst -sha3-256 /tmp/sqlite.tar.gz | awk '{print $NF}')" = b6ced585c750916b1052667239a12c25a7ff34e7f06e1e6e01ecb0427657d9c4; \
    tar -xzf /tmp/sqlite.tar.gz -C /tmp; \
    cd /tmp/sqlite-autoconf-3540100; \
    ./configure --prefix=/usr/local --enable-fts5 --disable-readline; \
    make -j4; make install DESTDIR=/out; \
    test "$(/out/usr/local/bin/sqlite3 ':memory:' 'select sqlite_version()')" = 3.54.1
FROM ${ALPINE_IMAGE}
COPY --from=builder /out/usr/local/bin/sqlite3 /usr/local/bin/sqlite3
COPY --from=builder /out/usr/local/lib/libsqlite3.so* /usr/local/lib/
LABEL org.opencontainers.image.title="sql-megasamples-sqlite" \
      org.opencontainers.image.description="Sample SQLite databases with SQLite 3.54.1" \
      org.opencontainers.image.licenses="MIT AND BSD-3-Clause AND CC-BY-SA-3.0"
COPY NOTICE.md LICENSES.md CATALOGUE.md README.md /usr/share/doc/megasamples/
COPY engines/images.lock.yaml /usr/share/doc/megasamples/images.lock.yaml
COPY datasets/ /usr/share/doc/megasamples/datasets/
COPY build/sqlite/image/data/ /data/
COPY build/sqlite/image/templates/ /templates/
VOLUME /data
WORKDIR /data
CMD ["sleep", "infinity"]
