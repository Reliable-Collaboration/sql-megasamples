# Live engines, clients and consoles upgrade (coordinator only)

This coordinator procedure was **executed live once, on 2026-11-18**, at `2cf1f3e9`, with seven defects and coordinator-pinned corrections. This revision incorporates those corrections as preparation, verification and rollback gates. The [first-run evidence](live-upgrade-evidence.md) separates what was executed from what remains unverified. As of **2026-11-18**, acceptance was held for a DataIntent test failure outside this service; the acceptance record is DataIntent’s. Clients and acceptance remain coordinator-controlled. DL-077 templates/copies and their CLI remain a later task and second rollout. Keep the two existing socket-proxy services unchanged. The owner authorized the BTS refresh and accepted the SQL Server Developer EULA for the isolated WWI export on 2026-11-17. Oracle native verification remains **Not run, pending the owner's decision on Oracle's Free Use Terms**; do not accept those terms.

The isolated build uses `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/env.sh`. The live commands below deliberately use the default rootless Podman store instead. Run them only in the coordinator's live maintenance session. Never run them from the isolated validation shell.

The dataset candidate's cold-readiness blocker is resolved by the
[all-engine follow-up](cold-readiness-evidence.md): complete MySQL, PostgreSQL and SQLite image
checks and the repository gate Passed. Each engine now has a measured cold-copy/run limit and
the same independent 30-second server-query limit. The original 49.0-second MySQL and
38.2-second SQLite failures remain in the dataset receipt as historical results. The timing
and maintenance-window section below records the fresh measurements and their limits.

## Corrected target and upgrade path (DL-074)

The live MySQL change is **9.7.2 → 9.7.4**, a patch upgrade within 9.7 LTS. PostgreSQL remains **18.6 → 18.7** within major 18. SQLite remains the verified **3.54.1** target. Do not deploy the superseded 26.10 Innovation candidate, reuse its data directory, or bypass MySQL Shell dump-version checks. The isolated candidate was prepared with a fresh 9.7.4 build server from verified inputs. The cutover imports that exact validated candidate; a new rebuild requires its own isolated validation and interim comparison. The [DL-074 audit and receipt](lts-upgrade-evidence.md) identify the matching native clients, Oracle C API, Shell and JDBC versions and all retained pins. Client patch numbers differ by product.

The engine transition itself is an LTS patch. This procedure also packages the previously approved sample additions, so its preparation and outage components include fresh baked-volume materialization.

The corrected client changes include the loader CLI/C API at 9.7.4 (source-built sysbench), Shell 9.7.1 with Python 3.13.18 and embedded SQLite 3.54.1, Connector/J 9.7.0, DbGate on the newest tested compatible Node 24 LTS patch, NGINX 1.31.8 under the no-LTS current-major rule, SQLGlot 30.33.0, and PHP 8.5.12 for phpMyAdmin/Adminer with rebuilt matching extensions. DuckDB 2.0.0 and Java 25.0.5+8 are already on their newest eligible LTS lines. Preserve the unchanged memory limits used by the successful corrected full-corpus workload; this task does not infer a smaller MySQL allocation from the version number.

For a future replay, require the reviewed main merge containing these corrections, the same compared candidate, and a fresh coordinator-approved maintenance window. Historical isolated timing numbers below remain planning inputs. The live attempt required stops and recovery steps; it does not establish a repeatable outage or rollback duration.

## Credential prerequisite and DataIntent handoff (DL-079)

The [credential evidence](credential-prerequisite-evidence.md) and its receipt cover the reset
with configured credentials and native password rotation. The isolated rehearsal's canonical
credential file is `/home/rcc-vstudio/working/sql-megasamples-upgrade/.env`, mode 0600. The live
canonical file is `/home/rcc-vstudio/working/sql-megasamples/.env`, also mode 0600. DataIntent's
interim note should give these locations, the isolated endpoints and the merged revision; obtain
values privately from the owner-readable file. Do not paste values into that note or a receipt.

Set **all four** keys: `DEMO_PASSWORD`, `ADMIN_PASSWORD`, `MYSQL_ROOT_PASSWORD` and
`POSTGRES_PASSWORD`. The latter two rotate both MySQL root host accounts and PostgreSQL's
superuser. `config.passwords()` is the shared repository path used by reset, its count helpers,
registry readers and console checks. Shell overrides take Compose's precedence; unset any exported
password overrides before maintenance so the private `.env` is authoritative. Single-quoted
single-line `.env` values preserve literal punctuation. The cutover block generates random values
without printing them, after the original credentials and cold rollback inputs have been retained.

Compose's owner-readable container configuration carries the startup/console overrides. The
entrypoint removes them from the server process environment after application. MySQL's startup
SQL is in a mysql-owned mode-0400 temporary file; health probes use mode-0600 files under
`/run/megasamples-health.*`. Maintenance clients use mode-0600 option/pass files inside mode-0700
container directories, cleaned when the command ends. PostgreSQL maintenance uses network TCP so
its trusted loopback cannot hide a wrong password. `PGPASSFILE` contains only a path. The generated
landing/Adminer help pages and console workspaces also contain demo/admin credentials by the
project's existing design; retain them privately with the configuration backup and exclude them
from screenshots and evidence. Container/daemon owners can inspect their own configuration.

Native verification runs each configured account against network authentication, plus MySQL's
local root account, and requires every previous password to fail specifically with an authentication
error. A connection failure does not count as password refusal. SQLite has no server accounts;
password verification there is **Unsupported**. The first-run receipt records native rotation and
local account checks; forwarded authenticated SQL and a complete live rollback remain unverified.

Implementation sources read **2026-11-18 00:55:49 UTC**:
[MySQL option files](https://dev.mysql.com/doc/refman/9.7/en/option-files.html),
[PostgreSQL password files](https://www.postgresql.org/docs/18/libpq-pgpass.html), and
[Compose interpolation and precedence](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
The engine version/support sources and their read times remain in the [LTS audit](lts-upgrade-evidence.md).

## DL-074 preparation and sizing

Finish preparation before quiescing live clients. With the already verified input cache, the fresh 33-dataset MySQL rebuild took approximately **5,402.26 s (90.04 min)**; that duration is a Linux process-start/wall-clock estimate. The corrected Oracle-base restore of all 30 physical databases took **985.05 s**, the final image bake **1,366.10 s**, and starting the corrected eight-service stack **186.40 s**. These are separate observed operations, not a measured live outage. PostgreSQL/SQLite retain their existing corrected images; a complete from-source rebuild of those unchanged engines was not timed again in DL-074. Downloads, client/runtime compilation and the final DataIntent checks are additional preparation or verification work.

The immutable corrected images contain these measured data files (GiB = 2^30 bytes):

| Engine | Complete image (GiB, uncompressed) | Baked data allocated (GiB) | Candidate data mounts |
|---|---:|---:|---|
| MySQL | 24.151 | 22.712 | One fresh data volume |
| PostgreSQL | 21.357 | 20.902 | One fresh cluster volume |
| SQLite | 17.897 | 17.862 | One data volume plus a second shared console copy |

A conservative sum is **68,080,242,292 bytes of engine images plus 85,188,780,032 bytes of candidate data mounts: 142.743 GiB**. Layer sharing and reflinks can reduce actual consumption. A **25% planning allowance**, rounded up, gives **179 GiB**, before console images, live cold rollback backups, logical dumps, retained original images and build/import scratch space. This allowance is a planning choice, not a measured peak. Let `B` be the coordinator's measured live cold-backup bytes and `D` the retained logical-dump bytes: reserve those in addition to the candidate allowance. Neither `B` nor `D` has been read from the live deployment in this rehearsal. The five running console images add **2.198 GiB** uncompressed. Including them before the 25% allowance rounds the complete candidate budget to **182 GiB + B + D**, still excluding retained original images and preparation scratch.

The later active-workload snapshot observed **36.054 GiB in MySQL mounts, 21.837 GiB in PostgreSQL mounts and 35.725 GiB across SQLite's two copies**. MySQL's binary-log metadata alone reported 10,884,386,099 bytes after the logical-reset rehearsal. Including the current image sizes, that is **159.219 GiB**, before any rollback backups or retained original images. Use the larger **200 GiB + B + D** prepared-candidate allowance for this observed workload with a 25% margin. The 182 GiB figure above describes the initial baked files. Unlinked temporary files and a complete isolated-store peak were not measured by this directory snapshot.

Building on the target host needs substantially more scratch space than importing already prepared images. Rootless image packaging temporarily retains dump layers, the builder data directory, the final data layer and export/import working files. Keep that preparation outside the outage, monitor free space and budget separately for its cache. The DL-074 receipt records shared-filesystem samples and narrowly scoped cleanup of this run's discarded objects; those observations are not an isolated-store peak or a universal minimum. At 20:05 UTC, the clone's verified downloads, staging files and three engine output directories occupied **49.036 GiB** allocated. A from-source planning example is **321 GiB + B + D + retained original/tool images**: 200 GiB workload candidate allowance, that existing cache, one 22.712 GiB MySQL builder directory and two additional 24.151 GiB packaging/export copies. This is an explicit allowance for overlapping copies, not a measured minimum or peak. Image-level validation needs separate temporary data copies: allow another **70 GiB** if detached test volumes are retained between phases. This rehearsal removed only its two completed MySQL image-test volumes by exact name after checking their recorded creation interval, zero mount count and absence from all remaining containers; they occupied 48,771,981,312 allocated bytes. Keep recording scratch mounts and removing only known, completed-test volumes as needed. Do not use a global image/volume prune. Retain every live rollback image and cold copy.

The current persistence rehearsal preserved every recorded count, SQLite file hash, inserted probe row and engine container ID across stop/start. The stop/start readiness interval was **44.16 s**; collecting the complete snapshots and restoring the probe databases made the full command **691.77 s**. Individual whole-engine resets took **44.09 s (MySQL), 50.63 s (PostgreSQL), and 109.81 s (SQLite)**, with the SQLite shared copy and mutation checks included. The complete three-engine reset took **161.20 s**. The exhaustive grouped 95-selector reset took **4,956.20 s (82.60 min)**, including per-database logical restore, foreign-key checks and hashes of both SQLite copies; the complete reset command, including all earlier scopes, took **5,897.46 s**. Schedule that exhaustive regression rehearsal outside the maintenance window. These are isolated measurements, excluding live backup/rollback and DataIntent time.

Keep the existing MySQL 2 GiB limit, 256 MiB InnoDB pool and 1 GiB TempTable budget for this validated full corpus. PostgreSQL remains at 1 GiB and SQLite at 256 MiB. Source builders, console processes, file-cache pressure and simultaneous copies need additional headroom. The final receipt records observed container limits and runtime state; no lower production memory allocation is inferred from the LTS version number.

### Corrected verification and readiness measurements

The complete configured runtime matrix Passed for all **95 supported pairs**. MySQL took **3678.12 s**, PostgreSQL **2245.14 s**, and the corrected SQLite run **2027.01 s**. These engine checks ran concurrently; their sum is not an elapsed outage. The MySQL Contoso 10m dataset alone took **1614.36 s**, including its long integrity join. Keep full-corpus verification in the offline preparation plan. The initial SQLite observer failure was CSV-style TSV quoting, and the corrected complete run preserved every data assertion.

Complete image tests Passed in **484.62 s (MySQL), 280.55 s (PostgreSQL), and 781.70 s (SQLite)**. Their displayed cold copy/run and subsequent query times were:

| Engine | Fresh-volume copy/run (s) | Query after run returned (s) | Unchanged copy/server budgets (s) |
|---|---:|---:|---:|
| MySQL | 36.2 | 1.2 | 170 / 30 |
| PostgreSQL | 36.2 | 0.4 | 180 / 30 |
| SQLite | 29.6 | 0.1 | 150 / 30 |

Six additional fresh-volume MySQL starts all Passed: **23.886–26.167 s** copy/run and **0.889–0.903 s** subsequent query readiness. These are volume-materialization observations on this shared host; host filesystem caches were not forcibly dropped. The complete six-start command, including scoped cleanup, took **171.57 s**. Budgets were not lowered for the corrected image.

Plan several hours of offline source preparation and exhaustive verification, including the measured rebuild, fresh restore, bake, all reset scopes and runtime checks. Compilation/download time and the coordinator's DataIntent suites are additional. Live downtime still requires a separate allowance for quiescing writers, final logical backups, cold rollback copies, replacement readiness, chosen verification, DataIntent and rollback reserve. Cold-backup size/throughput and live rollback duration remain unverified; derive those from the coordinator's actual `B` and `D` measurements. Rollback restores only the retained pre-upgrade 9.7.2 cold copy and exact images/configuration.

## Prepare while the live servers are still running

Quiesce DataIntent writers before the final backups and cutover. Keep its clients paused through verification. Building from upstream can take much longer than the outage; finish it before stopping the live servers. The previous core build documented in README took approximately twenty minutes; the full manifest includes much larger datasets. No full-manifest outage duration has been established.

First, in the **isolated validation shell**, export verification metadata from the exact compared
build. Image transport does not include these checkout files. Never regenerate or pin expectations
from the live target. The bundle includes every selected PostgreSQL/SQLite physical database's
`build/<engine>/<database>/model.json`, optional SQLite `dropped.txt`, and selected live-feed
`build/live/<dataset>.observed.yaml` files. Verification also reads tracked `datasets/*/dataset.yaml`,
`datasets/*/tests/*` and port records from the compared revision; SQLite checks copy the running
database files into a separate check directory. Registry checks read the running registries.

```sh
. /home/rcc-vstudio/working/sql-megasamples-upgrade-env/env.sh
test "$CONTAINERS_STORAGE_CONF" = /home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf
test "$(podman info --format '{{.Store.GraphRoot}}')" = /home/rcc-vstudio/working/sql-megasamples-upgrade-env/graph
cd /home/rcc-vstudio/working/sql-megasamples-upgrade
# Set a unique absolute bundle path for this candidate and retain it in the receipt.
: "${METADATA_BUNDLE:?Set the new verification metadata bundle path}"
podman exec -e PYTHONPATH=. megasamples-upgrade-tools .venv/bin/python \
  docs/validation/live-upgrade.py export-metadata "$METADATA_BUNDLE" </dev/null
podman exec -e PYTHONPATH=. megasamples-upgrade-tools .venv/bin/python \
  docs/validation/live-upgrade.py check-metadata "$METADATA_BUNDLE" </dev/null
```

Return to a separate **coordinator live maintenance shell** for the remaining procedure.
Use Bash (`bash --noprofile --norc`); the recoverable context below uses Bash's quoted
`declare -p` and `declare -f` output. Keep the backup directory path in the maintenance receipt.

```sh
set -eu
unset CONTAINERS_STORAGE_CONF CONTAINERS_CONF CONTAINERS_CONF_OVERRIDE DOCKER_HOST COMPOSE_PROJECT_NAME
unset DEMO_PASSWORD ADMIN_PASSWORD MYSQL_ROOT_PASSWORD POSTGRES_PASSWORD
export COMPOSE_PROJECT_NAME=sql-megasamples
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/podman/podman.sock"
cd /home/rcc-vstudio/working/sql-megasamples
# Coordinator supplies the reviewed main merge before ANY backup/configuration change.
: "${APPROVED_UPGRADE_MERGE:?Set the reviewed main merge containing DL-086}"
: "${METADATA_BUNDLE:?Set the unique verified metadata bundle directory}"
: "${EXTRA_RESERVE_BYTES:?Set measured backup/dump/candidate/tool/scratch reserve in bytes}"
git fetch origin main
# BEGIN original-head guard
if git merge-base --is-ancestor "$APPROVED_UPGRADE_MERGE" HEAD; then
  echo 'STOP: HEAD already contains the upgrade. Restore the retained context; do not repeat preparation.'
  exit 1
fi
# END original-head guard
UPGRADE_ID=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$PWD/build/live-upgrade-backups/$UPGRADE_ID"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
# Initialize recoverable paths before any operation that can refuse preparation.
UPGRADE_HELPER= UPGRADE_TOOLS_CONTAINER= MEGASAMPLES_PY= MEGASAMPLES_LIVE_API_PID=
TEARDOWN_SNAPSHOT= EXITED_RECEIPT= TEARDOWN_PHASE=
APPROVED_ENGINE_MERGE= APPROVED_CLIENTS_MERGE= APPROVED_DATASET_MERGE=
APPROVED_LTS_MERGE= APPROVED_CREDENTIAL_MERGE=
TOOLS_ARCHIVE= TOOLS_IMAGE= CANDIDATE_ARCHIVE= DOCKER_CLIENT=
: "${EXTRA_RESERVE_BYTES:?Set measured backup/dump/candidate/tool/scratch reserve in bytes}"
: "${METADATA_BUNDLE:?Set the unique verified metadata bundle directory}"
PREPARATION_STAGE=original-inputs
ms_tool() {
  podman exec -i -e "DOCKER_HOST=$DOCKER_HOST" -e COMPOSE_PROJECT_NAME=sql-megasamples \
    -e PYTHONPATH=. -w "$PWD" "$UPGRADE_TOOLS_CONTAINER" "$@"
}
save_context() {
# Save non-secret maintenance context.
umask 077
{
  printf '%s\n' 'set -eu' \
    'unset CONTAINERS_STORAGE_CONF CONTAINERS_CONF CONTAINERS_CONF_OVERRIDE' \
    'unset DEMO_PASSWORD ADMIN_PASSWORD MYSQL_ROOT_PASSWORD POSTGRES_PASSWORD'
  declare -p BACKUP_DIR UPGRADE_ID UPGRADE_HELPER UPGRADE_TOOLS_CONTAINER MEGASAMPLES_PY \
    METADATA_BUNDLE DOCKER_HOST MEGASAMPLES_LIVE_API_PID APPROVED_UPGRADE_MERGE PREPARATION_STAGE \
    TEARDOWN_SNAPSHOT EXITED_RECEIPT TEARDOWN_PHASE EXTRA_RESERVE_BYTES \
    APPROVED_ENGINE_MERGE APPROVED_CLIENTS_MERGE APPROVED_DATASET_MERGE \
    APPROVED_LTS_MERGE APPROVED_CREDENTIAL_MERGE TOOLS_ARCHIVE TOOLS_IMAGE CANDIDATE_ARCHIVE DOCKER_CLIENT
  printf '%s\n' 'export DOCKER_HOST COMPOSE_PROJECT_NAME=sql-megasamples'
  printf 'cd -- %q\n' "$PWD"
  declare -f ms_tool save_context
} > "$BACKUP_DIR/resume-context.bash"
chmod 600 "$BACKUP_DIR/resume-context.bash"
# End saved context.
}
save_context
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
if test -f .env; then cp .env "$BACKUP_DIR/"; chmod 600 "$BACKUP_DIR/.env"; fi
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
# Record exact engine AND console images, including any locally extended driver image.
set --
while IFS= read -r tag; do set -- "$@" "$tag"; done < "$BACKUP_DIR/rollback-image-tags.txt"
# Tags are convenient handles; SHA-256 image IDs and archive/config digests are the rollback inputs.
: > "$BACKUP_DIR/rollback-image-ids.txt"
for tag in "$@"; do
  printf '%s ' "$tag" >> "$BACKUP_DIR/rollback-image-ids.txt"
  podman image inspect -f '{{.Id}} {{json .RepoDigests}}' "$tag" >> "$BACKUP_DIR/rollback-image-ids.txt"
done
# Save/check each image after switching to the reviewed corrected helper below, before downtime.
# The complete original configuration archive includes private pages and the original .env.
bash -c 'set -o pipefail; cd "$1"; tar --sort=name --numeric-owner --format=gnu --atime-preserve=system -cf - consoles compose.yaml megasamples.yaml pyproject.toml uv.lock > original-configurations.tar' sh "$BACKUP_DIR"
if test -f "$BACKUP_DIR/.env"; then
  tar -rf "$BACKUP_DIR/original-configurations.tar" -C "$BACKUP_DIR" .env
fi
chmod 600 "$BACKUP_DIR/original-configurations.tar"
(cd "$BACKUP_DIR" && sha256sum original-configurations.tar > original-configurations.sha256)

# Refuse an unmerged draft or a main that has advanced beyond the reviewed upgrade.
APPROVED_ENGINE_MERGE=$(gh pr view 9 --repo Reliable-Collaboration/sql-megasamples \
  --json mergeCommit --jq '.mergeCommit.oid // empty')
test -n "$APPROVED_ENGINE_MERGE"
# Client PR 10 must be merged, followed by the owner-approved dataset PR.
CLIENTS_PR=${CLIENTS_PR:-10}
APPROVED_CLIENTS_MERGE=$(gh pr view "$CLIENTS_PR" --repo Reliable-Collaboration/sql-megasamples \
  --json mergeCommit --jq '.mergeCommit.oid // empty')
test -n "$APPROVED_CLIENTS_MERGE"
# The dataset/readiness PR is already merged; DL-074 supersedes its version selection.
DATASETS_PR=${DATASETS_PR:-11}
APPROVED_DATASET_MERGE=$(gh pr view "$DATASETS_PR" --repo Reliable-Collaboration/sql-megasamples \
  --json mergeCommit --jq '.mergeCommit.oid // empty')
test -n "$APPROVED_DATASET_MERGE"
APPROVED_LTS_MERGE=$(gh pr list --repo Reliable-Collaboration/sql-megasamples \
  --state merged --head upgrade/dl074-lts-correction --limit 1 \
  --json mergeCommit --jq '.[0].mergeCommit.oid // empty')
test -n "$APPROVED_LTS_MERGE"
APPROVED_CREDENTIAL_MERGE=$(gh pr list --repo Reliable-Collaboration/sql-megasamples \
  --state merged --head fix/dl079-configured-reset-credentials --limit 1 \
  --json mergeCommit --jq '.[0].mergeCommit.oid // empty')
test -n "$APPROVED_CREDENTIAL_MERGE"
PREPARATION_STAGE=source-switch
save_context
git fetch origin
if git ls-files --error-unmatch consoles/landing/adminer.html >/dev/null 2>&1; then
  git restore -- consoles/landing/adminer.html
fi
git switch main
git merge --ff-only origin/main
test "$(git rev-parse HEAD)" = "$APPROVED_UPGRADE_MERGE"
git merge-base --is-ancestor "$APPROVED_ENGINE_MERGE" HEAD
git merge-base --is-ancestor "$APPROVED_CLIENTS_MERGE" HEAD
git merge-base --is-ancestor "$APPROVED_DATASET_MERGE" HEAD
git merge-base --is-ancestor "$APPROVED_LTS_MERGE" HEAD
git merge-base --is-ancestor "$APPROVED_CREDENTIAL_MERGE" HEAD
# Keep the existing console page available until make up regenerates it from the same credentials.
if test -f "$BACKUP_DIR/adminer.generated.html"; then
  cp "$BACKUP_DIR/adminer.generated.html" consoles/landing/adminer.html
  chmod 644 consoles/landing/adminer.html  # readable by the local web-server worker
fi
git rev-parse HEAD > "$BACKUP_DIR/upgrade-commit.txt"
# Retain the helper outside the checkout: rollback switches to a branch predating it.
cp docs/validation/live-upgrade.py "$BACKUP_DIR/live-upgrade.py"
cp docs/validation/quiescence.py "$BACKUP_DIR/quiescence.py"
UPGRADE_HELPER="$BACKUP_DIR/live-upgrade.py"
chmod 600 "$UPGRADE_HELPER"
PREPARATION_STAGE=archive-gates
save_context
# Native host Python + Podman; no package installation, one docker archive per full image ID.
# Before saving, measure B (cold copies), D (logical dumps), remaining candidate/tool
# import/data copies and their scratch on THIS filesystem. Set the additional reserve.
: "${EXTRA_RESERVE_BYTES:?Set measured B+D+remaining candidate/tool/scratch reserve in bytes}"
# Adds TWO complete original-image sets (per-image archives + scratch load), with 25%.
# Existing original images and any retained malformed aggregate already occupy disk.
python3 "$UPGRADE_HELPER" space "$BACKUP_DIR" --extra-bytes "$EXTRA_RESERVE_BYTES" \
  > "$BACKUP_DIR/archive-space-$UPGRADE_ID.log"
# BEGIN archive gates
python3 "$UPGRADE_HELPER" save-images "$BACKUP_DIR"
python3 "$UPGRADE_HELPER" check-images "$BACKUP_DIR"
# END archive gates
# Rehearse the COMPLETE rollback set in a fresh store before downtime. No containers are started.
(
  SCRATCH_DIR="$BACKUP_DIR/rollback-load-rehearsal"
  mkdir "$SCRATCH_DIR"
  printf '[storage]\ndriver="overlay"\ngraphroot="%s/graph"\nrunroot="%s/run"\n' \
    "$SCRATCH_DIR" "$SCRATCH_DIR" > "$SCRATCH_DIR/storage.conf"
  printf '[engine]\ntmp_dir="%s/tmp"\n' "$SCRATCH_DIR" > "$SCRATCH_DIR/containers.conf"
  export CONTAINERS_STORAGE_CONF="$SCRATCH_DIR/storage.conf" CONTAINERS_CONF="$SCRATCH_DIR/containers.conf"
  unset CONTAINERS_CONF_OVERRIDE
  # Give this scratch store its own rootless pause process and runtime files.
  export XDG_RUNTIME_DIR="$SCRATCH_DIR/xdg"
  mkdir -m 700 "$XDG_RUNTIME_DIR"
  test "$(podman info --format '{{.Store.GraphRoot}}')" = "$SCRATCH_DIR/graph"
  python3 "$UPGRADE_HELPER" load-images "$BACKUP_DIR" > "$SCRATCH_DIR/load.log" 2>&1
  test -z "$(podman ps -aq)"
  # Only this freshly created scratch store: drop loaded duplicates AND its pause process.
  # Keep logs/configuration under BACKUP_DIR. Never run this in the default/isolated store.
  test "$CONTAINERS_STORAGE_CONF" = "$SCRATCH_DIR/storage.conf"
  test "$(podman info --format '{{.Store.GraphRoot}}')" = "$SCRATCH_DIR/graph"
  # No containers remain; stop the pause process in the private runtime first.
  podman system migrate >> "$SCRATCH_DIR/cleanup.log" 2>&1
  podman system reset --force >> "$SCRATCH_DIR/cleanup.log" 2>&1
)
# Back in the original maintenance shell/store. Retain the rehearsal log with the backup.
# The reviewed tools snapshot is a PRIVATE local artifact, not a public image.
# It contains the tested Python/uv/SQLite runtime; install dependencies only inside this container.
TOOLS_ARCHIVE=/home/rcc-vstudio/working/sql-megasamples-upgrade/build/client-evidence/current-validated-tools-image.tar
printf '%s  %s\n' '8e32e1e80ebf022ca9b882c6cac94f51477f01cc8dd5d96bb253c4bb62a6092c' "$TOOLS_ARCHIVE" | sha256sum -c -
podman load -i "$TOOLS_ARCHIVE"
TOOLS_IMAGE=localhost/megasamples-upgrade-tools:clients-20261117-libpq18.7
test "$(podman image inspect -f '{{.Id}}' "$TOOLS_IMAGE" | sed 's/^sha256://')" = '9cfca77f5b88e23f25e76429d70f0c72959ff13a6d933610c58ae74da67cd710'
CANDIDATE_ARCHIVE=/home/rcc-vstudio/working/sql-megasamples-upgrade/build/credential-upgrade/candidate-images.tar
test -f "$CANDIDATE_ARCHIVE"
test -f "$METADATA_BUNDLE/metadata.json"
UPGRADE_TOOLS_CONTAINER="megasamples-live-upgrade-tools-$UPGRADE_ID"
# The existing Docker CLI is mounted read-only; no host package installation.
DOCKER_CLIENT=$(command -v docker)
PREPARATION_STAGE=tools-start
save_context
podman run -d --name "$UPGRADE_TOOLS_CONTAINER" --network host --memory 18g \
  --label megasamples.role=upgrade-tools \
  -e "DOCKER_HOST=$DOCKER_HOST" -e COMPOSE_PROJECT_NAME=sql-megasamples \
  -v "$PWD:$PWD" -v "$XDG_RUNTIME_DIR/podman:$XDG_RUNTIME_DIR/podman" \
  -v "$CANDIDATE_ARCHIVE:$CANDIDATE_ARCHIVE:ro" \
  -v "$METADATA_BUNDLE:$METADATA_BUNDLE:ro" \
  -v "$DOCKER_CLIENT:/usr/local/bin/docker:ro" -w "$PWD" "$TOOLS_IMAGE" sleep infinity

# Keep the old environment for rollback; run tooling only in this container.
ms_tool /opt/venv/bin/uv sync --locked --python /usr/local/bin/python3 </dev/null
MEGASAMPLES_PY="$PWD/.venv/bin/python"
PREPARATION_STAGE=candidate-gates
save_context
# Prove heredoc delivery before trusting a zero exit status from Python reading stdin.
ms_tool "$MEGASAMPLES_PY" - <<'PY_STDIN_CHECK' > "$BACKUP_DIR/stdin-check.txt"
print("stdin-executed")
PY_STDIN_CHECK
test "$(cat "$BACKUP_DIR/stdin-check.txt")" = stdin-executed
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py export-ports \
  "$BACKUP_DIR/original-ports.json" --config "$BACKUP_DIR/megasamples.yaml" </dev/null
# Import the exact compared images, checking the committed receipt before any load/tag operation.
# Image import/tagging leaves the existing containers and their volumes running unchanged.
ms_tool "$MEGASAMPLES_PY" - "$CANDIDATE_ARCHIVE" <<'PY_IMPORT_CANDIDATE'
import hashlib, json, pathlib, subprocess, sys
from megasamples import config
receipt = json.loads(pathlib.Path("docs/validation/credential-prerequisite-2026-11-18.json").read_text())
candidate = receipt["prepared_candidate"]
assert candidate["status"] == "Passed"
tree = subprocess.check_output(["git", "ls-tree", "-r", "HEAD", "--", *candidate["software_paths"]], text=True).strip()
assert hashlib.sha256(tree.encode()).hexdigest() == candidate["software_tree_sha256"], "candidate software differs from the compared revision"
archive = pathlib.Path(sys.argv[1])
h = hashlib.sha256()
with archive.open("rb") as stream:
    for block in iter(lambda: stream.read(1 << 20), b""): h.update(block)
assert h.hexdigest() == candidate["archive"]["sha256"], "candidate archive digest mismatch"
subprocess.run(["docker", "load", "-i", str(archive)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def image_id(reference):
    p = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", reference], capture_output=True, text=True)
    return p.stdout.strip().removeprefix("sha256:") if p.returncode == 0 else None
for service, entry in candidate["services"].items():
    expected = entry["image_id"].removeprefix("sha256:")
    assert image_id(entry["validated_reference"]) == expected, service + " archive image differs"
    reference = entry["repository_reference"]
    if "@" in reference:
        # A Docker archive can omit a vendor RepoDigest. Fetch that fixed manifest if needed,
        # and require the resulting image ID to equal the already validated candidate.
        if image_id(reference) is None:
            subprocess.run(["docker", "pull", reference], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        subprocess.run(["docker", "tag", entry["validated_reference"], reference], check=True)
    assert image_id(reference) == expected, service + " repository reference differs"
# Preserve the live port map; use exactly the compared engine/dataset and console selection.
raw = config.load().raw
raw["engines"] = {engine: {"datasets": names} for engine, names in candidate["datasets"].items()}
raw["consoles"] = candidate["consoles"]
config.write(raw)
print("Passed: candidate archive, software tree, every image ID and dataset selection")
PY_IMPORT_CANDIDATE
ms_tool "$MEGASAMPLES_PY" -m pytest -q </dev/null
ms_tool make compose PY="$MEGASAMPLES_PY" </dev/null
ms_tool "$MEGASAMPLES_PY" -m megasamples console-config </dev/null
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py install-metadata "$METADATA_BUNDLE" </dev/null
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py check-metadata "$METADATA_BUNDLE" </dev/null
# Host-side port inspection/bind probes. Exempt only ports owned by this running Compose project.
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py ports --allow-running-project sql-megasamples </dev/null

```

The committed credential receipt is the authority for the transfer archive SHA-256 and each
application image ID. It must cover the same software tree and configured dataset selection as the
interim PostgreSQL comparison. Do not rebuild after that comparison and then deploy different
artifacts. The original from-source preparation measurements below remain historical planning
inputs; preparing another candidate requires the full isolated gates and comparison again. The
prepared images already contain the owner-approved BTS refresh and WWI exports. No new SQL Server
or Oracle database/terms acceptance is involved in importing them. Verify the archive and every
repository image reference while the original live containers are still running; preserve their
rollback tags, per-image archives and cold copies. A pinned vendor manifest may need fetching when its
RepoDigest was not retained by Docker archive transport, but its resulting image ID must be identical.

The scratch cleanup follows [Podman's reset reference](https://docs.podman.io/en/latest/markdown/podman-system-reset.1.html),
read **2026-11-18 18:03:54 UTC**. It deletes the selected store's resources and graph/run roots;
the graphroot assertions above restrict it to the freshly created rehearsal store.
The preceding [migrate command](https://docs.podman.io/en/latest/markdown/podman-system-migrate.1.html),
read **2026-11-18 18:10:46 UTC**, stops the rootless pause process. The private `XDG_RUNTIME_DIR`
keeps that process separate from the maintenance and isolated stores.

### Resume or abort preparation

At a refusal, start a fresh Bash shell, set the recorded `BACKUP_DIR`, and source
`"$BACKUP_DIR/resume-context.bash"`. Read `PREPARATION_STAGE` and the failed command's log.
Rerun **only that failed gate**, then continue at its next command. A failed metadata check can
be repaired only from the same verified bundle; a port refusal requires the unrelated listener's
owner to release it or a separately reviewed port configuration. Do not kill it or improvise a
port. For an interrupted save, retain all files and run
`python3 "$UPGRADE_HELPER" resume-save-images "$BACKUP_DIR"`. It validates every existing archive
before saving only missing full IDs, then creates the per-image checksum receipt exclusively.
An existing complete checksum receipt is verified without rewriting it. A damaged partial archive
refuses; record its path/digest and move only that damaged file to a unique `.partial` name in the
same private backup directory before rerunning this gate. Never replace a verified archive. Never overwrite original configuration/image mappings,
rerun the preparation capture, or reinterpret the upgraded HEAD as the rollback source.

If abandoning before `.env` rotation, cold copies may not exist, so do **not** enter the full
cold-copy rollback. If stop was attempted, complete the four teardown checks first; accept no
unresolved process or namespace evidence. Original containers/volumes still exist in this path.
Restore original source/configuration and start only the originally running containers:

```sh
# Abort before password rotation ONLY. Original container IDs must still exist.
. "$BACKUP_DIR/resume-context.bash"
ABORT_ID=$(date -u +%Y%m%dT%H%M%S%N)
ROLLBACK_BRANCH=$(cat "$BACKUP_DIR/rollback-branch.txt")
git switch "$ROLLBACK_BRANCH"
test "$(git rev-parse HEAD)" = "$(cat "$BACKUP_DIR/original-commit.txt")"
mv consoles "$BACKUP_DIR/aborted-consoles-$ABORT_ID"
cp -a "$BACKUP_DIR/consoles" ./consoles
cp "$BACKUP_DIR/compose.yaml" ./compose.yaml
cp "$BACKUP_DIR/megasamples.yaml" ./megasamples.yaml
if test -f "$BACKUP_DIR/.env"; then cp "$BACKUP_DIR/.env" .env; chmod 600 .env; else rm -f .env; fi
if test -d .venv; then mv .venv "$BACKUP_DIR/aborted-venv-$ABORT_ID"; fi
if test -d "$BACKUP_DIR/python-venv"; then cp -a "$BACKUP_DIR/python-venv" .venv; fi
if test -n "$TEARDOWN_SNAPSHOT"; then
  # Exempt only the original project's still-running ports; stopped ports must be free.
  python3 "$UPGRADE_HELPER" ports --port-config "$BACKUP_DIR/original-ports.json" \
    --allow-running-project sql-megasamples --services-file "$BACKUP_DIR/original-running-services.txt"
  set --
  while IFS= read -r service; do set -- "$@" "$service"; done < "$BACKUP_DIR/original-running-services.txt"
  test "$#" -gt 0
  docker compose -p sql-megasamples -f compose.yaml start "$@"
fi
# Before any stop attempt, leave the still-running original containers alone.
```

`start` reuses the retained containers and their original anonymous volumes. If any original ID
is missing or its data mount cannot be proved unchanged, stop for coordinator recovery; never
substitute `up` to create a new empty volume. Verify original versions, accounts and counts before
resuming clients. After password rotation or candidate creation, use the full guarded rollback.
A new preparation attempt needs original HEAD plus a new directory and approval window.

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
PREPARATION_STAGE=final-backups
save_context

# Keep logical backups for inspection/recovery; only private pass/option files reach clients.
ms_tool "$MEGASAMPLES_PY" - "$BACKUP_DIR" <<'PY_LOGICAL_BACKUP'
import pathlib, subprocess, sys
from megasamples import config
from megasamples.credentials import client
backup = pathlib.Path(sys.argv[1])
config.ROOT = str(backup)
old = config.passwords()
for engine, user, key, program, flags in [
    ("postgres", "postgres", "POSTGRES_PASSWORD", "pg_dumpall", []),
    ("mysql", "admin", "ADMIN_PASSWORD", "mysqldump",
     ["--all-databases", "--routines", "--events", "--triggers", "--single-transaction", "--hex-blob"]),
]:
    with client(engine, "megasamples-" + engine, user, old[key], program) as command:
        with (backup / (engine + ".sql")).open("w") as output:
            subprocess.run([*command, *flags], stdout=output, stderr=subprocess.PIPE, check=True)
PY_LOGICAL_BACKUP
test -s "$BACKUP_DIR/postgres.sql"
test -s "$BACKUP_DIR/mysql.sql"
chmod 600 "$BACKUP_DIR/"*.sql

# Repeat the preparation gates immediately before downtime; any failure aborts here.
python3 "$UPGRADE_HELPER" check-images "$BACKUP_DIR"
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py check-metadata "$METADATA_BUNDLE" </dev/null
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py ports --allow-running-project sql-megasamples </dev/null
# Downtime starts here. SQLite consumers must be stopped before copying its files.
# Stop every configured console as well as all engines; keep the proxy services running.
TEARDOWN_ATTEMPT=$(date -u +%Y%m%dT%H%M%S%N)
TEARDOWN_PHASE=stop
TEARDOWN_SNAPSHOT="$BACKUP_DIR/stop-before-$TEARDOWN_ATTEMPT.json"
EXITED_RECEIPT=
python3 "$UPGRADE_HELPER" snapshot "$TEARDOWN_SNAPSHOT" --project sql-megasamples \
  --engine megasamples-postgres --engine megasamples-mysql --engine megasamples-sqlite
save_context
printf '%s\n' "$TEARDOWN_ATTEMPT" >> "$BACKUP_DIR/stop.log.timestamps"
if docker compose -p sql-megasamples -f compose.yaml stop >> "$BACKUP_DIR/stop.log" 2>&1; then
  printf '0\n' >> "$BACKUP_DIR/stop.log.exit-code"
else
  STOP_RC=$?
  printf '%s\n' "$STOP_RC" >> "$BACKUP_DIR/stop.log.exit-code"
  echo 'STOP: inspect stop.log and apply the four-check teardown procedure below.'
  exit "$STOP_RC"
fi
EXITED_RECEIPT="$BACKUP_DIR/stop-exited-$TEARDOWN_ATTEMPT.json"
python3 "$UPGRADE_HELPER" exited "$TEARDOWN_SNAPSHOT" "$EXITED_RECEIPT"
save_context
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
# Content AND metadata digest of the cold inputs, in the same rootless UID/GID namespace.
# Keep these directories unchanged. Recompute this exact stream before any rollback restore.
bash -c 'set -o pipefail; podman unshare tar --sort=name --numeric-owner --format=gnu --atime-preserve=system -C "$1" -cf - postgres mysql sqlite sqlite-shared | sha256sum > "$1/cold-copies.stream.sha256"' sh "$BACKUP_DIR"
# Record and retain old anonymous volumes. Do not run down -v, reset, prune or clean-all.
podman volume ls --format json > "$BACKUP_DIR/volumes.json"

# Set all four NEW passwords only after old-server backups are complete.
# The original .env stays private in BACKUP_DIR; no secret value is printed or exported.
umask 077
ms_tool "$MEGASAMPLES_PY" - <<'PY_ROTATE_PASSWORDS'
import os, pathlib, secrets
from megasamples import config
path = pathlib.Path(".env")
lines = path.read_text().splitlines() if path.exists() else []
keys = config.PASSWORD_DEFAULTS
lines = [line for line in lines if line.split("=", 1)[0].strip().removeprefix("export ") not in keys]
lines += [key + "=" + secrets.token_urlsafe(36) for key in keys]
with path.open("w") as stream:
    os.fchmod(stream.fileno(), 0o600)
    stream.write("\n".join(lines) + "\n")
PY_ROTATE_PASSWORDS
chmod 600 .env
# Render the corrected credential wiring; all consoles and engines are still stopped.
ms_tool make compose PY="$MEGASAMPLES_PY" </dev/null
# Clear the shared SQLite copy only after its verified cold backup. Retain old anonymous volumes.
docker compose -p sql-megasamples -f compose.yaml run --rm --no-deps -T --entrypoint sh sqlite -c \
  'rm -f /shared/*.sqlite /shared/*.sqlite-wal /shared/*.sqlite-shm /shared/*.sqlite-journal'
# Use the imported images with fresh anonymous data copies. Never rebuild in this cutover step.
# No exemptions after stop: check again before engines, then consoles are started.
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py ports </dev/null
docker compose -p sql-megasamples -f compose.yaml up -d --force-recreate --renew-anon-volumes \
  --no-deps --wait mysql postgres sqlite
# Fresh console containers apply the new passwords and reseed CloudBeaver from the backed-up state.
ms_tool "$MEGASAMPLES_PY" docs/validation/live-upgrade.py ports --consoles-only </dev/null
docker compose -p sql-megasamples -f compose.yaml up -d --force-recreate --wait \
  landing phpmyadmin adminer dbgate cloudbeaver
ms_tool make console-page PY="$MEGASAMPLES_PY" </dev/null
# Require the running image IDs to remain exactly the compared candidate IDs.
ms_tool "$MEGASAMPLES_PY" - <<'PY_CHECK_CANDIDATE_IDS'
import json, pathlib, subprocess
candidate = json.loads(pathlib.Path("docs/validation/credential-prerequisite-2026-11-18.json").read_text())["prepared_candidate"]
for service, entry in candidate["services"].items():
    actual = subprocess.check_output(["docker", "inspect", "-f", "{{.Image}}", "megasamples-" + service], text=True).strip()
    assert actual.removeprefix("sha256:") == entry["image_id"].removeprefix("sha256:"), service + " differs from compared image"
PY_CHECK_CANDIDATE_IDS
# Require every new password to work and every old one to be refused by authentication.
ms_tool "$MEGASAMPLES_PY" docs/validation/verify-configured-passwords.py --previous-dir "$BACKUP_DIR" </dev/null
ms_tool make test-console PY="$MEGASAMPLES_PY" </dev/null
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

The Compose stop above includes every configured console, so SQLite consumers are closed before either copy. The cutover commands recreate the configured consoles and regenerate their local help pages. The new containers receive the freshly generated `.env` credentials. Keep this file mode 0600 and do not print or source it. No password belongs in a process argument, diagnostic log, screenshot or validation receipt.

### Conditional rootless network teardown failure (stop AND rollback down)

The first live run saw `kill network process: permission denied` during Compose stop (SQLite)
and rollback down (MySQL). **The root cause is unknown.** The isolated attempts are recorded in
the [first-run evidence](live-upgrade-evidence.md); a networking startup failure is not proof of
the teardown cause. Do not suppress arbitrary Compose errors or add a sudo/host-network workaround.

Both guarded commands stop the shell on failure. Preserve the exit code and private log. If the
only failure is this teardown error, the coordinator may resume **after** all four checks below
pass, with a dated receipt. A failed or inconclusive check keeps the procedure stopped.

The guards save the actual Compose status beside each log as `*.log.exit-code` before exiting.
To perform the four checks after that shell exits, start a fresh Bash maintenance shell, set
`BACKUP_DIR` to the exact retained directory from the receipt, then run
`. "$BACKUP_DIR/resume-context.bash"`. This restores the original directory, selected socket,
tooling function and non-secret paths/IDs without rerunning preparation or password generation.
It does not start, stop or restore a container. Inspect the saved exit status/log and carry out
all four checks before resuming at the specified block. Never source `.env` for recovery.

Run these commands from that restored context, writing a new receipt on every attempt.
The helper snapshots select name, ID, state, PID, exit code, OOM flag, network namespace and
mount source/destination pairs by format string; they never retain full inspection output.
Before `down`, the guarded `stop` and exited receipt are mandatory. A partially removed
container is accepted only against its exact ID in that exited receipt.

```sh
CHECK_ID=$(date -u +%Y%m%dT%H%M%S%N)
# 1. Engines exited, false running flag, PID 0; ordinary engine exit code must be 0.
# Also checks recorded console IDs, even if a container lost its project label.
# Expected: Passed: exited. Missing without an exited receipt is a refusal.
set --
if test -n "$EXITED_RECEIPT"; then set -- --removed-with "$EXITED_RECEIPT"; fi
python3 "$UPGRADE_HELPER" exited "$TEARDOWN_SNAPSHOT" \
  "$BACKUP_DIR/four-check-exited-$CHECK_ID.json" "$@"
# Exit 137 requires explicit coordinator acknowledgment of CRASH-CONSISTENT data;
# after recording that decision, rerun ONLY the failed exited gate, with a new output
# path and --allow-crash-consistent. Other engine exit codes or an OOM refuse.

# 2. No deployment containers running. Expected: EMPTY, plus Passed: exited above.
podman ps --filter label=com.docker.compose.project=sql-megasamples -q
# The upgrade-tools container is separate and must have no deployment data mount.

# 3. No process holding any recorded data mount. 4. No unattributed network helper.
# Expected: {"holders": [], "helpers": [], "unreadable": []}, status 0.
# The scanner reads comm, namespace/cgroup, root/cwd/fd and mount roots/mountpoints;
# it never reads process environments or argument lists.
podman unshare python3 "$BACKUP_DIR/quiescence.py" "$TEARDOWN_SNAPSHOT" \
  > "$BACKUP_DIR/process-evidence-$CHECK_ID.json"
```

The scanner is deliberately conservative: any holder, helper or unreadable PID returns 1.
Inspect the private evidence. A holder blocks continuation. Attribute remaining helpers and
unreadable processes using `/proc/<pid>/ns/net`, `/proc/<pid>/ns/mnt`, `/proc/<pid>/cgroup`,
`/proc/<pid>/fd` and parent PID from `/proc/<pid>/status`, compared with the retained container
IDs/PIDs/namespaces/mount pairs. Record each exclusion and its evidence in the four-check
receipt; unresolved attribution blocks continuation. Helpers for a separate isolated store
may remain with that attribution. Never blanket-kill helpers or change the LAN forwarders.
Rerun the scanner immediately before continuing to catch changes during process enumeration.

Capture available kernel/AppArmor diagnostics for the failure's timestamp, without host changes:

```sh
# Set FAILURE_SINCE / FAILURE_UNTIL around the UTC timestamp in *.log.timestamps.
: "${FAILURE_SINCE:?Set failure window start}" "${FAILURE_UNTIL:?Set failure window end}"
if journalctl -k --since "$FAILURE_SINCE" --until "$FAILURE_UNTIL" --no-pager \
  > "$BACKUP_DIR/kernel-$CHECK_ID.log" 2> "$BACKUP_DIR/kernel-$CHECK_ID.error"; then
  printf '0\n' > "$BACKUP_DIR/kernel-$CHECK_ID.exit-code"
else
  KERNEL_RC=$?
  printf '%s\n' "$KERNEL_RC" > "$BACKUP_DIR/kernel-$CHECK_ID.exit-code"
  echo 'Not run: kernel/AppArmor diagnostics unavailable; retain the error.'
fi
# Preserve status/output; permission refusal or absent journal is Not run, not proof
# that there were no AppArmor denials. Do not use sudo or alter logging policy.
```

For **stop**, after all four checks, set `EXITED_RECEIPT` to the new exited receipt,
run `save_context`, and resume at final workspace/cold-copy collection. For **rollback-stop**,
do the same and resume at the pre-down snapshot, then the guarded down. For **rollback-down**,
resume at branch/configuration restoration after all four checks; if exited containers remain,
retry only the same scoped guarded down (append logs, retain the prior exited receipt), then
repeat the four checks. Never use `down -v`, force-remove an active mount, repeat preparation,
regenerate passwords or restart candidates implicitly. Preserve original volumes and inputs.

In the isolated 30-dataset rehearsal, replacing all three engine containers and restoring SQLite's shared files took 121.65 seconds. Individual whole-engine resets took 23.07 seconds (MySQL), 26.4 seconds (PostgreSQL) and 92.4 seconds (SQLite). A stop/start of the existing eight-service stack, without replacing data volumes, took 38.66 seconds and preserved every recorded count, SQLite hash and inserted probe row. These measurements exclude cold-backup time and the coordinator's DataIntent checks and predate this follow-up; the added datasets have separate measurements in “Added dataset cost and scope”. Initial stack startup took 328.32 seconds while this custom store waited for health scheduling; real probes then completed successfully through the isolated-only runner. These are observed preparation/outage components, not a full-manifest downtime guarantee. The complete full-Contoso repository check against the shipped MySQL configuration took 1,736.02 seconds in this rehearsal, dominated by an indexed nested-loop constraint query. If the maintenance window includes that full integrity audit, budget its verification time as well as startup, cold copies and DataIntent tests.

Historical PR #11 calibration (superseded for MySQL version selection): the 2026-11-17 cold-readiness follow-up measured six fresh-volume starts per PR #11 image,
plus six each for the retained main MySQL and SQLite images. Starts were sequential, with
engine and comparison order reversed between rounds, no published ports and no cache dropping.
The measured standalone-image components are:

| Engine | Baked data files (bytes) | Cold copy/run range (s) | Query after run returns (s) | Cold-copy gate (s) | Server gate (s) |
|---|---:|---:|---:|---:|---:|
| MySQL | 22,953,654,938 | 32.071–83.762 | 1.431–2.205 | 170 | 30 |
| PostgreSQL | 22,443,408,360 | 40.372–85.274 | 0.414–0.607 | 180 | 30 |
| SQLite | 19,179,147,264 | 30.926–71.862 | 0.073–0.172 | 150 | 30 |

MySQL's first successful query followed its server-ready log by 0.039–0.347 s; PostgreSQL's
by 0.273–0.324 s. SQLite has no server: its shell query followed the container's process-start
event by 0.080–0.183 s. The server gate starts earlier, when detached `run` returns, and retains
the full independent 30-second limit for every engine. Cold copy/run includes volume
materialization and runtime launch overhead. Baked data bytes sum immutable regular-file sizes,
counting hard links once; allocated blocks and complete image sizes are recorded separately.

The old MySQL image contained 21,653,516,735 data bytes and copied/launched in 31.803–69.677 s;
the old SQLite image contained 19,008,032,768 bytes and took 28.310–65.938 s. The new contents
increase these file totals by about 6.0% and 0.9%. Timing ranges overlap widely; they do not
establish a stable linear cost per added byte. Use the full observed range when planning.

All engines use the same rule in `megasamples/engines/image_startup.py`: twice the largest
measured cold copy/run interval for that engine, rounded up to ten seconds, considering both
images where compared. The server interval is checked separately. The copy allowances plus
30 seconds per server total 590 seconds if all three starts are serialized; these are validation
ceilings, not measured downtime. The standalone checks exclude Compose health scheduling,
SQLite's additional shared-console copy, cold backups, fingerprint verification, DataIntent
checks and rollback. Keep the separately observed 269.27-second replacement-stack startup and
200.15-second five-pair verification in view; no complete live maintenance window is verified.
The [cold-readiness evidence](cold-readiness-evidence.md) and
[receipt](validation/cold-readiness-2026-11-17.json) preserve all samples and final validation.

The outage lasts from the first stop through readiness and verification, plus any rollback.
Reserve those additional components separately. Rebuilding before cutover avoids putting
download/conversion time in the outage.

## Verify before resuming clients

```sh
podman ps --format '{{.Names}} {{.Status}} {{.Ports}}'
podman exec megasamples-postgres psql -U postgres -Atc 'SHOW server_version'
ms_tool "$MEGASAMPLES_PY" -c 'from megasamples.engines import get; print(get("mysql").query("megasamples-mysql", "SELECT VERSION()"))' </dev/null
podman exec megasamples-sqlite sqlite3 :memory: 'SELECT sqlite_version()'
podman exec megasamples-postgres psql -U postgres -d megasamples -Atc \
  'SELECT name,row_counts FROM datasets ORDER BY name'
ms_tool "$MEGASAMPLES_PY" -c 'from megasamples.engines import get; print(get("mysql").registry_rows("megasamples-mysql"))' </dev/null
podman exec megasamples-sqlite sqlite3 /data/megasamples.sqlite \
  'SELECT name,row_counts FROM datasets ORDER BY name'
# Actual added-dataset fingerprints against the replacement containers, without pinning fixtures.
ms_tool "$MEGASAMPLES_PY" -c ' </dev/null
import json, pathlib, shutil, subprocess
from megasamples import config, verify
from megasamples.engines.mysql import server as mysql
from megasamples.engines.postgres import server as pg
from megasamples.engines.sqlite import adapter as sq
root = pathlib.Path.cwd()
secret = config.passwords()
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

Verify the forwards **from the host**, first at the protocol level and then with host clients.
Rootless engine containers cannot reliably connect to their own host's LAN address.
Use host clients or native clients installed in the prepared upgrade-tools container, which is
started above with `--network host`. Do not use `credentials.client()` for forwarded checks:
it executes inside the engine container. Prepare and validate client binaries inside the tools
image during isolated preparation; the retained tools image does not currently supply them.
If neither host nor prepared tools clients are available, record **Not run** and arrange
coordinator verification. Do not install packages on the host.

```sh
# Host maintenance shell. Obtain these endpoints from private forwarder configuration or
# the listening sockets (ss -ltn); never hard-code this deployment's LAN address in Git.
: "${FORWARD_HOST:?Set the configured LAN listener address}"
: "${PG_FORWARD_PORT:?Set the configured PostgreSQL forward port}"
: "${MYSQL_FORWARD_PORT:?Set the configured MySQL forward port}"
python3 "$UPGRADE_HELPER" forwarded-protocol postgres "$FORWARD_HOST" "$PG_FORWARD_PORT"
python3 "$UPGRADE_HELPER" forwarded-protocol mysql "$FORWARD_HOST" "$MYSQL_FORWARD_PORT"
# Host client sign-ins: enter DEMO_PASSWORD privately from .env at each prompt.
# PostgreSQL SSLRequest and a MySQL greeting alone do not establish authentication.
psql -X -W -h "$FORWARD_HOST" -p "$PG_FORWARD_PORT" -U demo -d megasamples \
  -v ON_ERROR_STOP=1 -tAc 'SELECT current_user, version(); SELECT count(*) FROM datasets'
mysql --no-defaults --host="$FORWARD_HOST" --port="$MYSQL_FORWARD_PORT" --user=demo --password \
  --batch --skip-column-names --execute='SELECT CURRENT_USER(), VERSION(); SELECT count(*) FROM megasamples.datasets'
```

Alternatively, with native clients prepared in the **host-network tools container**, use its
terminal for private password prompts. First require its namespace to match the host and both
binaries to exist. This method is a coordinator backlog action; **Not run against live forwards**
by this documentation task.

```sh
TOOLS_PID=$(podman inspect -f '{{.State.Pid}}' "$UPGRADE_TOOLS_CONTAINER")
test "$(readlink /proc/$$/ns/net)" = "$(readlink /proc/$TOOLS_PID/ns/net)"
podman exec "$UPGRADE_TOOLS_CONTAINER" sh -c 'command -v psql && command -v mysql' </dev/null
# -it is intentional here: prompts read from the operator's terminal, not pasted script input.
podman exec -it "$UPGRADE_TOOLS_CONTAINER" psql -X -W -h "$FORWARD_HOST" \
  -p "$PG_FORWARD_PORT" -U demo -d megasamples -v ON_ERROR_STOP=1 -tAc \
  'SELECT current_user, version(); SELECT count(*) FROM datasets'
podman exec -it "$UPGRADE_TOOLS_CONTAINER" mysql --no-defaults --host="$FORWARD_HOST" \
  --port="$MYSQL_FORWARD_PORT" --user=demo --password --batch --skip-column-names \
  --execute='SELECT CURRENT_USER(), VERSION(); SELECT count(*) FROM megasamples.datasets'
```

The [Podman network reference](https://docs.podman.io/en/latest/markdown/podman-run.1.html),
read **2026-11-18 18:03:54 UTC**, documents host network namespace sharing. It does not establish
that either forwarded sign-in was executed.

Require the `demo` identity, expected runtime versions and complete expected registry counts.
The first live run proved the two protocols from the host; forwarded client sign-ins were
**Not run**, so do not describe the first run as authenticated forwarded-SQL verification.
TLS certificate validation was also **Not run**. The protocol probe does not validate a certificate.

Compare the complete registry sets and each table's actual row counts with the validated configuration and catalogue. Registry text alone is not an actual count check. Run the repository's image tests before cutover and the same validation queries against the replacement servers afterwards. Live-feed counts/checksums must match the hub snapshot built with these images; historical manifest counts are floors for those feeds. Verify `demo` remains read-only and `admin` can write using disposable probe tables, then remove the probes.

Confirm PostgreSQL binds to `127.0.0.1:5432` and MySQL to `127.0.0.1:3306`. Run the coordinator's DataIntent server-bound suites against both the local endpoints and the configured forwarded endpoints from the host. The proxies continue forwarding to the same local ports and require no changes. Resume clients only after these checks pass.

The added-dataset check above uses actual server tables and a fresh copy of the shipped SQLite file.
It must pass exact counts and applicable canonical fingerprints, foreign keys, indexes and views.
For BTS, also require 6,942 airport rows and zero unmatched origin/destination rows across 539,747
flights. Check the complete console lists: three new MySQL databases and the supported warehouse
ports, including the new SQLite connection in CloudBeaver and DbGate. Unsupported pairs must not
be presented as available. Preserve the result logs with the maintenance receipt.

## Roll back

```sh
# Fresh Bash maintenance shell, also when the failed cutover shell exited.
# Set BACKUP_DIR to the exact private directory in the maintenance receipt.
: "${BACKUP_DIR:?Set the retained backup directory}"
. "$BACKUP_DIR/resume-context.bash"
```

Keep clients paused. Do not remove any backup, original image tag, original branch, original anonymous volume, or proxy service.

The saved pre-upgrade configuration, console tree, images and cold volumes also roll back these
new datasets. Restoring them removes the added databases/files and their console connections as
part of restoring the original deployment. First retain any application writes made in the new
datasets; the pre-upgrade cold copies cannot contain those writes. Do not use `make reset` for
rollback: it restores the new image contents, including the added datasets.

```sh
# Verify immutable rollback inputs before restoring anything.
python3 "$UPGRADE_HELPER" check-images "$BACKUP_DIR"
(cd "$BACKUP_DIR" && sha256sum -c original-configurations.sha256)
bash -c 'set -o pipefail; actual=$(podman unshare tar --sort=name --numeric-owner --format=gnu --atime-preserve=system -C "$1" -cf - postgres mysql sqlite sqlite-shared | sha256sum); test "$actual" = "$(cat "$1/cold-copies.stream.sha256")"' sh "$BACKUP_DIR"
if test -f .env; then cp .env "$BACKUP_DIR/failed-candidate.env"; chmod 600 "$BACKUP_DIR/failed-candidate.env"; fi
tar -xf "$BACKUP_DIR/original-configurations.tar" -C "$BACKUP_DIR"
# Stop candidates BEFORE down can remove evidence. Keep every failed candidate volume.
TEARDOWN_ATTEMPT=$(date -u +%Y%m%dT%H%M%S%N)
TEARDOWN_PHASE=rollback-stop
TEARDOWN_SNAPSHOT="$BACKUP_DIR/rollback-stop-before-$TEARDOWN_ATTEMPT.json"
EXITED_RECEIPT=
python3 "$UPGRADE_HELPER" snapshot "$TEARDOWN_SNAPSHOT" --project sql-megasamples \
  --engine megasamples-postgres --engine megasamples-mysql --engine megasamples-sqlite
save_context
printf '%s\n' "$TEARDOWN_ATTEMPT" >> "$BACKUP_DIR/rollback-stop.log.timestamps"
if docker compose -p sql-megasamples -f compose.yaml stop >> "$BACKUP_DIR/rollback-stop.log" 2>&1; then
  printf '0\n' >> "$BACKUP_DIR/rollback-stop.log.exit-code"
else
  STOP_RC=$?
  printf '%s\n' "$STOP_RC" >> "$BACKUP_DIR/rollback-stop.log.exit-code"
  echo 'STOP: apply the four checks to rollback-stop before down.'
  exit "$STOP_RC"
fi
EXITED_RECEIPT="$BACKUP_DIR/rollback-stop-exited-$TEARDOWN_ATTEMPT.json"
python3 "$UPGRADE_HELPER" exited "$TEARDOWN_SNAPSHOT" "$EXITED_RECEIPT"
# Snapshot again immediately before down, with stopped PIDs/exit codes and mounts.
TEARDOWN_PHASE=rollback-down
TEARDOWN_SNAPSHOT="$BACKUP_DIR/rollback-down-before-$TEARDOWN_ATTEMPT.json"
python3 "$UPGRADE_HELPER" snapshot "$TEARDOWN_SNAPSHOT" --project sql-megasamples \
  --engine megasamples-postgres --engine megasamples-mysql --engine megasamples-sqlite
save_context
printf '%s\n' "$TEARDOWN_ATTEMPT" >> "$BACKUP_DIR/rollback-down.log.timestamps"
# Restore original configuration and its original branch (never reset a pushed branch).
if docker compose -p sql-megasamples -f compose.yaml down >> "$BACKUP_DIR/rollback-down.log" 2>&1; then
  printf '0\n' >> "$BACKUP_DIR/rollback-down.log.exit-code"
else
  DOWN_RC=$?
  printf '%s\n' "$DOWN_RC" >> "$BACKUP_DIR/rollback-down.log.exit-code"
  echo 'STOP: inspect rollback-down.log and apply the four-check teardown procedure below.'
  exit "$DOWN_RC"
fi
python3 "$UPGRADE_HELPER" exited "$TEARDOWN_SNAPSHOT" \
  "$BACKUP_DIR/rollback-down-exited-$TEARDOWN_ATTEMPT.json" --removed-with "$EXITED_RECEIPT"
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
if test -f "$BACKUP_DIR/.env"; then cp "$BACKUP_DIR/.env" ./.env; chmod 600 .env; else rm -f .env; fi
# Validate all per-image digests/configuration IDs before loading, then explicitly restore tags.
python3 "$UPGRADE_HELPER" load-images "$BACKUP_DIR"
while read -r tag expected repo_digests; do
  actual=$(podman image inspect -f '{{.Id}}' "$tag")
  test "${actual#sha256:}" = "${expected#sha256:}"
done < "$BACKUP_DIR/rollback-image-ids.txt"
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
# Standalone retained helper reads the original port selection, even on the old branch.
python3 "$UPGRADE_HELPER" ports --port-config "$BACKUP_DIR/original-ports.json" \
  --services-file "$BACKUP_DIR/original-running-services.txt"
set --
RESTORE_CLOUDBEAVER=0
while IFS= read -r service; do
  if test "$service" = cloudbeaver; then RESTORE_CLOUDBEAVER=1; else set -- "$@" "$service"; fi
done < "$BACKUP_DIR/original-running-services.txt"
test "$#" -gt 0
docker compose -p sql-megasamples -f compose.yaml -f "$BACKUP_DIR/rollback.override.yaml" \
  -f "$BACKUP_DIR/rollback-consoles.override.json" up -d --wait "$@"
if test "$RESTORE_CLOUDBEAVER" = 1; then
  python3 "$UPGRADE_HELPER" ports --port-config "$BACKUP_DIR/original-ports.json" --service cloudbeaver
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

For the first live run's retained layout, the helper reads `saved_images` in
`phase-a-resume-receipt.json` when `rollback-images.sha256` names only the malformed
`rollback-images.tar`. It verifies every service-named replacement archive's receipt digest,
configuration ID and complete tag/ID mapping before loading any archive. The malformed aggregate
is never loaded or rewritten. Keep that phase-A receipt beside the original checksum file.
Future backups use full-image-ID filenames and the per-image checksum list.

Rollback uses the retained pre-upgrade MySQL image identified in `rollback-image-ids.txt`, the
SHA-256-checked `rollback-image-<full-image-id>.tar` and `original-configurations.tar`, and the unchanged cold
copies whose deterministic tar stream (contents, ownership, permissions and symlink targets) must
match `cold-copies.stream.sha256`. Keep the three digest receipts with the private maintenance
receipt and verify them before restore. A local image may have no registry RepoDigest; its SHA-256
image ID and saved-archive digest remain mandatory. After loading, compare each saved tag's actual
image ID with its recorded ID before starting it. These are rollback inputs, not a reset of new data.

Rollback never starts the 9.7.2 image against the candidate data directory. Restore the retained pre-upgrade cold copy and exact saved image/configuration; keep failed candidate volumes separately. The fact that this is a same-LTS patch upgrade does not replace that required rollback discipline.

Rollback keeps all original engine/console images in per-image archives, the original complete console/configuration tree, credentials, original Python environment and an immutable rollback branch. The new tools container and new environments are separate resources. Keep them stopped or retained for diagnosis after rollback; never replace the original tooling with the new dependency set. The original live deployment may have no running consoles: the saved running-service list ensures rollback does not start additional ones. Newly built console images are never substituted for their saved rollback image IDs.

## Isolation used for rehearsal

The rehearsal's settings and generated credentials are in the upgrade clone's `megasamples.yaml` and `.env` (mode 0600). Its socket is `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/podman.sock`, project `megasamples-upgrade`; ports are PostgreSQL `127.0.0.1:15432`, MySQL `127.0.0.1:13306`, and consoles `127.0.0.1:18080` through `:18084`. It uses the isolated `slirp4netns` override under `build/upgrade-evidence/containers-slirp.conf` because Pasta failed to access the custom runroot's network namespace. Source `env.sh` and set `CONTAINERS_CONF_OVERRIDE` to that absolute file before starting its socket. The isolated API process can be stopped without stopping its running containers; start it again to use Docker Compose or the repository's commands. None of these settings belongs in the live checkout. Automatic health probes were not observed in this custom store. The temporary native runner `build/upgrade-evidence/run-isolated-healthchecks.py` drives the actual configured checks only for the three isolated engine IDs, validating their Compose labels. Its current PID and last results are in `healthcheck-runner-state.json`; the client follow-up restarted a stopped predecessor and records its launcher in `build/client-evidence/health-probe-runner.pid`; it does not require the API socket. Keep it while exercising the rehearsal. After the coordinator is finished with that stack, `touch build/upgrade-evidence/healthcheck-runner.stop` stops only this helper. Do not copy that workaround into the live service configuration.

After successful cutover or rollback, if this maintenance shell started an API process, stop only that process (the stack keeps running):

```sh
if test -n "${MEGASAMPLES_LIVE_API_PID:-}"; then
  kill "$MEGASAMPLES_LIVE_API_PID"
fi
```
