# Engine upgrade evidence

Validation is in progress on `upgrade/latest-stable-engines`. This report is not authorization to change the live deployment. The raw command logs, source captures and per-dataset JSON results live under `build/upgrade-evidence/` in the isolated clone; downloaded inputs are under `downloads/`. No host packages were installed.

## Branch integration

| PR | Change | Merge commit |
|---|---|---|
| [6](https://github.com/Reliable-Collaboration/sql-megasamples/pull/6) | Download progress start times | `6ed6d5fc378a48e879774a03d54802f2969732d4` |
| [7](https://github.com/Reliable-Collaboration/sql-megasamples/pull/7) | Live-feed snapshots, exact hub-to-port verification, refreshed hub dumps; regenerated stale catalogue | `e75ca8abc4f9c0f2228ffec53c70342bb3345708` |
| [5](https://github.com/Reliable-Collaboration/sql-megasamples/pull/5) | Scoped resets, pristine images, reset locks, SQLite lifecycle/journals; into rootless-podman first | `af9899e68aad9dd02de8573fca86ffb728165524` |
| [8](https://github.com/Reliable-Collaboration/sql-megasamples/pull/8) | Rootless Podman user/build/context support and reset integration into main | `d581d93f845e79e23a7224d3a041342be0f1c782` |

`rootless-podman` received current main through merge commit `b7bf7fa` before PR 8. No rebase, squash, force push or branch deletion was used. `release-2` was already merged in PR 4 (`8506a61e5b64e29a8eec680682eefb5015176f3e`). All remote branches were kept; none was rejected as obsolete.

| Branch gate | Result |
|---|---|
| fix/fetch-start-time | Passed: `make check`, 54 tests |
| live-artifacts before repair | Failed: stale catalogue/README; 56 tests passed |
| live-artifacts after `make catalogue` | Passed: `make check`, 56 tests |
| rootless-podman original head | Failed: stale provenance and catalogue; 56 tests passed |
| reset-command / PR 5 head | Passed: `make check`, 92 tests |
| rootless-podman after PR 5 and main merge | Passed: `make check`, 92 tests |

The branch gates explicitly reported port-record reproduction as **Not run** because the build server was absent. A zero exit from that gate does not establish runtime port validation. All gates ran inside the isolated tools container with `make check PY=/opt/venv/bin/python`.

## Release selection and image provenance

The prior defaults were MySQL 9.7.2, PostgreSQL 18.6-bookworm and Alpine's packaged SQLite (README described 3.49). Those are repository defaults, not a fresh version query against the live containers. Source: [the initial repository tree](https://github.com/Reliable-Collaboration/sql-megasamples/tree/8506a61e5b64e29a8eec680682eefb5015176f3e), reread 2026-11-16 19:08:11 UTC.

| Component | Selected release | Primary source (read time UTC) |
|---|---|---|
| PostgreSQL | 18.7, official trixie image | [Release notes](https://www.postgresql.org/docs/release/18.7/), 2026-11-16 18:58:36 |
| MySQL Server | 26.10.0, newest GA Innovation release | [GA downloads](https://dev.mysql.com/downloads/mysql/), [release notes](https://dev.mysql.com/doc/relnotes/mysql/26.10/en/news-26-10-0.html), 2026-11-16 18:58:36 |
| MySQL Shell | 26.10.0, bundled with the selected server image | [Shell downloads](https://dev.mysql.com/downloads/shell/), 2026-11-16 18:58:36; binary queried in isolation |
| SQLite | 3.54.1, built from vendor source with vendor SHA3-256 | [Downloads](https://sqlite.org/download.html), [release notes](https://sqlite.org/releaselog/3_54_1.html), 2026-11-16 18:58:36 / 18:44 UTC |
| nginx | 1.30.6, stable line | [Vendor downloads](https://nginx.org/en/download.html), 2026-11-16 18:58:36 |
| CloudBeaver Community | 26.2.5 | [Publisher's image tags](https://hub.docker.com/v2/repositories/dbeaver/cloudbeaver/tags?page_size=20), 2026-11-16 18:58:36 |
| DbGate | 7.3.6, Debian image | [Publisher's image tags](https://hub.docker.com/v2/repositories/dbgate/dbgate/tags?page_size=20), 2026-11-16 18:58:36 |
| Adminer | 6.3.0 | [Vendor downloads](https://www.adminer.org/), 2026-11-16 18:58:36 |
| phpMyAdmin | 5.2.3 | [Vendor downloads](https://www.phpmyadmin.net/downloads/), 2026-11-16 18:58:36 |
| Playwright Python | 1.65.0 | [Publisher's package metadata](https://pypi.org/pypi/playwright/json), 2026-11-16 18:58:36 |
| SQLite image base | Alpine 3.24.4 | [Vendor releases](https://www.alpinelinux.org/releases/), 2026-11-16 18:58:36 |
| Loader base | Debian 13.7-slim | [Vendor releases](https://www.debian.org/releases/), 2026-11-16 18:58:36 |
| Optional Oracle verification tool | 26ai Free 23.26.3.0.0 | [Vendor Free downloads](https://www.oracle.com/database/free/get-started/), 2026-11-16 19:40 UTC; packaged composite version and SQL*Plus queried without starting a database |
| SQL Server export tool | SQL Server 2025 CU11, 17.0.5065.9 | [Vendor build list](https://support.microsoft.com/en-au/servicing/sql/sql-server-2025/kb5005684-build-versions), 2026-11-16 18:58:37 |

The [Playwright vendor release notes](https://playwright.dev/python/docs/release-notes) also list 1.65 as their newest release (read 2026-11-16 20:36:56 UTC; captured in `vendor-release-pages.json`). CloudBeaver and DbGate's selected exact versions are confirmed by their publishers' image registries; fresh reads at 2026-11-16 20:38:25 UTC prove each numbered tag has the same digest as `latest` (`console-release-tags.json`). CloudBeaver's [vendor tag policy](https://dbeaver.com/docs/cloudbeaver/CloudBeaver-release-cycles/) explicitly defines `latest` as its stable release (read 2026-11-16 20:38 UTC), supporting that stable selection. A matching release-announcement page for either exact patch was **not verified**. DbGate's [vendor news](https://www.dbgate.io/news/) showed 7.3.5 while the publisher image tag is 7.3.6 (read 2026-11-16 20:37 UTC). The [vendor download page](https://www.dbgate.io/download/) describes its offered builds as stable and separates beta/older releases (read 2026-11-16 20:36:55 UTC); selecting the current numbered publisher `latest` image is an inference from that policy and registry evidence. The news discrepancy is retained as an evidence limitation, not silently treated as an announcement of 7.3.6. Docker's release-notes URL automatically redirected to another GitHub repository during lookup; that was outside the requested repository scope, and no further links there were followed. The frontend digest is supported by the publisher registry rather than a separately verified release page.

Every image reference and digest is recorded in `engines/images.lock.yaml`, with its source and read time. The Dockerfile frontend is pinned to the publisher's release-tagged 1.29.0 manifest; its live registry verification/read time is in that file. The optional Oracle verification image's current `23`/`latest` digest is pinned. Its composite-version tool reports **23.26.3.0.0**, matching the current [vendor Free downloads](https://www.oracle.com/database/free/get-started/) (read 2026-11-16 19:40 UTC). No Oracle database was started; native Oracle cross-checks are **Not run**.

The MySQL choice implements "latest stable" as newest generally available release, including the Innovation line, rather than staying on the older LTS line. The [vendor release policy](https://dev.mysql.com/doc/refman/26.10/en/mysql-releases.html) describes both as production-grade and the switch to calendar versioning (read 2026-11-16 18:58:36). PostgreSQL 19 was still an RC on the [vendor home page](https://www.postgresql.org/) when read on 2026-11-16 at 18:44 UTC, so it was excluded. No prerelease image is selected.

SQLite is compiled independently of Alpine's package version. Its source archive must match SHA3-256 `b6ced585c750916b1052667239a12c25a7ff34e7f06e1e6e01ecb0427657d9c4`. The tools container's SQLite library was also compiled from these verified bytes; Python there reports 3.54.1. MySQL server and Shell both reported 26.10.0 from the isolated base image. PostgreSQL's runtime and all final images still require the completed runtime checks recorded below.

## Test-first changes and input recovery

- Engine release/input regressions: **Failed** first (6 failures, 1 pass); **Passed** after pins changed (7 tests).
- Console/tool release regressions on original inputs: **Failed** (8 failures, 7 passes); **Passed** after changes (15 tests).
- Full-manifest loading exposed an existing T-SQL view concatenation bug. The two reproducing tests **Failed** before the fix; **Passed** after it. A third test reproduced T-SQL `--ORDER BY` comments being parsed before MySQL comment normalization; it **Failed** before correction. A fourth preserved the existing reporting of unsupported XML/APPLY constructs; it **Failed** before correction. All four then **Passed**.
- Tagged digest references exposed a `pull-image` parser bug: it included `:tag` in the registry repository path. The new reference tests **Failed** (3 failures, 2 passes), then **Passed** (5 tests) after correcting the parser. Both proposed database manifest digests were independently verified against the registry.
- Sakila's upstream ZIP wrapper changed again. Both inner SQL files match the byte lengths and MD5 values recorded in `knowledge/datasets/sakila.md`. Only the transport archive SHA-256 was updated; dataset expectations were retained.
- Lahman's public Box folder was downloaded through the browser. Its generated ZIP wrapper differs per download. Its README and every dataset assertion are checked before accepting the new archive pin. The source is the [published Box share](https://sabr.box.com/s/y1prhc795jk8zvmelfd3jq7tl389y6cd), read 2026-11-16 during this run.
- BTS's upstream lookup files drifted. Two lookup CSVs were recovered with exact manifest hashes and fresh mirror downloads **Passed**. The airport lookup remains unavailable at its pin. Source archives are recorded in `build/upgrade-evidence/bts-archive-recovery.json`; dataset expectations are unchanged.
- The full Wikipedia load passed all existing counts, checksums, indexes and smoke queries, then failed because its view baseline was missing. Added the four-view baseline without altering any existing expectation.
- A whole SQLite reset retained client-added databases in the shared console volume. The strengthened reset test **Failed** first; after clearing those database files before recreating the holder, all **36 reset tests Passed**.
- Seven image-gate regression cases **Failed** on historical live-count floors and duplicate registry rows for append datasets, then **Passed** with exact verified hub counts and one registry row per database. Three further cases confirm incomplete or below-floor hub records are rejected.
- A full Chicago conversion failed with unconstrained dependency versions. The repository's locked dependencies successfully staged all 24 year files; a focused boolean-projection test also **Passed** without a converter change. All final validation uses the locked environment.
- Enron initially **Failed** its existing message/view fingerprints and date-range query in the UTC tools container. The converter used the host timezone despite the `date_utc` name. Tests under UTC and America/Chicago **Failed** for UTC before correction; explicit preservation of the historical Chicago values, including DST and offset-free headers, made all **6 timezone cases Pass** without changing existing expectations. The legacy column name is documented in the converter and dataset record.
- DVD Store reviews initially **Failed** because its emitted load paths pointed into the core dataset's staging directory. The two-case regression suite **Failed** for the extension while the core passed; after deriving paths from the output directory, both tests **Passed** and the actual MySQL review load **Passed**.
- Oracle SH declared a nonexistent `channels.csv` even though its rows come from the pinned SQL script. The new manifest-contract test **Failed**, the input list was corrected, and all **6 inventory tests Passed**.
- A native Podman loader-image attempt **Failed** because the IPv4 OCI archive flattened an image-index digest. A regression test **Failed** before selecting Podman's native importer, then **Passed**; platform-preservation cases likewise **Failed** before correction and the full image-reference suite **Passed** (7 tests). The actual **loader image build Passed** after the import correction.
- Live Chicago provenance incorrectly described feed bytes and content expectations as fixed pins. The regression suite **Failed** (2 failures, 1 pass) before correction and **Passed** (3 tests) after documenting historical floors and the exact observed hashes in the baked registry; both generated provenance files were refreshed.
- The SQLite source builder **Passed**; executing its built shell reported 3.54.1. The isolated PostgreSQL build server reported 18.7.

The full unit suite also **Passed** with the exact `uv.lock` dependencies installed inside `/opt/locked-venv` in the tools container: initially **116 tests**, then **127 tests** after the image-snapshot regressions and Chicago CSV coverage were added, and **130 tests** after the manifest-contract and native-import cases. With the DVD Store and Enron regressions, the full locked suite **Passed: 138 tests in 22.63 seconds** (`locked-unit-tests-with-enron.log`). After the provenance and native-index-limit cases, the full locked suite **Passed: 149 tests in 22.62 seconds** (`locked-unit-tests-with-native-limit.log`). The repository checkout has no host-installed environment.

## Native PostgreSQL full-text limit

The full Enron load initially **Failed** on PostgreSQL while building `message.ft_message`. With notices suppressed, the actual error was `string is too long for tsvector (1491766 bytes, max 1048575 bytes)`. The [vendor documents this native vector-size limit](https://www.postgresql.org/docs/18/textsearch-limitations.html) (read 2026-11-16 20:45:06 UTC, capture `postgres-textsearch-limit-source.json`). Core Enron fits and retains its index; full Enron's rows, body text, counts and canonical checksum expectations remain unchanged.

The upgrade candidate declares only that named full-corpus PostgreSQL FULLTEXT index **Unsupported**, with its reason in the dataset contract, generated port records, catalogue and baked registry. It does not truncate messages or omit rows. The verifier reports the unsupported index explicitly while requiring every other declared index. Eight regression cases **Failed** before implementation and then **Passed**, including guards against unknown names, missing reasons, ordinary-index exclusions and exclusions on SQLite. Together with the existing port tests, **25 tests Passed**. The actual full-corpus PostgreSQL rerun **Passed** all supported checks: 3 tables, 4,771,893 rows, unchanged canonical digests, 2 foreign keys with no orphans, remaining indexes and its view. The full-text index is explicitly reported **Unsupported** in the verification output (`recovered-postgres-enron-full-native-limit.log`). This limitation is part of draft PR 9 for owner review, not a claim of full-text parity.

## Runtime validation

The three-engine `pubs` image preflight first **Failed** because `.dockerignore` excluded the new image lock file; adding its precise allowlist entry made all three builds **Pass**. The actual preflight is the regression check; no existing assertion was weakened. MySQL's image test then **Failed** its read check because it hardcoded Sakila in a pubs-only image. The corrected checker creates a real table and modifying procedure in a shipped database, requires reads, denies all writes and routine execution, and also requires admin writes. The unchanged three-engine preflight command then **Passed**. Separate container checks **Passed** for the exact image-lock SHA-256 in every image (`preflight-provenance-results.json`). These are small preflight images, not the full-data image validation.


The build/port phase **Passed for 30 available datasets on all three engines (90 combinations)**. Nine combinations are **Not run**: the pinned BTS airport bytes are unavailable, and both WideWorldImporters exports require explicit operator EULA acceptance. The complete requested configuration is saved at `build/upgrade-evidence/full-manifest-config.yaml`; the active rehearsal configuration explicitly excludes only those three datasets, as recorded in `rehearsal-coverage.json`.

| Dataset | MySQL | PostgreSQL | SQLite |
|---|---|---|---|
| jaffle_shop | Passed | Passed | Passed |
| dvdstore | Passed | Passed | Passed |
| oracle_hr | Passed | Passed | Passed |
| pubs | Passed | Passed | Passed |
| smallsets | Passed | Passed | Passed |
| chinook | Passed | Passed | Passed |
| sakila | Passed | Passed | Passed |
| adventureworks_lt | Passed | Passed | Passed |
| northwind | Passed | Passed | Passed |
| nyc_taxi | Passed | Passed | Passed |
| oracle_co | Passed | Passed | Passed |
| oracle_oe | Passed | Passed | Passed |
| stackexchange_beer | Passed | Passed | Passed |
| contoso | Passed | Passed | Passed |
| adventureworks_dw | Passed | Passed | Passed |
| adventureworks | Passed | Passed | Passed |
| bts_ontime | Not run | Not run | Not run |
| lahman | Passed | Passed | Passed |
| contoso_1m | Passed | Passed | Passed |
| wideworldimporters_dw | Not run | Not run | Not run |
| nyc_taxi_yellow | Passed | Passed | Passed |
| chicago_crimes | Passed | Passed | Passed |
| oracle_sh | Passed | Passed | Passed |
| wideworldimporters | Not run | Not run | Not run |
| employees | Passed | Passed | Passed |
| dvdstore_reviews | Passed | Passed | Passed |
| stackexchange_dba | Passed | Passed | Passed |
| enron | Passed | Passed | Passed |
| enron_full | Passed | Passed (FTS unsupported) | Passed |
| contoso_10m | Passed | Passed | Passed |
| wikipedia_simple | Passed | Passed | Passed |
| wikipedia_simple_full | Passed | Passed | Passed |
| chicago_crimes_full | Passed | Passed | Passed |

The full repository gate initially **Failed** on core port records after append datasets expanded their shared databases. Records were regenerated for Chicago, DVD Store and NYC taxi; that changed the catalogue's routine metadata, so the catalogue was refreshed again. The final gate **Passed**: 149 tests in 22.58 seconds, port reproduction for all 30 loaded datasets, canonical knowledge records, current provenance files and current catalogue/README (`stack-check.log`). The earlier failed gates are retained under `before-catalogue-refresh-*` and `stack-ports-before.log`.

Final full-data images, running-stack resets and persistence checks are pending. Per-dataset commands use `python -m megasamples build --no-fetch --engine ENGINE DATASET`, which loads and runs the repository's applicable counts, canonical fingerprints, constraints, views, routines, triggers, explain and smoke checks. Unsupported/not-ported objects remain subject to the repository's explicit exception records. A driver's successful exit is not a substitute for its per-dataset results.

One early full gate ran while the hub was rebuilding a database and failed port reproduction on that temporarily absent database; it must be rerun after the build settles. This is retained as **Failed**, not reported as a test pass.

## Isolation and handoff

The isolated store was verified empty before creating containers. `podman info` with the supplied environment reports graph root `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/graph` and run root `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/run`. Pasta could not access a namespace beneath that custom runroot; only this run's socket service was restarted with the installed `slirp4netns` override.

Read-only inspection of the default store matched all three supplied live baseline IDs, image IDs, nanosecond start times and running states after normalizing timezone notation and Podman's image-ID prefix. The initial failed comparisons were representation differences, not a container change. Final proof must be refreshed when validation finishes. No proxy service or live checkout was changed.

Settings: ignored `megasamples.yaml` and mode-0600 `.env` in this clone. Planned endpoints: MySQL `127.0.0.1:13306`, PostgreSQL `127.0.0.1:15432`; consoles `127.0.0.1:18080`–`:18084`. Connection settings are not yet evidence of a running stack. Follow `docs/live-upgrade-runbook.md` only after the upgrade and DataIntent validations are complete.
