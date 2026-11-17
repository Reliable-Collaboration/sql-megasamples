FROM dbgate/dbgate:7.3.6@sha256:adb32bb7e0de948d1ffccbc9639014741e1f6d750f7fddd800af651777922953 AS driver
USER root
RUN apt-get update -qq && apt-get install -y --no-install-recommends build-essential python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/sqlite-driver
COPY driver/package.json driver/package-lock.json ./
# 13.2.0 is locked with its complete dependency graph and registry integrity hashes.
RUN npm ci --omit=dev --no-audit --no-fund \
 && node -e 'if(require("better-sqlite3/package.json").version!=="13.2.0")process.exit(1); new(require("better-sqlite3"))(":memory:").close()'
FROM dbgate/dbgate:7.3.6@sha256:adb32bb7e0de948d1ffccbc9639014741e1f6d750f7fddd800af651777922953
USER root
COPY --from=driver /opt/sqlite-driver /opt/sqlite-driver
RUN rm -rf /home/dbgate-docker/node_modules/better-sqlite3 \
 && ln -s /opt/sqlite-driver/node_modules/better-sqlite3 /home/dbgate-docker/node_modules/better-sqlite3
