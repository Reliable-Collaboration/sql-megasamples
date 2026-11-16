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
FROM debian:13.7-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2

RUN apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cmake git ca-certificates sysbench default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

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
