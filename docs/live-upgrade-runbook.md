# Live engines, clients and consoles upgrade (coordinator only)

This procedure is written for the coordinator. It has **not been executed** against the live deployment. Do not execute until the engine, client and owner-approved dataset PRs have merged, their evidence covers the configured datasets, and the DataIntent suites pass against the isolated endpoints. Keep the two existing socket-proxy services unchanged. The owner authorized the BTS refresh and accepted the SQL Server Developer EULA for the isolated WWI export on 2026-11-17. Loading these three datasets is part of this upgrade, on the engines that passed the dataset receipt. Oracle native verification remains **Not run, pending the owner's decision on Oracle's Free Use Terms**; do not accept those terms.

The isolated build uses `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/env.sh`. The live commands below deliberately use the default rootless Podman store instead. Run them only in the coordinator's live maintenance session. Never run them from the isolated validation shell.

The current dataset candidate has a recorded blocker: MySQL full-image cold readiness was
49.0 seconds against 30 seconds, and SQLite cold readiness was 38.2 seconds against 30 seconds.
Both gates are unchanged. Data/reset/console validation Passed, but these failures keep the dataset PR open. Resolve and rerun the gate before merging or live cutover;
the procedure below does not authorize bypassing it.

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
# Older branches tracked this generated credential page. Back it up privately, never commit it.
if test -f consoles/landing/adminer.html; then
  cp consoles/landing/adminer.html "$BACKUP_DIR/adminer.generated.html"
  chmod 600 "$BACKUP_DIR/adminer.generated.html"
fi
git status --porcelain -- . ':(exclude)consoles/landing/adminer.html' > "$BACKUP_DIR/git-status.txt"
test ! -s "$BACKUP_DIR/git-status.txt"  # resolve other local edits before proceeding
# Preserve both the original branch and the exact commit; never reset or delete the branch.
git branch --show-current > "$BACKUP_DIR/original-branch.txt"
git rev-parse HEAD > "$BACKUP_DIR/original-commit.txt"
# main may advance during preparation. Retain an immutable rollback branch instead of rewinding it.
ROLLBACK_BRANCH="rollback/live-$UPGRADE_ID"
git branch "$ROLLBACK_BRANCH" "$(git rev-parse HEAD)"
printf '%s\n' "$ROLLBACK_BRANCH" > "$BACKUP_DIR/rollback-branch.txt"
cp -a consoles "$BACKUP_DIR/consoles"
cp pyproject.toml uv.lock "$BACKUP_DIR/"
if test -d .venv; then cp -a .venv "$BACKUP_DIR/python-venv"; fi
# Also retain the original tooling/container invocation privately for any post-rollback build work.
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
# Record the original running set; a console absent before the upgrade stays absent on rollback.
docker compose -p sql-megasamples -f compose.yaml ps --services --status running \
  > "$BACKUP_DIR/original-running-services.txt"
# CloudBeaver keeps its workspace in the container's writable layer in this deployment.
# Retain it privately before any client-image or catalogue refresh; stop it for a consistent copy.
if podman container exists megasamples-cloudbeaver; then
  CB_WAS_RUNNING=$(podman inspect -f '{{.State.Running}}' megasamples-cloudbeaver)
  if test "$CB_WAS_RUNNING" = true; then podman stop megasamples-cloudbeaver; fi
  podman cp megasamples-cloudbeaver:/opt/cloudbeaver/workspace "$BACKUP_DIR/cloudbeaver-workspace"
  chmod 700 "$BACKUP_DIR/cloudbeaver-workspace"
  if test "$CB_WAS_RUNNING" = true; then podman start megasamples-cloudbeaver; fi
fi
: > "$BACKUP_DIR/rollback-image-tags.txt"
for service in postgres mysql sqlite landing cloudbeaver dbgate adminer phpmyadmin; do
  if podman container exists "megasamples-$service"; then
    test "$(podman inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "megasamples-$service")" = sql-megasamples
    tag="localhost/sql-megasamples-$service:rollback-$UPGRADE_ID"
    podman image tag "$(podman inspect -f '{{.Image}}' "megasamples-$service")" "$tag"
    printf '%s\n' "$tag" >> "$BACKUP_DIR/rollback-image-tags.txt"
  fi
done
# Preserve source-side client tools as well; these names are used by this repository.
: > "$BACKUP_DIR/original-tool-images.txt"
while read -r key reference; do
  if podman image exists "$reference"; then
    tag="localhost/sql-megasamples-$key:rollback-$UPGRADE_ID"
    podman image tag "$(podman image inspect -f '{{.Id}}' "$reference")" "$tag"
    printf '%s\n' "$tag" >> "$BACKUP_DIR/rollback-image-tags.txt"
    printf '%s %s\n' "$reference" "$tag" >> "$BACKUP_DIR/original-tool-images.txt"
  fi
done <<TOOL_IMAGES
loader sql-megasamples-loader:dev
oracle-source ${ORACLE_IMAGE:-gvenzl/oracle-free:23}
TOOL_IMAGES
# Save exact engine AND console images, including any locally extended driver image.
set --
while IFS= read -r tag; do set -- "$@" "$tag"; done < "$BACKUP_DIR/rollback-image-tags.txt"
podman save -o "$BACKUP_DIR/rollback-images.tar" "$@"

# Refuse an unmerged draft or a main that has advanced beyond the reviewed upgrade.
APPROVED_ENGINE_MERGE=$(gh pr view 9 --repo Reliable-Collaboration/sql-megasamples \
  --json mergeCommit --jq '.mergeCommit.oid // empty')
test -n "$APPROVED_ENGINE_MERGE"
# Client PR 10 must be merged, followed by the owner-approved dataset PR.
CLIENTS_PR=${CLIENTS_PR:-10}
APPROVED_CLIENTS_MERGE=$(gh pr view "$CLIENTS_PR" --repo Reliable-Collaboration/sql-megasamples \
  --json mergeCommit --jq '.mergeCommit.oid // empty')
test -n "$APPROVED_CLIENTS_MERGE"
# Set DATASETS_PR to the merged PR linked in docs/dataset-upgrade-evidence.md.
: "${DATASETS_PR:?set the reviewed owner-approved dataset PR number}"
APPROVED_UPGRADE_MERGE=$(gh pr view "$DATASETS_PR" --repo Reliable-Collaboration/sql-megasamples \
  --json mergeCommit --jq '.mergeCommit.oid // empty')
test -n "$APPROVED_UPGRADE_MERGE"
git fetch origin
if git ls-files --error-unmatch consoles/landing/adminer.html >/dev/null 2>&1; then
  git restore -- consoles/landing/adminer.html
fi
git switch main
git merge --ff-only origin/main
test "$(git rev-parse HEAD)" = "$APPROVED_UPGRADE_MERGE"
git merge-base --is-ancestor "$APPROVED_ENGINE_MERGE" HEAD
git merge-base --is-ancestor "$APPROVED_CLIENTS_MERGE" HEAD
# Keep the existing console page available until make up regenerates it from the same credentials.
if test -f "$BACKUP_DIR/adminer.generated.html"; then
  cp "$BACKUP_DIR/adminer.generated.html" consoles/landing/adminer.html
  chmod 644 consoles/landing/adminer.html  # readable by the local web-server worker
fi
git rev-parse HEAD > "$BACKUP_DIR/upgrade-commit.txt"
# The reviewed tools snapshot is a PRIVATE local artifact, not a public image.
# It contains the tested Python/uv/SQLite runtime; install dependencies only inside this container.
TOOLS_ARCHIVE=/home/rcc-vstudio/working/sql-megasamples-upgrade/build/client-evidence/current-validated-tools-image.tar
printf '%s  %s\n' '8e32e1e80ebf022ca9b882c6cac94f51477f01cc8dd5d96bb253c4bb62a6092c' "$TOOLS_ARCHIVE" | sha256sum -c -
podman load -i "$TOOLS_ARCHIVE"
TOOLS_IMAGE=localhost/megasamples-upgrade-tools:clients-20261117-libpq18.7
test "$(podman image inspect -f '{{.Id}}' "$TOOLS_IMAGE" | sed 's/^sha256://')" = '9cfca77f5b88e23f25e76429d70f0c72959ff13a6d933610c58ae74da67cd710'
UPGRADE_TOOLS_CONTAINER="megasamples-live-upgrade-tools-$UPGRADE_ID"
# The existing Docker CLI is mounted read-only; no host package installation.
DOCKER_CLIENT=$(command -v docker)
podman run -d --name "$UPGRADE_TOOLS_CONTAINER" --network host --memory 18g \
  --label megasamples.role=upgrade-tools \
  -e "DOCKER_HOST=$DOCKER_HOST" -e COMPOSE_PROJECT_NAME=sql-megasamples \
  -v "$PWD:$PWD" -v "$XDG_RUNTIME_DIR/podman:$XDG_RUNTIME_DIR/podman" \
  -v "$DOCKER_CLIENT:/usr/local/bin/docker:ro" -w "$PWD" "$TOOLS_IMAGE" sleep infinity
ms_tool() {
  podman exec -e "DOCKER_HOST=$DOCKER_HOST" -e COMPOSE_PROJECT_NAME=sql-megasamples \
    -e PYTHONPATH=. -w "$PWD" "$UPGRADE_TOOLS_CONTAINER" "$@"
}
# Preserve the previous environment as rollback; the original copy is already in BACKUP_DIR.
# uv and all packages execute in the tools container, with only this checkout mounted.
ms_tool /opt/venv/bin/uv sync --locked --python /usr/local/bin/python3
MEGASAMPLES_PY="$PWD/.venv/bin/python"
ms_tool "$MEGASAMPLES_PY" -m pytest -q tests/test_versions.py tests/test_client_releases.py
ms_tool make check PY="$MEGASAMPLES_PY"
# Preserve the live configuration and credentials; never copy isolated port settings here.
# Complete both the loader image and console extensions before the outage.
ms_tool make loader-image PY="$MEGASAMPLES_PY"
ms_tool make oracle-client-image PY="$MEGASAMPLES_PY"  # binaries only; no database licence acceptance
ms_tool "$MEGASAMPLES_PY" -c 'from megasamples import config,console_images; raise SystemExit(console_images.build(config.load()))'
# Reuse only the pinned sample inputs/exports, never SQL Server image layers or tools.
APPROVED_INPUTS=/home/rcc-vstudio/working/sql-megasamples-upgrade/build/dataset-upgrade-evidence/approved-inputs.tar
printf '%s  %s\n' '0a74cd4ee4def587889b373d11f29aa938cce91a0c21f3f501d7b328d62ce596' "$APPROVED_INPUTS" | sha256sum -c -
mkdir -p downloads
tar -xf "$APPROVED_INPUTS" -C downloads
# Add the datasets on each configured engine whose complete receipt Passed; remove Unsupported pairs.
# All existing ports, credentials, other datasets and consoles stay in the live configuration.
ms_tool "$MEGASAMPLES_PY" -c '
import json, pathlib, yaml
p = pathlib.Path("megasamples.yaml")
cfg = yaml.safe_load(p.read_text())
receipt = json.loads(pathlib.Path("docs/validation/dataset-upgrade-2026-11-17.json").read_text())
for engine, entry in cfg["engines"].items():
    names = entry["datasets"]
    for name in ["bts_ontime", "wideworldimporters", "wideworldimporters_dw"]:
        status = receipt["matrix"][engine + ":" + name]["status"]
        assert status in ["Passed", "Unsupported"], (engine, name, status)
        if status == "Passed" and name not in names: names.append(name)
        if status == "Unsupported" and name in names: names.remove(name)
p.write_text(yaml.safe_dump(cfg, sort_keys=False))
'
ms_tool make run PY="$MEGASAMPLES_PY"
ms_tool make test-image PY="$MEGASAMPLES_PY"
```

`make run` must complete with every configured dataset included. A missing download is a failure. Supply the manually obtained Lahman archive through the documented fetch workflow. Include the three owner-approved datasets using the preparation instructions above. Reuse the verified isolated WWI exports; the live servers do not need SQL Server or a new EULA acceptance. Keep the refreshed BTS airport SHA-256 pinned; a mismatch is a failure rather than authority to refresh it again. Every configured, in-scope dataset must pass. Read `docs/engine-upgrade-evidence.md` for exact validation coverage and unresolved inputs.

## Added dataset cost and scope

The owner-approved additions are MySQL `bts_ontime` (4 tables / 550,245 rows),
`wideworldimporters` (48 / 4,713,833) and `wideworldimporters_dw` (16 / 923,643).
PostgreSQL and SQLite each add only the warehouse (16 / 923,643). The repository rejects BTS
and OLTP generated expressions on those two ports; those four pairs are Unsupported and excluded.
The dated [dataset evidence](dataset-upgrade-evidence.md) and receipt link the exact capability
rule, its read time and attempted-command diagnostics.

The isolated additional database/file footprint was **1,933,059,775 bytes**, including both SQLite
copies, excluding shared WAL/engine overhead. The approved-input archive adds 899,993,600 bytes;
retain space for extracted inputs/staging/dumps and both complete old/new images and data copies.
Per-engine and per-dataset measurements are in the receipt. Whole-corpus image packaging took
mysql 1641.39 s, postgres 1564.71 s, sqlite 326.52 s. The successful WWI source builds took 286.75 s for both on MySQL,
plus 53.13 s for the warehouse PostgreSQL port and 39.19 s for SQLite.
The SQL Server export took 114 s and is already reusable. Replacement-stack startup took 269.27 s;
five-pair running verification took 200.15 s. These are observed isolated costs, not a live SLA.
Complete downloads, export reuse, conversion and image packaging before the outage. Reserve cold
copy, startup, actual fingerprint checks and DataIntent verification separately. Full reset tests
are isolated rehearsal checks; do not run them as live verification.

## Final backups and cutover

The files in `containers.json` include environment credentials: restrict access, do not paste them into tickets. Take logical backups while quiesced, then cold-copy each data directory. Rollback uses the cold copies with the original engine images; never open a new-version data directory with an old binary.

```sh
# BACKUP_DIR and UPGRADE_ID are the values from the preparation shell.
# Keep logical backups for inspection/recovery; credentials stay inside the container.
podman exec megasamples-postgres sh -c \
  'exec pg_dumpall -U postgres' > "$BACKUP_DIR/postgres.sql"
podman exec megasamples-mysql sh -c \
  'export MYSQL_PWD="$ADMIN_PASSWORD"; exec mysqldump -uadmin --all-databases --routines --events --triggers --single-transaction --hex-blob' \
  > "$BACKUP_DIR/mysql.sql"
chmod 600 "$BACKUP_DIR/"*.sql

# Downtime starts here. SQLite consumers must be stopped before copying its files.
# Stop every configured console as well as all engines; keep the proxy services running.
docker compose -p sql-megasamples -f compose.yaml stop
# Retain the final quiesced UI workspace too, including changes made during preparation.
if podman container exists megasamples-cloudbeaver; then
  podman cp megasamples-cloudbeaver:/opt/cloudbeaver/workspace "$BACKUP_DIR/cloudbeaver-workspace-final"
  chmod 700 "$BACKUP_DIR/cloudbeaver-workspace-final"
fi
# Copy each stopped data mount inside Podman's user namespace, retaining its real UID/GID.
# This includes the separate SQLite console volume and does not modify the source mounts.
while read -r label container destination; do
  source=$(podman inspect -f "{{range .Mounts}}{{if eq .Destination \"$destination\"}}{{.Source}}{{end}}{{end}}" "$container")
  test -n "$source"
  podman unshare test -d "$source"
  mkdir -p "$BACKUP_DIR/$label"
  podman unshare cp -a "$source/." "$BACKUP_DIR/$label/"
done <<'DATA_MOUNTS'
postgres megasamples-postgres /var/lib/postgresql
mysql megasamples-mysql /var/lib/mysql
sqlite megasamples-sqlite /data
sqlite-shared megasamples-sqlite /shared
DATA_MOUNTS
# Record and retain old anonymous volumes. Do not run down -v, reset, prune or clean-all.
podman volume ls --format json > "$BACKUP_DIR/volumes.json"

# make up detects a changed image and renews anonymous data volumes for the three engines.
# A replacement is the newly built sample corpus; application writes remain in the backups.
ms_tool make up PY="$MEGASAMPLES_PY"
# Initial connection files are seeded into the workspace. A restart retains the old catalogue.
# The original workspace is backed up above; reseed the configured connection list now.
if ms_tool "$MEGASAMPLES_PY" -c 'from megasamples import config; raise SystemExit(0 if "cloudbeaver" in config.load().consoles else 1)'; then
  docker compose -p sql-megasamples -f compose.yaml up -d --force-recreate \
    --renew-anon-volumes --no-deps --wait cloudbeaver
fi
ms_tool make test-console PY="$MEGASAMPLES_PY"
```

If `make up` waits with no health-log entries, the isolated rehearsal observed the same scheduling issue. In a second **coordinator maintenance shell**, run the real configured probes once for this project's engines; do not edit health status or change proxy services:

```sh
unset CONTAINERS_STORAGE_CONF CONTAINERS_CONF CONTAINERS_CONF_OVERRIDE DOCKER_HOST COMPOSE_PROJECT_NAME
export COMPOSE_PROJECT_NAME=sql-megasamples
cd /home/rcc-vstudio/working/sql-megasamples
for engine in mysql postgres sqlite; do
  test "$(podman inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "megasamples-$engine")" = sql-megasamples
  podman healthcheck run "megasamples-$engine"
done
```

This is a conditional manual-probe fallback; automatic scheduling in the live store has not been verified by this task. If a configured probe fails, inspect that engine and roll back if the failure cannot be resolved within the maintenance window.

The Compose stop above includes every configured console, so SQLite consumers are closed before either copy. `make up` restarts configured consoles. The new containers receive the existing `.env` credentials. Do not print that file.

In the isolated 30-dataset rehearsal, replacing all three engine containers and restoring SQLite's shared files took 121.65 seconds. Individual whole-engine resets took 23.07 seconds (MySQL), 26.4 seconds (PostgreSQL) and 92.4 seconds (SQLite). A stop/start of the existing eight-service stack, without replacing data volumes, took 38.66 seconds and preserved every recorded count, SQLite hash and inserted probe row. These measurements exclude cold-backup time and the coordinator's DataIntent checks and predate this follow-up; the added datasets have separate measurements in “Added dataset cost and scope”. Initial stack startup took 328.32 seconds while this custom store waited for health scheduling; real probes then completed successfully through the isolated-only runner. These are observed preparation/outage components, not a full-manifest downtime guarantee. The complete full-Contoso repository check against the shipped MySQL configuration took 1,736.02 seconds in this rehearsal, dominated by an indexed nested-loop constraint query. If the maintenance window includes that full integrity audit, budget its verification time as well as startup, cold copies and DataIntent tests.

The outage lasts from the first stop through readiness and verification, plus any rollback. Reserve a maintenance window; measured isolated timings belong in the evidence report, not an assumed SLA. Rebuilding before cutover avoids putting download/conversion time in the outage.

## Verify before resuming clients

```sh
podman ps --format '{{.Names}} {{.Status}} {{.Ports}}'
podman exec megasamples-postgres psql -U postgres -Atc 'SHOW server_version'
podman exec megasamples-mysql sh -c \
  'export MYSQL_PWD="$ADMIN_PASSWORD"; mysql -uadmin -N -e "SELECT VERSION()"'
podman exec megasamples-sqlite sqlite3 :memory: 'SELECT sqlite_version()'
podman exec megasamples-postgres psql -U postgres -d megasamples -Atc \
  'SELECT name,row_counts FROM datasets ORDER BY name'
podman exec megasamples-mysql sh -c \
  'export MYSQL_PWD="$ADMIN_PASSWORD"; mysql -uadmin -N -e "SELECT name,row_counts FROM megasamples.datasets ORDER BY name"'
podman exec megasamples-sqlite sqlite3 /data/megasamples.sqlite \
  'SELECT name,row_counts FROM datasets ORDER BY name'
# Actual added-dataset fingerprints against the replacement containers, without pinning fixtures.
ms_tool "$MEGASAMPLES_PY" -c '
import json, pathlib, shutil, subprocess
from megasamples import config, verify
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as pg
from megasamples.engines.sqlite import adapter as sq
root = pathlib.Path.cwd()
secret = dict(line.split("=", 1) for line in (root / ".env").read_text().splitlines() if line and not line.startswith("#"))
mysql.NAME = "megasamples-mysql"
mysql.PW = secret["MYSQL_ROOT_PASSWORD"]
pg.NAME = "megasamples-postgres"
receipt = json.loads((root / "docs/validation/dataset-upgrade-2026-11-17.json").read_text())
cfg = config.load()
checks = root / "build/live-upgrade-checks/sqlite"
failures = 0
for pair, result in receipt["matrix"].items():
    engine, name = pair.split(":")
    if result["status"] != "Passed" or engine not in cfg.engines: continue
    assert name in cfg.datasets(engine), pair
    if engine == "sqlite":
        target = checks / name
        target.mkdir(parents=True, exist_ok=True)
        subprocess.run(["docker", "cp", "megasamples-sqlite:/data/" + name + ".sqlite", str(target / (name + ".sqlite"))], check=True, capture_output=True)
        for filename in ["model.json", "dropped.txt"]:
            source = root / "build/sqlite" / name / filename
            if source.exists(): shutil.copy2(source, target / filename)
        sq.engine_build_dir = lambda _: str(checks)
    failures += verify.verify(name, engine=engine)
assert failures == 0, failures
joins = mysql.rows("SELECT COUNT(*), SUM(o.code IS NULL), SUM(d.code IS NULL) FROM bts_ontime.ontime f LEFT JOIN bts_ontime.l_airport o ON o.code=f.origin LEFT JOIN bts_ontime.l_airport d ON d.code=f.dest")
assert joins == [["539747", "0", "0"]], joins
'
```

Verify both existing forwarded endpoints with the containers' installed clients (credentials stay inside each container):

```sh
podman exec megasamples-postgres sh -c \
  'export PGPASSWORD="$DEMO_PASSWORD"; exec psql -h 10.0.0.172 -p 5432 -U demo -d megasamples -Atc "SELECT version(); SELECT count(*) FROM datasets"'
podman exec megasamples-mysql sh -c \
  'export MYSQL_PWD="$DEMO_PASSWORD"; exec mysql -h 10.0.0.172 -P 3306 -udemo -N -e "SELECT VERSION(); SELECT count(*) FROM megasamples.datasets"'
```

Compare the complete registry sets and each table's actual row counts with the validated configuration and catalogue. Registry text alone is not an actual count check. Run the repository's image tests before cutover and the same validation queries against the replacement servers afterwards. Live-feed counts/checksums must match the hub snapshot built with these images; historical manifest counts are floors for those feeds. Verify `demo` remains read-only and `admin` can write using disposable probe tables, then remove the probes.

Confirm PostgreSQL binds to `127.0.0.1:5432` and MySQL to `127.0.0.1:3306`. Run the coordinator's DataIntent server-bound suites against both the local endpoints and the existing forwarded endpoints `10.0.0.172:5432` and `10.0.0.172:3306`. The proxies continue forwarding to the same local ports and require no changes. Resume clients only after these checks pass.

The added-dataset check above uses actual server tables and a fresh copy of the shipped SQLite file.
It must pass exact counts and applicable canonical fingerprints, foreign keys, indexes and views.
For BTS, also require 6,942 airport rows and zero unmatched origin/destination rows across 539,747
flights. Check the complete console lists: three new MySQL databases and the supported warehouse
ports, including the new SQLite connection in CloudBeaver and DbGate. Unsupported pairs must not
be presented as available. Preserve the result logs with the maintenance receipt.

## Roll back

Keep clients paused. Do not remove any backup, original image tag, original branch, original anonymous volume, or proxy service.

The saved pre-upgrade configuration, console tree, images and cold volumes also roll back these
new datasets. Restoring them removes the added databases/files and their console connections as
part of restoring the original deployment. First retain any application writes made in the new
datasets; the pre-upgrade cold copies cannot contain those writes. Do not use `make reset` for
rollback: it restores the new image contents, including the added datasets.

```sh
# Restore original configuration and its original branch (never reset a pushed branch).
docker compose -p sql-megasamples -f compose.yaml down  # no -v: retained volumes remain available
ROLLBACK_BRANCH=$(cat "$BACKUP_DIR/rollback-branch.txt")
git switch "$ROLLBACK_BRANCH"
test "$(git rev-parse HEAD)" = "$(cat "$BACKUP_DIR/original-commit.txt")"
if test -f "$BACKUP_DIR/adminer.generated.html"; then
  cp "$BACKUP_DIR/adminer.generated.html" consoles/landing/adminer.html
  chmod 644 consoles/landing/adminer.html  # readable by the local web-server worker
fi
# Restore the entire console tree, including templates, generated connections and landing files.
mv consoles "$BACKUP_DIR/console-tree-before-restore"
cp -a "$BACKUP_DIR/consoles" ./consoles
if test -d .venv; then mv .venv "$BACKUP_DIR/failed-upgrade-python-venv"; fi
if test -d "$BACKUP_DIR/python-venv"; then cp -a "$BACKUP_DIR/python-venv" ./.venv; fi
cp "$BACKUP_DIR/megasamples.yaml" ./megasamples.yaml
cp "$BACKUP_DIR/compose.yaml" ./compose.yaml
if test -f "$BACKUP_DIR/.env"; then cp "$BACKUP_DIR/.env" ./.env; fi
podman load -i "$BACKUP_DIR/rollback-images.tar"
while read -r reference saved; do
  case "$reference" in
    *@*) : ;;  # keep the immutable input; the saved tag is also available as an override
    *) podman image tag "$saved" "$reference" ;;
  esac
done < "$BACKUP_DIR/original-tool-images.txt"
```

For exact preservation of application writes, create four **new** named rollback volumes (the three engine data directories and SQLite shared files), populate them from the cold copies while no database has them open, and attach them to the original image IDs. The backup loop resolves the actual source of each stopped data mount and copies it without changing ownership. Both backup and restore run `cp -a` inside the native rootless user namespace ([unshare reference](https://docs.podman.io/en/latest/markdown/podman-unshare.1.html), read 2026-11-16 21:05 UTC); this command is unavailable through a remote Podman client. The cold files may require `podman unshare` to inspect because their subordinate UID/GID ownership is retained. Use a Compose override, leaving original volumes untouched:

```sh
for engine in postgres mysql sqlite sqlite-shared; do
  podman volume create "megasamples-rollback-$engine-$UPGRADE_ID"
done
# podman unshare preserves ownership from the cold copies in rootless Podman's namespace.
for engine in postgres mysql sqlite sqlite-shared; do
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
  megasamples-sqlite:
    external: true
    name: megasamples-rollback-sqlite-shared-$UPGRADE_ID
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
# Add exact saved console images if they existed before the upgrade. This is a second override,
# so it also works when the old release used only vendor digest references.
python3 - "$BACKUP_DIR" "$UPGRADE_ID" <<'PY_CONSOLE_ROLLBACK'
import json, pathlib, sys
backup=pathlib.Path(sys.argv[1]); upgrade=sys.argv[2]
names={"landing", "cloudbeaver", "dbgate", "adminer", "phpmyadmin"}
services={}
for line in (backup/'rollback-image-tags.txt').read_text().splitlines():
    name=line.split('/sql-megasamples-',1)[1].split(':',1)[0]
    if name in names: services[name]={"image":line,"pull_policy":"never"}
(backup/'rollback-consoles.override.json').write_text(json.dumps({"services":services},indent=2)+'\n')
PY_CONSOLE_ROLLBACK
set --
RESTORE_CLOUDBEAVER=0
while IFS= read -r service; do
  if test "$service" = cloudbeaver; then RESTORE_CLOUDBEAVER=1; else set -- "$@" "$service"; fi
done < "$BACKUP_DIR/original-running-services.txt"
test "$#" -gt 0
docker compose -p sql-megasamples -f compose.yaml -f "$BACKUP_DIR/rollback.override.yaml" \
  -f "$BACKUP_DIR/rollback-consoles.override.json" up -d --wait "$@"
if test "$RESTORE_CLOUDBEAVER" = 1; then
  # Populate a stopped fresh container before its first initialization, retaining original UI state.
  docker compose -p sql-megasamples -f compose.yaml -f "$BACKUP_DIR/rollback.override.yaml" \
    -f "$BACKUP_DIR/rollback-consoles.override.json" create --force-recreate --no-build cloudbeaver
  CB_WORKSPACE_BACKUP="$BACKUP_DIR/cloudbeaver-workspace-final"
  if ! test -d "$CB_WORKSPACE_BACKUP"; then CB_WORKSPACE_BACKUP="$BACKUP_DIR/cloudbeaver-workspace"; fi
  if test -d "$CB_WORKSPACE_BACKUP"; then
    podman cp "$CB_WORKSPACE_BACKUP/." megasamples-cloudbeaver:/opt/cloudbeaver/workspace/
  fi
  docker compose -p sql-megasamples -f compose.yaml -f "$BACKUP_DIR/rollback.override.yaml" \
    -f "$BACKUP_DIR/rollback-consoles.override.json" up -d --no-deps --wait cloudbeaver
fi
```

If that default socket is absent, start a Podman API service for the **default** store in the coordinator's session before the Compose command. This is separate from the isolated build's service. The override also maps the original shared-volume name to the restored cold copy for every SQLite consumer. The SQLite service's original startup command republishes `/data` into that restored shared console volume; keep SQLite consoles stopped until that copy finishes. Repeat version, actual row-count, account and DataIntent endpoint checks against the restored stack, including the forwarded endpoints. Verify only the originally running consoles, using their restored image IDs, login flows and dataset lists. Keep the original tool invocation/environment for old-release build checks; do not run its converters under the upgraded dependency lock. Resume clients only after rollback validation succeeds. Record the failed upgrade and retain its data directories separately for diagnosis.

## Client and console verification and rollback details

The MySQL runtime now uses a 2 GiB container limit and an explicit 1 GiB TempTable allowance, retaining its 256 MiB InnoDB pool. The former 1 GiB limit OOM-killed the full Contoso aggregate during isolated validation. The limit follows the observed allocation budget; account for the additional 1 GiB maximum in maintenance planning. Original runtime settings are retained with the rollback source/configuration.

The release changes include the engine-supplied command-line clients; the Oracle MySQL clients and Connector/C in the loader; exact Python dependencies and `uv.lock`; CloudBeaver's MySQL/SQLite JDBC jars; DbGate's locked native SQLite driver; Adminer's current libpq and the separately pinned libpq used by pure Psycopg endpoint tests; and the digest-pinned phpMyAdmin, Adminer and nginx consoles; and independent pinned SQL*Plus/SQL*Loader archives for the optional Oracle verifier. The Oracle Free database still requires its explicit license gate before any native check. The new optional Oracle client recipe is Linux x86-64; other architectures are Unsupported by that recipe. Exact before/after versions, URLs, read times and compatibility evidence are in `docs/client-upgrade-evidence.md` and `clients.lock.yaml`. PostgreSQL uses matching server/client majors; the MySQL paths retain `caching_sha2_password` authentication. The TPC-C loader shares only its disposable build server's network namespace and uses loopback for Connector/C's local TLS behavior. No global certificate-verification bypass is set.

Before cutover, check the loader CLI dump/restore, TPC-C cardinalities, the DuckDB CSV conversions, the Python gate, every configured reset selector and complete dataset fingerprints in isolation. Reset commands are destructive data-restoration tests and belong only in the isolated rehearsal. Do not use `make reset` as a live verification command.

CloudBeaver's [initial configuration](https://dbeaver.com/docs/cloudbeaver/Initial-data-configuration/)
and [workspace connection file](https://dbeaver.com/docs/cloudbeaver/Data-Sources-Json-Reference/)
documentation were read 2026-11-17T10:14:42Z. The actual isolated upgrade showed that restarting
retained its old 31-connection catalogue and omitted the new SQLite warehouse. A consistent private
workspace backup followed by recreating only CloudBeaver reseeds the generated catalogue. Retain
that backup (it can contain credentials and saved queries), and restore it into a stopped original
console container for rollback as above. No engine data volume is renewed by this console step.

After cutover, run `ms_tool make test-console PY="$MEGASAMPLES_PY"`. In addition, open the landing page and every configured console through their actual live localhost ports. In phpMyAdmin, list the MySQL datasets for both configured accounts. In Adminer, sign in for MySQL and PostgreSQL and list their databases. In DbGate, open each engine, including a SQLite file; in CloudBeaver, open both server accounts and every SQLite connection and list the databases. Confirm each shows the complete configured registry, test read-only denial and admin writes on a disposable table, then remove the probe. The isolated receipt records the automated HTTP/GraphQL/installed-driver probes; repeat those checks against live ports without substituting HTTP 200 for a database connection.

Rollback keeps all original engine/console images in the archive, the original complete console/configuration tree, credentials, original Python environment and an immutable rollback branch. The new tools container and new environments are separate resources. Keep them stopped or retained for diagnosis after rollback; never replace the original tooling with the new dependency set. The original live deployment may have no running consoles: the saved running-service list ensures rollback does not start additional ones. Newly built console images are never substituted for their saved rollback image IDs.

## Isolation used for rehearsal

The rehearsal's settings and generated credentials are in the upgrade clone's `megasamples.yaml` and `.env` (mode 0600). Its socket is `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock`, project `megasamples-upgrade`; ports are PostgreSQL `127.0.0.1:15432`, MySQL `127.0.0.1:13306`, and consoles `127.0.0.1:18080` through `:18084`. It uses the isolated `slirp4netns` override under `build/upgrade-evidence/containers-slirp.conf` because Pasta failed to access the custom runroot's network namespace. Source `env.sh` and set `CONTAINERS_CONF_OVERRIDE` to that absolute file before starting its socket. The isolated API process can be stopped without stopping its running containers; start it again to use Docker Compose or the repository's commands. None of these settings belongs in the live checkout. Automatic health probes were not observed in this custom store. The temporary native runner `build/upgrade-evidence/run-isolated-healthchecks.py` drives the actual configured checks only for the three isolated engine IDs, validating their Compose labels. Its current PID and last results are in `healthcheck-runner-state.json`; the client follow-up restarted a stopped predecessor and records its launcher in `build/client-evidence/health-probe-runner.pid`; it does not require the API socket. Keep it while exercising the rehearsal. After the coordinator is finished with that stack, `touch build/upgrade-evidence/healthcheck-runner.stop` stops only this helper. Do not copy that workaround into the live service configuration.

After successful cutover or rollback, if this maintenance shell started an API process, stop only that process (the stack keeps running):

```sh
if test -n "${MEGASAMPLES_LIVE_API_PID:-}"; then
  kill "$MEGASAMPLES_LIVE_API_PID"
fi
```
