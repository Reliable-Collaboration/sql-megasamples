# Client upgrade evidence

Read/capture time: 2026-11-17T04:24:43.505534+00:00. Branch `upgrade/latest-stable-clients` starts from completed engine branch commit `7b3d5a35966d82abd69598ed795b9610ddf27c35`. Engine PR [9](https://github.com/Reliable-Collaboration/sql-megasamples/pull/9) was made ready and merged with merge commit `b80583cd28b02f144c1f19ddad68076c636fef4f`. No live deployment action was executed.

The baseline already included the latest console tags and native engine clients from PR 9. Those exact vendor pins are retained. This follow-up updates the loader binaries/library, configured embedded console drivers, every resolved Python dependency, reproducible endpoint tooling, and optional Oracle query/load clients. Version/support statements below use primary publisher pages or registries, with exact read times in `clients.lock.yaml` and the receipt. Baseline observations come from the isolated images and the [base tree](https://github.com/Reliable-Collaboration/sql-megasamples/tree/7b3d5a35966d82abd69598ed795b9610ddf27c35), read 2026-11-17T04:20:19.886547+00:00.

## Client inventory

| Client | Before this follow-up | Selected | Primary source / read time UTC |
|---|---|---|---|
| psql, pg_dump, pg_dumpall, pg_restore, pg_isready | 18.7 | 18.7 | [Publisher source](https://www.postgresql.org/docs/release/18.7/), 2026-11-17T02:40:50.644194+00:00 |
| mysql, mysqladmin, mysqldump, mysqlsh | 26.10.0 | 26.10.0 | [Publisher source](https://dev.mysql.com/doc/relnotes/mysql/26.10/en/news-26-10-0.html), 2026-11-17T02:40:51.624426+00:00 |
| sqlite3 | 3.54.1 | 3.54.1 | [Publisher source](https://sqlite.org/download.html), 2026-11-16T18:58:36.461111+00:00 |
| mysql, mysqladmin, mysqldump | MariaDB 11.8.6 (unversioned Debian default-mysql-client) | 26.10.0 | [Publisher source](https://dev.mysql.com/doc/relnotes/mysql/26.10/en/news-26-10-0.html), 2026-11-17T02:40:51.624426+00:00 |
| sysbench | 1.0.20+ds-7 | 1.0.20+ds-7 | [Publisher source](https://github.com/akopytov/sysbench/releases), 2026-11-17T03:32:12.781355+00:00 |
| landing | 1.30.6 | 1.30.6 | [Publisher source](https://nginx.org/en/download.html), 2026-11-16T18:58:36.520324+00:00 |
| cloudbeaver | 26.2.5 | 26.2.5 | [Publisher source](https://hub.docker.com/v2/repositories/dbeaver/cloudbeaver/tags?page_size=20), 2026-11-16T18:58:36.671862+00:00 |
| dbgate | 7.3.6 | 7.3.6 | [Publisher source](https://hub.docker.com/v2/repositories/dbgate/dbgate/tags?page_size=20), 2026-11-16T18:58:36.830920+00:00 |
| adminer | 6.3.0 | 6.3.0 | [Publisher source](https://www.adminer.org/), 2026-11-16T18:58:36.571475+00:00 |
| phpmyadmin | 5.2.3 | 5.2.3 | [Publisher source](https://www.phpmyadmin.net/downloads/), 2026-11-16T18:58:36.655862+00:00 |
| cloudbeaver-mysql-connector-j | 8.2.0 | 26.10.0 | [Publisher source](https://repo.maven.apache.org/maven2/com/mysql/mysql-connector-j/maven-metadata.xml), 2026-11-17T02:42:57.279826+00:00 |
| cloudbeaver-sqlite-jdbc | 3.48.0.0 | 3.54.1.0 | [Publisher source](https://repo.maven.apache.org/maven2/org/xerial/sqlite-jdbc/maven-metadata.xml), 2026-11-17T02:42:57.355956+00:00 |
| postgresql | 42.7.14 | 42.7.14 | [Publisher source](https://repo.maven.apache.org/maven2/org/postgresql/postgresql/maven-metadata.xml), 2026-11-17T02:42:57.194811+00:00 |
| mysql2 | 3.24.6 | 3.24.6 | [Publisher source](https://registry.npmjs.org/mysql2/latest), 2026-11-17T02:42:57.655541+00:00 |
| pg | 8.23.1 | 8.23.1 | [Publisher source](https://registry.npmjs.org/pg/latest), 2026-11-17T02:42:57.860116+00:00 |
| better-sqlite3 | 13.0.3 | 13.2.0 | [Publisher source](https://registry.npmjs.org/better-sqlite3/latest), 2026-11-17T02:42:58.043635+00:00 |
| sysbench-connector-c | 3.4.9 | 3.4.11 | [Publisher source](https://mariadb.org/connector-c/all-releases/), 2026-11-17T02:43:45.108646+00:00 |
| adminer-libpq | 18.6 | 18.7-r0 | [Publisher source](https://pkgs.alpinelinux.org/package/v3.24/main/x86_64/libpq), 2026-11-17T04:06:09.391699+00:00 |
| psycopg-libpq | 18.6 (initial binary-wheel probe) | 18.7 | [Publisher source](https://apt.postgresql.org/pub/repos/apt/dists/trixie-pgdg/main/binary-amd64/Packages.gz), 2026-11-17T04:09:43.044818+00:00 |
| sqlcmd (ODBC implementation), bcp, msodbcsql18 | same pinned engine-tool distribution | 18.7.1.1 | [Publisher source](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver17), 2026-11-17T02:40:57.415308+00:00 |
| SQL*Plus, SQL*Loader | 23.26.3.0.0 | 23.26.4.0.0 | [Publisher source](https://www.oracle.com/database/technologies/instant-client/linux-x86-64-downloads.html), 2026-11-17T03:33:50.395350+00:00 |
| Playwright screenshot client | 1.65.0 | 1.65.0 | [Publisher source](https://playwright.dev/python/docs/release-notes), 2026-11-17T02:40:57.779038+00:00 |

All configured connection paths were audited: `megasamples/consoles.py`, console templates, loader Dockerfiles, engine servers/adapters, reset/dump/restore helpers, Oracle/SQL Server source helpers, and screenshot tooling. `pg_dumpall`, `pg_isready` and `mysqladmin` are included alongside the specifically requested clients. No SQLAlchemy, psycopg2, python-oracledb, mysql-connector-python, pgloader or SQLcl execution/import is present in the current project. Knowledge-only mentions of pyarrow/mwxml are historical, not installed project dependencies. Unconfigured third-party drivers bundled inside a vendor console are not separately selected connections. PHP mysqlnd follows the current vendor PHP runtime. Adminer's libpq and the endpoint-test libpq are separately pinned to 18.7; runtime versions and UI/wire tests are recorded separately.

## Python lock

Every external resolved package equals the current stable version in the captured publisher metadata. Direct requirements and the endpoint-test driver are exact in `pyproject.toml`; `uv lock --upgrade`, `uv sync --locked` and `uv lock --check` ran inside the isolated tools container. The existing README procedure is made explicit; no host package installation occurred. The optional Windows/older-Python dependency branches are resolved/hashed, not execution-tested.

| Package | Before | Selected | Publisher source / read time UTC |
|---|---|---|---|
| backports-zstd | 1.7.0 | 1.8.0 | [Publisher source](https://pypi.org/pypi/backports-zstd/json), 2026-11-17T02:39:53.263367+00:00 |
| brotli | 1.2.0 | 1.2.1 | [Publisher source](https://pypi.org/pypi/brotli/json), 2026-11-17T02:39:53.470571+00:00 |
| brotlicffi | 1.2.0.2 | 1.2.1.0 | [Publisher source](https://pypi.org/pypi/brotlicffi/json), 2026-11-17T02:39:53.565570+00:00 |
| cffi | 2.1.1 | 2.1.1 | [Publisher source](https://pypi.org/pypi/cffi/json), 2026-11-17T02:39:53.825212+00:00 |
| colorama | 0.4.6 | 0.4.6 | [Publisher source](https://pypi.org/pypi/colorama/json), 2026-11-17T02:39:54.192197+00:00 |
| cryptography | 50.0.1 | 50.0.2 | [Publisher source](https://pypi.org/pypi/cryptography/json), 2026-11-17T02:39:54.385937+00:00 |
| duckdb | 1.5.5 | 2.0.0 | [Publisher source](https://pypi.org/pypi/duckdb/json), 2026-11-17T02:39:54.569904+00:00 |
| inflate64 | 1.0.4 | 1.0.4 | [Publisher source](https://pypi.org/pypi/inflate64/json), 2026-11-17T02:39:54.749548+00:00 |
| iniconfig | 2.3.0 | 2.3.1 | [Publisher source](https://pypi.org/pypi/iniconfig/json), 2026-11-17T02:39:54.831508+00:00 |
| lxml | 6.1.3 | 6.1.3 | [Publisher source](https://pypi.org/pypi/lxml/json), 2026-11-17T02:39:55.142111+00:00 |
| multivolumefile | 0.2.3 | 0.2.3 | [Publisher source](https://pypi.org/pypi/multivolumefile/json), 2026-11-17T02:39:55.250535+00:00 |
| packaging | 26.3 | 26.3 | [Publisher source](https://pypi.org/pypi/packaging/json), 2026-11-17T02:39:55.339472+00:00 |
| pluggy | 1.6.0 | 1.7.0 | [Publisher source](https://pypi.org/pypi/pluggy/json), 2026-11-17T02:39:55.629026+00:00 |
| psutil | 7.2.2 | 7.2.2 | [Publisher source](https://pypi.org/pypi/psutil/json), 2026-11-17T02:39:55.785694+00:00 |
| psycopg | not declared | 3.3.9 | [Publisher source](https://pypi.org/pypi/psycopg/json), 2026-11-17T03:08:19.577223+00:00 |
| py7zr | 1.1.3 | 1.1.4 | [Publisher source](https://pypi.org/pypi/py7zr/json), 2026-11-17T02:39:56.024069+00:00 |
| pybcj | 1.0.8 | 1.0.8 | [Publisher source](https://pypi.org/pypi/pybcj/json), 2026-11-17T02:39:56.176487+00:00 |
| pycparser | 3.0 | 3.12 | [Publisher source](https://pypi.org/pypi/pycparser/json), 2026-11-17T02:39:56.339181+00:00 |
| pycryptodomex | 3.23.0 | 3.24.2 | [Publisher source](https://pypi.org/pypi/pycryptodomex/json), 2026-11-17T02:39:56.870877+00:00 |
| pygments | 2.21.0 | 2.21.0 | [Publisher source](https://pypi.org/pypi/pygments/json), 2026-11-17T02:39:56.982886+00:00 |
| pymysql | 1.2.0 | 1.2.4 | [Publisher source](https://pypi.org/pypi/pymysql/json), 2026-11-17T02:39:57.145327+00:00 |
| pyppmd | 1.3.1 | 1.3.1 | [Publisher source](https://pypi.org/pypi/pyppmd/json), 2026-11-17T02:39:57.423471+00:00 |
| pytest | 9.1.1 | 9.2.0 | [Publisher source](https://pypi.org/pypi/pytest/json), 2026-11-17T02:39:57.587685+00:00 |
| pyyaml | 6.0.3 | 6.0.3 | [Publisher source](https://pypi.org/pypi/pyyaml/json), 2026-11-17T02:39:57.705138+00:00 |
| sqlglot | 30.18.0 | 30.32.0 | [Publisher source](https://pypi.org/pypi/sqlglot/json), 2026-11-17T02:39:57.837512+00:00 |
| texttable | 1.7.0 | 1.7.3 | [Publisher source](https://pypi.org/pypi/texttable/json), 2026-11-17T02:39:58.055272+00:00 |
| typing-extensions | not declared | 4.16.0 | [Publisher source](https://pypi.org/pypi/typing-extensions/json), 2026-11-17T03:47:39.637215+00:00 |
| tzdata | not declared | 2026.6 | [Publisher source](https://pypi.org/pypi/tzdata/json), 2026-11-17T03:47:39.714806+00:00 |

## Compatibility and reproducibility

PostgreSQL uses the same major/minor tool distribution as its server. The [pg_dump compatibility rules](https://www.postgresql.org/docs/18/app-pgdump.html) were read 2026-11-17 02:40:51 UTC: this is a same-release dump/restore path, not a newer-server/older-client pairing. MySQL CLI/Shell are taken from the matching server image; the vendor [Connector/J release notes](https://dev.mysql.com/doc/relnotes/connector-j/en/news-26-10-0.html), read 2026-11-17 02:43:46 UTC, support servers from 8.4 upward. Actual CLI roundtrips, authentication and installed-console driver queries target the upgraded isolated server. No authentication plugin was downgraded.

The latest source-built Connector/C defaults to checking remote TLS peers. Its initial probe rejected the throwaway MySQL server's self-signed certificate. The [vendor TLS documentation](https://mariadb.com/docs/server/security/encryption/data-in-transit-encryption/securing-connections-for-client-and-server), read 2026-11-17 03:26 UTC, documents local versus remote behavior; the exact 3.4.11 source archive/read time/hash is in the lock. The TPC-C helper now joins only its build server's network namespace and uses 127.0.0.1, keeping the connector's defaults. A new-account caching_sha2 exchange/prepared-query probe and the actual repository one-warehouse loader passed. It retains cardinality/range checks and the documented nondeterministic-content exception.

CloudBeaver's original plugin lookup filenames are retained while their bytes are replaced by SHA-256-verified current MySQL and SQLite jars. DbGate's native module and complete dependency graph are installed with npm ci from a committed integrity lock. All inputs are exact vendor versions/digests. Adminer's current application also receives an exact libpq package update. The endpoint helper uses pure Psycopg and a separately pinned current PGDG libpq package, avoiding the older library bundled by the binary wheel. make up builds these extensions from small console contexts before starting the stack; generated connection settings and credentials are not included in those build contexts. Oracle clients likewise use vendor archive SHA-256 values in a separate image, leaving the Free server's own bootstrap tools intact. The new SQL*Plus/SQL*Loader wrappers are used by every query/load call in the optional verifier. Its explicit Free Use Terms gate still runs before any build/start action through make verify-oracle.

phpMyAdmin's [requirements](https://docs.phpmyadmin.net/en/release_5_2_3/require.html), read 2026-11-17 03:57:28 UTC, document MySQL 5.5 upward; [pgJDBC](https://jdbc.postgresql.org/download/), read at the same time, lists 42.7.14 for Java 8+ and PostgreSQL 8.4+ (testing from 9.1); actual PostgreSQL 18.7 catalogue listings pass. For phpMyAdmin, the actual current-server HTTP database lists were checked for both accounts. DbGate's exact patch announcement remains unverified, but its publisher numbered image equals the stable latest digest. CloudBeaver's publisher stable-tag policy and matching numbered digest are captured. Tests establish the configured connection paths; they are not a claim of separate vendor certification for every engine/feature combination.

## Test-first changes

- Client requirement/loader/console pin tests: Failed before changes; Passed afterward. The new Psycopg declaration also failed first and then passed.
- DuckDB 2.0 rejected true/false after cast pushdown; both existing full-archive and new core regressions failed before the boolean CASE/source-type fix. They pass with unchanged expectations. All four actual Chicago/NYC TSV outputs are byte-identical to their old outputs.
- TPC-C transport regression: Failed before loopback/network-namespace change; Passed after. The actual latest-library first-auth/prepared queries and one-warehouse repository loader pass.
- Optional Oracle client selection/archive tests: Failed first; Passed after. The explicit-license refusal test passes without any container action. An additional base-image-override test failed first and passed after preserving that override.
- Loader build-context regression: Failed first, then Passed after limiting the context to engines/mysql. A root context with already-baked data was stopped rather than transferred.

## Validation

| Check | Result |
|---|---|
| Repository gate | **Passed**: 184 tests; assertions retained; mocked unit fixtures use a private TMPDIR |
| Real CSV conversions | **Passed**: four conversions; all output TSV hashes unchanged |
| Console HTTP/GraphQL/installed-driver connections | **Passed**: phpMyAdmin both accounts, Adminer both server engines, DbGate all engines, CloudBeaver 31 connections; complete database lists |
| Loader CLI dump/restore | **Passed**: isolated disposable MySQL; removed afterward |
| Connector/C first auth and prepared queries | **Passed**: isolated disposable MySQL; removed afterward |
| Actual TPC-C loader | **Passed**: isolated disposable MySQL; removed afterward |
| Reset pairs | **Passed**: same-count text/binary restoration and extra-object removal |
| Reset mysql | **Passed**: same-count text/binary restoration and extra-object removal |
| Reset postgres | **Passed**: same-count text/binary restoration and extra-object removal |
| Reset sqlite | **Passed**: same-count text/binary restoration and extra-object removal |
| Reset all | **Passed**: same-count text/binary restoration and extra-object removal |
| Append selector reset | **Passed**: core row and both SQLite copies restored |
| Published endpoint authentication | **Passed**: see receipt for exact scope |
| Optional Oracle binary probes | **Passed**: SQL*Plus and SQL*Loader report the selected version without starting a database |
| Oracle native connection/load checks | **Not run**, pending explicit Oracle Free Use Terms acceptance |
| BTS and both WWI exports × three engines | **Not run, pending the owner's decision**: absent from live; BTS pins unchanged; no SQL Server EULA accepted |
| Full Enron PostgreSQL FTS index | **Unsupported**, unchanged native vector-size limit; data and checksum expectations preserved |
| TPC-DS normative answer function | **Unsupported** in current DuckDB as in the earlier release; both extension query registries load, and the existing peer-engine comparison policy is retained |
| DataIntent, live cutover/rollback, Docker/BuildKit | **Not run** |
| Other architectures | **Not run** for general stack; optional x86-64 Oracle client recipe **Unsupported** elsewhere |

The complete engine-branch build/port and image checks are retained in its receipt, including all 90 available combinations and the measured PostgreSQL startup correction. This follow-up does not rebuild unchanged engine images or re-pin any dataset: runtime native clients already come from those current engine distributions. It exercises the updated client paths and repeats the running-data verification after resets. Acceptance is still ongoing wherever a current result is absent; no absent result is counted as Passed.

## Recovered harness failures and retained evidence

- DuckDB 2.0 CSV boolean cast pushdown: full/core regression tests fail first, then pass after explicit BOOLEAN source types and CASE projection; real CSV outputs byte-identical.
- Latest source-built Connector/C rejects the throwaway server's remote self-signed certificate. First real loader probe failed; loopback/network-namespace regression failed first, then passed, and actual first caching_sha2 auth/prepared queries and TPC-C cardinalities passed. No global verification bypass.
- Adminer HTTP probe initially omitted its CSRF field; corrected the harness and both engine UI listings passed.
- A source gate run during the real reset hit four valid global reset locks. A separate TMPDIR for mocked unit fixtures retained all assertions and the complete source gate passed.
- The previous session's health helper was stopped. The project-checked isolated helper was restarted; the first MySQL engine reset includes this wait and is not a startup-performance measurement.
- An initial comparison harness preceded its image build; initial staging harness missed PYTHONPATH. Corrected before obtaining results. A broad loader build context was stopped and replaced with its small source directory; regression test passes.
- The initial exported base tools image lacked the container's later SQLite/uv setup. It was discarded, replaced by an actual running-tools filesystem snapshot (bind mounts excluded), smoke-tested and hashed.

Raw logs, publisher captures and per-dataset results live under build/client-evidence/; selected compact results, source URLs/read times and SHA-256 values are committed in docs/validation/client-upgrade-2026-11-17.json. API debug output is private and excluded from the receipt hash list because it may contain command environments. The full tools archive is private (mode 0600), identified by its image ID and SHA-256 in the receipt; the runbook smoke-checks its actual SQLite/uv setup before use.

## Runbook and isolation

The live runbook now covers client/consoles preparation, exact loader/console/native-client rollback images, original generated console files and credentials, original Python environment, an immutable rollback branch, a separate tools container, all database/UI verifications, and restoring only the originally running service set. All shell blocks and embedded rollback Python are syntax-checked. No live runbook command was executed.

The private rehearsal uses settings in megasamples.yaml and the mode-0600 .env in this clone, the supplied env.sh/socket/store, project megasamples-upgrade, and 127.0.0.1 only: MySQL 13306, PostgreSQL 15432, landing 18080, phpMyAdmin 18081, Adminer 18082, DbGate 18083, CloudBeaver 18084. The current isolated native health helper is recorded in build/client-evidence/health-probe-runner.pid and build/upgrade-evidence/healthcheck-runner-state.json. Final native store listings and the read-only live baseline comparison are recorded when complete. No proxy service is changed.
