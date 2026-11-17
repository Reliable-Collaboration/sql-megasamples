FROM node:24.22.3-bookworm-slim@sha256:dc26ae92c9fb15cf6b1d63e20f0944b2efe0f115b20e00be48fb23fceb061c54 AS node
FROM dbgate/dbgate:7.3.6@sha256:adb32bb7e0de948d1ffccbc9639014741e1f6d750f7fddd800af651777922953 AS runtime
USER root
# DbGate supports Node >=24; select the newest compatible LTS and rebuild native modules.
# Remove npm first: COPY merges directories and leaves incompatible old internals.
RUN rm -rf /usr/local/lib/node_modules/npm
COPY --from=node /usr/local/ /usr/local/
RUN apt-get update -qq && apt-get install -y --no-install-recommends libatomic1 \
 && rm -rf /var/lib/apt/lists/* \
 && test "$(node --version)" = v24.22.3
FROM runtime AS driver
RUN apt-get update -qq && apt-get install -y --no-install-recommends build-essential python3 ca-certificates libssl-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /home/dbgate-docker
RUN npm install-scripts approve cpu-features ssh2 \
 && npm rebuild cpu-features ssh2 --foreground-scripts --no-audit --no-fund \
 && node -e 'require("./node_modules/cpu-features/build/Release/cpufeatures.node"); require("./node_modules/ssh2/lib/protocol/crypto/build/Release/sshcrypto.node")'
WORKDIR /opt/sqlite-driver
COPY driver/package.json driver/package-lock.json ./
# 13.2.0 is locked with its complete dependency graph and registry integrity hashes.
RUN npm ci --omit=dev --no-audit --no-fund \
 && npm install-scripts approve better-sqlite3 \
 && npm rebuild better-sqlite3 --no-audit --no-fund \
 && node -e 'if(require("better-sqlite3/package.json").version!=="13.2.0")process.exit(1); new(require("better-sqlite3"))(":memory:").close()'
FROM runtime
COPY --from=driver /opt/sqlite-driver /opt/sqlite-driver
COPY --from=driver /home/dbgate-docker/node_modules/cpu-features /home/dbgate-docker/node_modules/cpu-features
COPY --from=driver /home/dbgate-docker/node_modules/ssh2 /home/dbgate-docker/node_modules/ssh2
RUN rm -rf /home/dbgate-docker/node_modules/better-sqlite3 \
 && ln -s /opt/sqlite-driver/node_modules/better-sqlite3 /home/dbgate-docker/node_modules/better-sqlite3
WORKDIR /home/dbgate-docker
