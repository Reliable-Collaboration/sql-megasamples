# The build-time loader image (deferred until something actually needed it --
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
FROM container-registry.oracle.com/mysql/community-server:9.7.4@sha256:cb9cfddeccbbd9922bf927cd67bdb58067b357a1fc75d132988d1f5cc4cb17bb AS mysql-client

FROM debian:13.7-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2

RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates curl libssl-dev libncurses6 libz-dev \
    && rm -rf /var/lib/apt/lists/*

# Oracle's matching clients replace Debian's MariaDB command aliases. These
# binaries link to the system OpenSSL/ncurses/zlib ABI, verified in the build.
COPY --from=mysql-client /usr/bin/mysql /usr/bin/mysqldump /usr/bin/mysqladmin /usr/local/bin/
RUN mysql --version | grep -F '9.7.4' && mysqldump --version | grep -F '9.7.4'

# Oracle libmysqlclient follows the same 9.7 LTS patch as the server.
RUN apt-get update -qq && apt-get install -y --no-install-recommends autoconf automake libtool pkg-config libaio-dev libluajit-5.1-dev libck-dev \
 && rm -rf /var/lib/apt/lists/*
RUN curl -fL --retry 3 -o /tmp/client.deb https://repo.mysql.com/apt/debian/pool/mysql-9.7-lts/m/mysql-community/libmysqlclient-dev_9.7.4-1debian13_amd64.deb \
 && echo '1f012077e30d0bb3b883beb0d3bf243237f066071fd96ed545eb65644ef64ea1  /tmp/client.deb' | sha256sum -c - \
 && dpkg-deb -x /tmp/client.deb / && rm /tmp/client.deb
RUN curl -fL --retry 3 -o /tmp/client.deb https://repo.mysql.com/apt/debian/pool/mysql-9.7-lts/m/mysql-community/libmysqlclient24_9.7.4-1debian13_amd64.deb \
 && echo '90388cd01e273002d345a39e79a18da165b28249e639672e482858fa262fe6b7  /tmp/client.deb' | sha256sum -c - \
 && dpkg-deb -x /tmp/client.deb / && rm /tmp/client.deb
# Rebuild the existing sysbench release against Oracle C API; no ABI aliasing.
RUN curl -fL --retry 3 -o /tmp/sysbench.tar.gz https://deb.debian.org/debian/pool/main/s/sysbench/sysbench_1.0.20+ds.orig.tar.gz \
 && echo '9a2d8f1b7474d7956ec6ca69301ed0e4f916295d2d7d400f0622caf8c0c34da7  /tmp/sysbench.tar.gz' | sha256sum -c - \
 && mkdir /tmp/sysbench && tar -xzf /tmp/sysbench.tar.gz -C /tmp/sysbench --strip-components=1 \
 && curl -fL --retry 3 -o /tmp/debian.tar.xz https://deb.debian.org/debian/pool/main/s/sysbench/sysbench_1.0.20+ds-7.debian.tar.xz \
 && echo '9add3bdd0edd34c936a479448106683fa9da2f611d995266ad32a33875ec4a06  /tmp/debian.tar.xz' | sha256sum -c - \
 && tar -xJf /tmp/debian.tar.xz -C /tmp/sysbench \
 && cd /tmp/sysbench && patch -p1 < debian/patches/01_dont_require_third_party.diff \
 && autoreconf -fi \
 && ./configure --with-mysql --without-pgsql --with-system-luajit --with-system-ck \
 && make -j4 && make install \
 && ldconfig \
 && test "$(mysql_config --version)" = 9.7.4 \
 && ldd /usr/local/bin/sysbench | grep libmysqlclient \
 && ! ldd /usr/local/bin/sysbench | grep libmariadb \
 && rm -rf /tmp/sysbench /tmp/sysbench.tar.gz /tmp/debian.tar.xz

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
