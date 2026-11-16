# Live database upgrade (coordinator only)

This procedure is written for the coordinator. It has **not been executed** against the live deployment. Do not execute until the upgrade PR has merged, its evidence covers the required datasets, and the DataIntent suites pass against the isolated endpoints. Keep the two existing socket-proxy services unchanged.

The isolated build uses `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/env.sh`. The live commands below deliberately use the default rootless Podman store instead. Run them only in the coordinator's live maintenance session. Never run them from the isolated validation shell.

## Prepare while the live servers are still running

Quiesce DataIntent writers before the final backups and cutover. Keep its clients paused through verification. Building from upstream can take much longer than the outage; finish it before stopping the live servers. The previous core build documented in README took approximately twenty minutes; the full manifest includes much larger datasets. No full-manifest outage duration has been established.

```sh
set -eu
unset CONTAINERS_STORAGE_CONF CONTAINERS_CONF CONTAINERS_CONF_OVERRIDE DOCKER_HOST COMPOSE_PROJECT_NAME
export COMPOSE_PROJECT_NAME=sql-megasamples
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
cd /home/rcc-vstudio/working/sql-megasamples
UPGRADE_ID=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$PWD/build/live-upgrade-backups/$UPGRADE_ID"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
git status --porcelain > "$BACKUP_DIR/git-status.txt"
test ! -s "$BACKUP_DIR/git-status.txt"  # resolve local edits before proceeding
# Preserve both the original branch and the exact commit; never reset or delete the branch.
git branch --show-current > "$BACKUP_DIR/original-branch.txt"
git rev-parse HEAD > "$BACKUP_DIR/original-commit.txt"
cp megasamples.yaml "$BACKUP_DIR/"
cp compose.yaml "$BACKUP_DIR/"
if test -f .env; then cp .env "$BACKUP_DIR/"; fi
# The existing Docker client uses this default-store socket, not the isolated socket.
MEGASAMPLES_LIVE_API_PID=
if ! test -S "${DOCKER_HOST#unix://}"; then
  podman system service --time=0 "$DOCKER_HOST" > "$BACKUP_DIR/api-service.log" 2>&1 &
  MEGASAMPLES_LIVE_API_PID=$!
  for attempt in $(seq 1 50); do
    test -S "${DOCKER_HOST#unix://}" && break
    sleep 0.2
  done
fi
docker version --format '{{.Server.Version}}'
podman inspect megasamples-postgres megasamples-mysql megasamples-sqlite > "$BACKUP_DIR/containers.json"
chmod 600 "$BACKUP_DIR/containers.json"
for engine in postgres mysql sqlite; do
  podman image tag "$(podman inspect -f '{{.Image}}' "megasamples-$engine")" \
    "localhost/sql-megasamples-$engine:rollback-$UPGRADE_ID"
done
# Save the images as well as tagging them, so rollback survives an accidental image cleanup.
podman save -o "$BACKUP_DIR/rollback-images.tar" \
  "localhost/sql-megasamples-postgres:rollback-$UPGRADE_ID" \
  "localhost/sql-megasamples-mysql:rollback-$UPGRADE_ID" \
  "localhost/sql-megasamples-sqlite:rollback-$UPGRADE_ID"

git fetch origin
git switch main
git merge --ff-only origin/main
git rev-parse HEAD > "$BACKUP_DIR/upgrade-commit.txt"
# Verify this is the reviewed upgrade, not just an arbitrary newer main.
MEGASAMPLES_PY=python3
if test -x .venv/bin/python; then MEGASAMPLES_PY="$PWD/.venv/bin/python"; fi
"$MEGASAMPLES_PY" -m pytest -q tests/test_versions.py
make check PY="$MEGASAMPLES_PY"
# Preserve the live configuration and credentials. Do not copy the isolated ports into this file.
# Rebuild the datasets and images in the live store while the current tagged containers keep running.
# This does not upgrade their data directories in place.
make run
make test-image
```

`make run` must complete with every configured dataset included. A missing download is a failure. Supply the manually obtained Lahman archive through the documented fetch workflow. WideWorldImporters requires the executor's explicit SQL Server Developer EULA acceptance and `make wwi-export` before its conversion. Do not accept a partial build as the live release. Read `docs/engine-upgrade-evidence.md` for exact validation coverage and unresolved inputs.

## Final backups and cutover

The files in `containers.json` include environment credentials: restrict access, do not paste them into tickets. Take logical backups while quiesced, then cold-copy each data directory. Rollback uses the cold copies with the original engine images; never open a new-version data directory with an old binary.

```sh
# BACKUP_DIR and UPGRADE_ID are the values from the preparation shell.
# Keep logical backups for inspection/recovery; credentials stay inside the container.
podman exec megasamples-postgres sh -c \
  'exec pg_dumpall -U postgres' > "$BACKUP_DIR/postgres.sql"
podman exec megasamples-mysql sh -c \
  'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysqldump -uroot --all-databases --routines --events --triggers --single-transaction --hex-blob' \
  > "$BACKUP_DIR/mysql.sql"
chmod 600 "$BACKUP_DIR/"*.sql

# Downtime starts here. SQLite consumers must be stopped before copying its files.
# Stop every configured console as well as all engines; keep the proxy services running.
docker compose -p sql-megasamples -f compose.yaml stop
for engine in postgres mysql sqlite; do
  mkdir -p "$BACKUP_DIR/$engine"
done
podman cp megasamples-postgres:/var/lib/postgresql/. "$BACKUP_DIR/postgres/"
podman cp megasamples-mysql:/var/lib/mysql/. "$BACKUP_DIR/mysql/"
podman cp megasamples-sqlite:/data/. "$BACKUP_DIR/sqlite/"
# Preserve the SQLite console volume separately, including any changed files.
podman cp megasamples-sqlite:/shared/. "$BACKUP_DIR/sqlite-shared/"
# Record and retain old anonymous volumes. Do not run down -v, reset, prune or clean-all.
podman volume ls --format json > "$BACKUP_DIR/volumes.json"

# make up detects a changed image and renews anonymous data volumes for the three engines.
# A replacement is the newly built sample corpus; application writes remain in the backups.
make up
make test-console
```

The Compose stop above includes every configured console, so SQLite consumers are closed before either copy. `make up` restarts configured consoles. The new containers receive the existing `.env` credentials. Do not print that file.

The outage lasts from the first stop through readiness and verification, plus any rollback. Reserve a maintenance window; measured isolated timings belong in the evidence report, not an assumed SLA. Rebuilding before cutover avoids putting download/conversion time in the outage.

## Verify before resuming clients

```sh
podman ps --format '{{.Names}} {{.Status}} {{.Ports}}'
podman exec megasamples-postgres psql -U postgres -Atc 'SHOW server_version'
podman exec megasamples-mysql sh -c \
  'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; mysql -uroot -N -e "SELECT VERSION()"'
podman exec megasamples-sqlite sqlite3 :memory: 'SELECT sqlite_version()'
podman exec megasamples-postgres psql -U postgres -d megasamples -Atc \
  'SELECT name,row_counts FROM datasets ORDER BY name'
podman exec megasamples-mysql sh -c \
  'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; mysql -uroot -N -e "SELECT name,row_counts FROM megasamples.datasets ORDER BY name"'
podman exec megasamples-sqlite sqlite3 /data/megasamples.sqlite \
  'SELECT name,row_counts FROM datasets ORDER BY name'
```

Compare the complete registry sets and each table's actual row counts with the validated configuration and catalogue. Registry text alone is not an actual count check. Run the repository's image tests before cutover and the same validation queries against the replacement servers afterwards. Live-feed counts/checksums must match the hub snapshot built with these images; historical manifest counts are floors for those feeds. Verify `demo` remains read-only and `admin` can write using disposable probe tables, then remove the probes.

Confirm PostgreSQL binds to `127.0.0.1:5432` and MySQL to `127.0.0.1:3306`. Run the coordinator's DataIntent server-bound suites against both the local endpoints and the existing forwarded endpoints `10.0.0.172:5432` and `10.0.0.172:3306`. The proxies continue forwarding to the same local ports and require no changes. Resume clients only after these checks pass.

## Roll back

Keep clients paused. Do not remove any backup, original image tag, original branch, original anonymous volume, or proxy service.

```sh
# Restore original configuration and its original branch (never reset a pushed branch).
make down                         # no -v: retained volumes remain available
ORIGINAL_BRANCH=$(cat "$BACKUP_DIR/original-branch.txt")
git switch "$ORIGINAL_BRANCH"
cp "$BACKUP_DIR/megasamples.yaml" ./megasamples.yaml
cp "$BACKUP_DIR/compose.yaml" ./compose.yaml
if test -f "$BACKUP_DIR/.env"; then cp "$BACKUP_DIR/.env" ./.env; fi
podman load -i "$BACKUP_DIR/rollback-images.tar"
```

For exact preservation of application writes, create three **new** named rollback volumes, populate them from the cold copies while no database has them open, and attach them to the original image IDs. Use a Compose override, leaving original volumes untouched:

```sh
for engine in postgres mysql sqlite; do
  podman volume create "megasamples-rollback-$engine-$UPGRADE_ID"
done
# podman unshare preserves ownership from the cold copies in rootless Podman's namespace.
for engine in postgres mysql sqlite; do
  target=$(podman volume inspect -f '{{.Mountpoint}}' "megasamples-rollback-$engine-$UPGRADE_ID")
  podman unshare cp -a "$BACKUP_DIR/$engine/." "$target/"
done
# PostgreSQL's backup above includes the 18/docker path under /var/lib/postgresql.
cat > "$BACKUP_DIR/rollback.override.yaml" <<YAML
services:
  postgres:
    image: localhost/sql-megasamples-postgres:rollback-$UPGRADE_ID
    volumes:
      - rollback-postgres:/var/lib/postgresql
  mysql:
    image: localhost/sql-megasamples-mysql:rollback-$UPGRADE_ID
    volumes:
      - rollback-mysql:/var/lib/mysql
  sqlite:
    image: localhost/sql-megasamples-sqlite:rollback-$UPGRADE_ID
    volumes:
      - rollback-sqlite:/data
volumes:
  rollback-postgres:
    external: true
    name: megasamples-rollback-postgres-$UPGRADE_ID
  rollback-mysql:
    external: true
    name: megasamples-rollback-mysql-$UPGRADE_ID
  rollback-sqlite:
    external: true
    name: megasamples-rollback-sqlite-$UPGRADE_ID
YAML
# Use the host's existing Docker-compatible socket and Compose client, targeting the default store.
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
docker compose -p sql-megasamples -f compose.yaml -f "$BACKUP_DIR/rollback.override.yaml" up -d --wait
```

If that default socket is absent, start a Podman API service for the **default** store in the coordinator's session before the Compose command. This is separate from the isolated build's service. The SQLite service's original startup command republishes `/data` into its shared console volume; keep SQLite consoles stopped until that copy finishes. Repeat version, actual row-count, account and DataIntent endpoint checks against the restored stack, including the forwarded endpoints. Resume clients only after rollback validation succeeds. Record the failed upgrade and retain its data directories separately for diagnosis.

## Isolation used for rehearsal

The rehearsal's settings and generated credentials are in the upgrade clone's `megasamples.yaml` and `.env` (mode 0600). Its socket is `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock`, project `megasamples-upgrade`; ports are PostgreSQL `127.0.0.1:15432`, MySQL `127.0.0.1:13306`, and consoles `127.0.0.1:18080` through `:18084`. It uses the isolated `slirp4netns` override under `build/upgrade-evidence/containers-slirp.conf` because Pasta failed to access the custom runroot's network namespace. Source `env.sh` and set `CONTAINERS_CONF_OVERRIDE` to that absolute file before starting its socket. The isolated API process can be stopped without stopping its running containers; start it again to use Docker Compose or the repository's commands. None of these settings belongs in the live checkout.

After successful cutover or rollback, if this maintenance shell started an API process, stop only that process (the stack keeps running):

```sh
if test -n "${MEGASAMPLES_LIVE_API_PID:-}"; then
  kill "$MEGASAMPLES_LIVE_API_PID"
fi
```
