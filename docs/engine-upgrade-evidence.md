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
- DVD Store reviews initially **Failed** because its emitted load paths pointed into the core dataset's staging directory. The two-case regression suite **Failed** for the extension while the core passed; after deriving paths from the output directory, both tests **Passed** and the actual MySQL review load **Passed**.
- Oracle SH declared a nonexistent `channels.csv` even though its rows come from the pinned SQL script. The new manifest-contract test **Failed**, the input list was corrected, and all **6 inventory tests Passed**.
- A native Podman loader-image attempt **Failed** because the IPv4 OCI archive flattened an image-index digest. A regression test **Failed** before selecting Podman's native importer, then **Passed**; platform-preservation cases likewise **Failed** before correction and the full image-reference suite **Passed** (7 tests). The actual **loader image build Passed** after the import correction.
- The SQLite source builder **Passed**; executing its built shell reported 3.54.1. The isolated PostgreSQL build server reported 18.7.

The full unit suite also **Passed** with the exact `uv.lock` dependencies installed inside `/opt/locked-venv` in the tools container: initially **116 tests**, then **127 tests** after the image-snapshot regressions and Chicago CSV coverage were added, and **130 tests** after the manifest-contract and native-import cases. The repository checkout has no host-installed environment.

## Runtime validation

Pending completion. Per-dataset commands use `python -m megasamples build --no-fetch --engine ENGINE DATASET`, which loads and runs the repository's applicable counts, canonical fingerprints, constraints, views, routines, triggers, explain and smoke checks. Unsupported/not-ported objects remain subject to the repository's explicit exception records. A driver's successful exit is not a substitute for its per-dataset results.

One early full gate ran while the hub was rebuilding a database and failed port reproduction on that temporarily absent database; it must be rerun after the build settles. This is retained as **Failed**, not reported as a test pass.

## Isolation and handoff

The isolated store was verified empty before creating containers. `podman info` with the supplied environment reports graph root `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/graph` and run root `/home/rcc-vstudio/working/sql-megasamples-upgrade-env/run`. Pasta could not access a namespace beneath that custom runroot; only this run's socket service was restarted with the installed `slirp4netns` override.

Read-only inspection of the default store matched all three supplied live baseline IDs, image IDs, nanosecond start times and running states after normalizing timezone notation and Podman's image-ID prefix. The initial failed comparisons were representation differences, not a container change. Final proof must be refreshed when validation finishes. No proxy service or live checkout was changed.

Settings: ignored `megasamples.yaml` and mode-0600 `.env` in this clone. Planned endpoints: MySQL `127.0.0.1:13306`, PostgreSQL `127.0.0.1:15432`; consoles `127.0.0.1:18080`–`:18084`. Connection settings are not yet evidence of a running stack. Follow `docs/live-upgrade-runbook.md` only after the upgrade and DataIntent validations are complete.
