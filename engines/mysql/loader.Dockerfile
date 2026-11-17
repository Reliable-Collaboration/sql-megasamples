# The build-time loader image (PLAN.md task P-04, deferred until something actually needed it --
# which is now: SSB has to compile dbgen from source, and TPC-C needs sysbench).
#
# Nothing here reaches the published MySQL image. This container compiles or drives generators and
# writes their output to a mounted directory; it is removed afterwards.
#
# Pinned by digest rather than by tag. On this machine the Docker daemon cannot pull from the
# registry over its own network stack -- the blob CDN answers with a bare EOF, the IPv6 signature
# the runbook puts first -- so the base image is fetched by `megasamples/pull_image.py` over IPv4 and
# referenced here by the digest that produced. Container networking itself is fine: apt and git
# both work from inside.
FROM docker.io/library/mysql:26.10.0@sha256:b401608b19ffafbc6aa3d84523acf783078c8cf01e0f7ee1dc3ca75a5701a999 AS mysql-client

FROM debian:13.7-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2

RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates curl libssl-dev libncurses6 libz-dev sysbench=1.0.20+ds-7 \
    && rm -rf /var/lib/apt/lists/*

# Oracle's matching clients replace Debian's MariaDB command aliases. These
# binaries link to the system OpenSSL/ncurses/zlib ABI, verified in the build.
COPY --from=mysql-client /usr/bin/mysql /usr/bin/mysqldump /usr/bin/mysqladmin /usr/local/bin/
RUN mysql --version | grep -F '26.10.0' && mysqldump --version | grep -F '26.10.0'

# sysbench uses the latest stable MariaDB Connector/C, independently of Debian's
# older server-derived libmariadb3 package. Verify the vendor source checksum.
RUN curl -fL --retry 3 -o /tmp/connector.tar.gz https://archive.mariadb.org/connector-c-3.4.11/mariadb-connector-c-3.4.11-src.tar.gz \
 && echo '521c0712e9291fa96558df9e2ff431376a3a79329f13751896b694cae12765b4  /tmp/connector.tar.gz' | sha256sum -c - \
 && mkdir /tmp/connector && tar -xzf /tmp/connector.tar.gz -C /tmp/connector --strip-components=1 \
 && cmake -S /tmp/connector -B /tmp/connector/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local -DINSTALL_LIBDIR=lib -DWITH_UNIT_TESTS=OFF -DWITH_CURL=OFF -DWITH_SSL=OPENSSL \
 && cmake --build /tmp/connector/build --parallel 4 \
 && cmake --install /tmp/connector/build \
 && rm -rf /tmp/connector /tmp/connector.tar.gz
ENV LD_LIBRARY_PATH=/usr/local/lib:/usr/local/lib/mariadb
RUN test "$(mariadb_config --cc_version)" = 3.4.11 \
 && ldd /usr/bin/sysbench | grep -E 'libmariadb.*=> /usr/local/'

# SSB's generator is a fork of TPC-H's dbgen. No fork carries a LICENSE file, and the sources keep
# the TPC SCCS ids, so the TPC EULA governs it as a modified dbgen: it is cloned and built here at
# build time and never vendored into this repository.
ARG SSB_DBGEN_COMMIT=ae1e254aa4d603d8ef1f44078e5abed011634b23
RUN git clone --quiet https://github.com/eyalroz/ssb-dbgen.git /opt/ssb-dbgen \
    && cd /opt/ssb-dbgen \
    && git checkout --quiet "$SSB_DBGEN_COMMIT" \
    && git rev-parse HEAD > /opt/ssb-dbgen-commit.txt \
    && cmake -B build -DEOL_HANDLING=ON -DYMD_DASH_DATE=ON -Wno-dev >/dev/null \
    && cmake --build build --parallel >/dev/null \
    && cp build/dbgen /usr/local/bin/ssb-dbgen \
    && cp dists.dss /opt/dists.dss

# sysbench-tpcc is Lua only; nothing is compiled.
# the commit knowledge/decisions/tpcc-implementation-choice.md names, in full
ARG SYSBENCH_TPCC_COMMIT=f110afa8023c7924b1ba00177232a9090624acb5
RUN git clone --quiet https://github.com/Percona-Lab/sysbench-tpcc.git /opt/sysbench-tpcc \
    && cd /opt/sysbench-tpcc \
    && git checkout --quiet "$SYSBENCH_TPCC_COMMIT" \
    && git rev-parse HEAD > /opt/sysbench-tpcc-commit.txt

WORKDIR /work
