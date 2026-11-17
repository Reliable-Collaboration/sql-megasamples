# Owner-approved BTS and WideWorldImporters upgrade

<!-- gate:start -->
Original dataset-only validation: **Failed** on the cold-readiness gates below. The five supported dataset pairs and all console/reset checks Passed. The subsequent [all-engine cold-readiness follow-up](cold-readiness-evidence.md) resolves that blocker: all three complete image checks and the repository gate **Passed**. The original receipt and failed attempts below remain unchanged as historical evidence.
<!-- gate:end -->

The owner authorized the BTS lookup refresh and accepted the SQL Server Developer EULA for the
isolated WWI export on **2026-11-17** (decision supplied in the task, DL-072). PR
[#10](https://github.com/Reliable-Collaboration/sql-megasamples/pull/10) was marked ready and merged
as `d97445d2c9d9d4b0c81697f5acb7408b7ae6364e`, with parents `b80583cd28b02f144c1f19ddad68076c636fef4f`
and the required client head `a83255d4ddaf26265c26fd1a18c04c2555e8b433`. This branch starts from that merge.
Oracle native verification remains **Not run, pending the owner's decision on Oracle's Free Use Terms**.
No Oracle database was started or terms accepted. The merged PR description records this disposition.

The dataset follow-up is [PR #11](https://github.com/Reliable-Collaboration/sql-megasamples/pull/11).
Its original head `c854f399` remained draft because the MySQL and SQLite cold-readiness gates
Failed. The [follow-up receipt](validation/cold-readiness-2026-11-17.json) records the class-wide
gate correction, measurements and passing rerun required before marking it ready and merging
with a merge commit matching the validated head. The supported data remains loaded in isolation.

## BTS source and pin

The original [upstream lookup](https://www.transtats.bts.gov/Download_Lookup.asp?Y11x72=Y_NVecbeg)
served HTTP 200 and valid CSV at **2026-11-17T08:12:49.635146Z**. It was chosen over the January and
May archive candidates in `build/upgrade-evidence/bts-archive-recovery.json`: the owner's preference
was current upstream when served. The archive CDX index was also read at
2026-11-17T08:12:50.795466Z; the exact query URL/response hash are in the receipt. No archive bytes
were substituted for this refresh. Keep the upstream URL, with no unverified mirror.

| Pin | Before | After |
|---|---|---|
| bytes | 319,686 | 320,236 |
| SHA-256 | `7be383b4eb599a861aa19208e7fae9a97824abc094078e73ad05b118c0fc2405` | `7a3c2a0bbcdc6951c2ae6eefe1e5739cfeb86f5016006cec49e146bb54b9466d` |
| licence | `us-government-public-domain` | `us-government-public-domain` |

`make fetch D=bts_ontime` independently fetched and verified the new pin. All 6,942 unique source
keys and descriptions match the load after the converter's existing tab-to-space normalization
(one description, code `2F5`). Both joins cover every one of 539,747 flights, with zero unmatched
origins and zero unmatched destinations, and 329 distinct codes on each side. No foreign key is
invented for historically reused airport codes. One cp1252 `0xCD` byte remains and is re-encoded
correctly. The old pinned bytes were unavailable, so the net gain of thirteen rows is not a claim
that exactly thirteen keys were added with no other source edits.

## WWI export and acceptance

The authorized command was exactly `MEGASAMPLES_ACCEPT_MSSQL_EULA=1 make wwi-export`, with `env.sh`
sourced and its isolated store/socket checked. The flag was scoped to that command. The repository
route printed its terms, restored both pinned backups, exported source-side per-column baselines,
and removed `megasamples-build-mssql` when finished (**114 seconds**). The
[Developer EULA](https://go.microsoft.com/fwlink/?linkid=857698) was read successfully at
**2026-11-17T08:14:53.507896Z**; the resolved URL and byte count are in the receipt.

Acceptance in both local `downloads/<dataset>/export/server.json` files is explicitly attributed
to the **repository owner, 2026-11-17**. Those files, their export hashes and attribution are also
preserved in the local approved-input archive and committed receipt. No SQL Server binary, tool,
image layer or EULA text is redistributed. Engine/tool pins were retained; publisher URLs and
read times remain in `engines/images.lock.yaml` and `clients.lock.yaml`.

| Export | Source tables | Source rows | Export bytes |
|---|---:|---:|---:|
| WWI OLTP | 48 | 4,713,833 | 566,347,226 |
| WWI DW | 29 | 923,643 | 125,122,127 |

The existing warehouse converter excludes thirteen empty integration staging tables, leaving
16 loaded tables and the same 923,643 rows. Existing temporal, sequence, programmable-object and
fractional-datetime conversion limits remain documented in the converters/provenance. The source
baselines check row counts, non-null values, UTF-16 units and non-ASCII occurrences before loading.

## Test-first fixes and changed expectations

The new pin regression **Failed** on the old hash, then **Passed**. The real BTS build **Failed**
first on the old counts/fingerprints/lookup-size output and the missing view baseline; after the
observations below were recorded, the full MySQL build **Passed**.

| BTS expectation | Before | After |
|---|---|---|
| `l_airport` count / digest n | 6,929 | 6,942 |
| `l_airport` digest x | `13169048756575951982` | `17097811671866272680` |
| `l_airport` digest s | `2861332761622831348` | `3388410830110865038` |
| `lookup_sizes` smoke output | `6929\t1778\t1778` | `6942\t1778\t1778` |
| `v_ontime_delay` baseline | absent | n `539747`, x `17213811468148301600`, s `896074037464083808` |

Flight and carrier counts, fingerprints and all other existing BTS smoke expectations are unchanged.

The WWI conversion exposed quadratic suffix copying in `read_rows`. A deterministic copy-budget
regression **Failed** first (3,771,750 copied bytes for a 24,900-byte fixture), then **Passed** after
tracking a record offset and retaining the incomplete suffix once per chunk. The framing test
covers split terminators, Unicode, NULL, empty text, an embedded NUL value and an unterminated last
record. The initial slow converter process was deliberately terminated and restarted; its failed
wrapper log is retained. No database/container was stopped for that restart.

The subsequent WWI builds **Failed** with 22 spatial x/s mismatches. Investigation proved these
fixtures predate the repository's existing [longitude-first canonical WKB correction](https://github.com/Reliable-Collaboration/sql-megasamples/commit/39a100ba42bdeb2f7fa87dc4809f5c8567832ee2),
read from local history at **2026-11-17T08:54:52.649412+00:00**. `audit-wwi-axis-order.py` reproduces **every historical spatial
pin exactly on the newly loaded rows**, using the previous expression, before recording the
current canonical expression. This covers twelve spatial tables; eleven need changed fingerprints,
and supplier-history geometry does not. Counts, column sets, exclusions and all
non-spatial fingerprints remain unchanged. The official [geometry conversion documentation](https://dev.mysql.com/doc/refman/26.10/en/gis-format-conversion-functions.html)
was read at **2026-11-17T08:37:25.052914Z** and documents the explicit axis-order option.

| dataset.table | count (unchanged) | XOR before → after | SUM before → after |
|---|---:|---|---|
| `wideworldimporters.application_cities` | 37,940 | `4507629804472251712` → `6735625259573066116` | `16219337559159682180` → `312861780517158762` |
| `wideworldimporters.application_cities_archive` | 28 | `1345619199829998912` → `10429824891521468099` | `6887691594683785430` → `14737488119177392153` |
| `wideworldimporters.application_countries` | 190 | `15341270223541961129` → `1425095345194106471` | `5997892828104006945` → `17583937016603517193` |
| `wideworldimporters.application_countries_archive` | 37 | `554023383433127930` → `10669774194503469474` | `5124005709495390862` → `6518621158686021452` |
| `wideworldimporters.application_stateprovinces` | 53 | `4691453213289502061` → `15177311867757041183` | `6882193958328376943` → `3362018121277439013` |
| `wideworldimporters.application_stateprovinces_archive` | 104 | `6430459954969562152` → `7084668878436842555` | `6465635852461325332` → `13817821251839490819` |
| `wideworldimporters.application_systemparameters` | 1 | `2157305026322130524` → `18009151036368565944` | `2157305026322130524` → `18009151036368565944` |
| `wideworldimporters.purchasing_suppliers` | 13 | `9957329550293883136` → `1534186529903638992` | `6684544239104671100` → `3495763281050745048` |
| `wideworldimporters.sales_customers` | 663 | `17193904155976444274` → `5835989084913653967` | `17074012341241004484` → `15062874395378306165` |
| `wideworldimporters.sales_customers_archive` | 51 | `16272734704658140093` → `1885799833431724360` | `7049434545409133487` → `7514985172129761556` |
| `wideworldimporters_dw.dimension_city` | 116,295 | `6139414012753560817` → `12892259299130777823` | `12090046503416816199` → `17904273180255008591` |

The complete MySQL build of both WWI datasets subsequently **Passed** with zero failures.

The catalogue regression **Failed** before explicit engine dispositions were rendered, then
**Passed**. Measured opt-in counts now appear alongside their engine results, while the core-image
totals retain their original scope. Generated port SQL and omission records for WWI DW are committed.

The first MySQL build context captured the preceding catalogue while the full data image was
being built. A documentation-only layer refreshes that file; its recipe and before/after image IDs
are in the receipt. Every existing root filesystem layer is preserved, with one catalogue layer
appended, and the embedded file matches the current repository SHA-256. The initial tmpfs-based
process probe **Failed** with OCI `No space left on device` despite adequate host filesystem space;
the stopped-container `create`/`cp`/`rm` probe **Passed** and starts no database. This harness recovery
and its logs are retained. Subsequent checks target the final image IDs.

The MySQL image checker also skipped every data assertion when cold provisioning consumed its
polling window. A new regression **Failed** before the fix, then **Passed**: after a late ready
start, all data checks execute and the unchanged 30-second gate is the sole failure. The polling
window is finite after `run` returns; the end-to-end pass/fail budget remains exactly 30 seconds.
The corrected real run checked the full configured image and failed only readiness: **49.0 s**.
Its data, integrity, account and override checks passed. The existing
[30-second rule](https://github.com/Reliable-Collaboration/sql-megasamples/blob/d97445d2c9d9d4b0c81697f5acb7408b7ae6364e/megasamples/engines/mysql/image_test.py#L20)
was read at **2026-11-17T10:40:51.169595+00:00**. The first run's skipped-data failure is retained separately.
The isolated API was restarted with the handoff's existing slirp override; no engine or forwarding
service was stopped for that API restart. This improves the diagnostics without relaxing a gate.

## Nine-combination validation

<!-- matrix:start -->
| Dataset | Engine | Build/port | Counts/checksums | Reset + revalidation | Consoles |
|---|---|---|---|---|---|
| `bts_ontime` | mysql | Passed | Passed | Passed | Passed |
| `bts_ontime` | postgres | Unsupported | Unsupported | Unsupported | Unsupported |
| `bts_ontime` | sqlite | Unsupported | Unsupported | Unsupported | Unsupported |
| `wideworldimporters` | mysql | Passed | Passed | Passed | Passed |
| `wideworldimporters` | postgres | Unsupported | Unsupported | Unsupported | Unsupported |
| `wideworldimporters` | sqlite | Unsupported | Unsupported | Unsupported | Unsupported |
| `wideworldimporters_dw` | mysql | Passed | Passed | Passed | Passed |
| `wideworldimporters_dw` | postgres | Passed | Passed | Passed | Passed |
| `wideworldimporters_dw` | sqlite | Passed | Passed | Passed | Passed |

The five supported pairs passed real builds, full applicable repository verification on the
running containers, and a separate `make reset R=engine:dataset` per pair. Same-count text
mutations were restored and added objects removed. Both SQLite copies returned byte-for-byte to
their shipped content; full counts/fingerprints/structure were rechecked after all resets.

Full configured image results: mysql Failed, postgres Passed, sqlite Failed.
The final five-pair verification
does not replace the explicitly retained earlier 90-pair fingerprint receipt.

The complete repository gate Passed: **191 tests in 24.3 seconds**, plus generated files and one loaded warehouse port record reproduced. The other
30 existing port records were reported Not run in this source-build-server command; they were
not loaded there. Their prior reproduction remains in the client receipt. All five consoles list
the complete supported database sets; CloudBeaver opens 32 expected server/SQLite connections.

| Image | Result | Failed assertions |
|---|---|---|
| mysql | Failed | x ready in 49.0s (budget 30s) |
| postgres | Passed | none |
| sqlite | Failed | x ready in 38.2s (budget 30s) |

Readiness thresholds are unchanged. A failed timing gate blocks merging/cutover even when
its data/account checks pass. Earlier skipped-data behavior is corrected and regression-tested.
<!-- matrix:end -->

The four Unsupported dispositions follow the repository's
[generated-expression guard](https://github.com/Reliable-Collaboration/sql-megasamples/blob/d97445d2c9d9d4b0c81697f5acb7408b7ae6364e/megasamples/port/ddl.py#L192-L207),
read **2026-11-17T08:34:42.177343Z**. BTS stops on `ontime.crs_dep_time` (`cast`, `left`, `maketime`,
`right`); WWI OLTP stops on `application_people.searchname` (`concat`). These are limits of the
current repository translator/allowlist, not assertions that PostgreSQL or SQLite cannot ever
represent those expressions. No columns or checks were removed to force a port through.
Unsupported pairs are excluded from the running configuration and console listings. The warehouse
ports retain every loaded table; normal adapter limitations (such as MySQL-dialect smoke/explain
queries and SQLite exact-decimal handling) remain explicit in verification output.

The running verifier initially stopped before data access because its launcher omitted the
storage environment variable. Explicit inheritance fixed the launcher without changing the
isolation guard. A subsequent attempt passed the four server pairs and then failed parsing the
SQLite CLI quoted JSON cell. The corrected TSV reader uses `csv.reader`; it retains the exact
registry assertion. Both failed attempts and timings are preserved separately from the final
successful complete run. Reset checks also compare exact foreign-key definitions before/after,
including MySQL referenced columns and update/delete rules.

CloudBeaver initially failed the real connection-list probe because its old workspace lacked
`sqlite-wideworldimporters_dw`. A restart retained that workspace. Its consistent workspace was
copied privately while stopped, then only that isolated console was recreated to reseed the new
connection catalogue. The subsequent deep and shallow probes **Passed**, including all 32
connections. The runbook now backs up the original workspace and the final quiesced copy, refreshes
the configured catalogue, and restores the workspace into a stopped original console during
rollback. Vendor [initial configuration](https://dbeaver.com/docs/cloudbeaver/Initial-data-configuration/)
and [workspace format](https://dbeaver.com/docs/cloudbeaver/Data-Sources-Json-Reference/) documentation
were read at 2026-11-17T10:14:42Z; the exact observations and private-backup digest are in the receipt.
No backup content or credentials are committed.

SQLite also exceeded its unchanged [30-second image readiness gate](https://github.com/Reliable-Collaboration/sql-megasamples/blob/d97445d2c9d9d4b0c81697f5acb7408b7ae6364e/megasamples/engines/sqlite/image_test.py#L19):
**38.2 seconds**. That source rule was read at **2026-11-17T10:48:40.939570+00:00**. The current image checker
continues its data/integrity checks while retaining the timing failure. Both MySQL and SQLite
readiness failures block merging and live cutover; neither budget was increased.

## Live preparation, cost, verification and rollback

Loading these datasets is now part of `docs/live-upgrade-runbook.md`: MySQL receives all three;
PostgreSQL and SQLite receive WWI DW. The runbook checks the merged engine, client and dataset PRs,
reuses a hashed sample-input/export archive, adds only Passed pairs to each configured engine,
builds before the outage, then verifies actual loaded fingerprints and BTS joins. It includes
complete console lists and restores the original configuration, console files, engine images and
cold copies for rollback, removing these additions while preserving new writes separately first.
Oracle terms are still not accepted. All live actions remain **Not run**.

The private reproducible input archive is `build/dataset-upgrade-evidence/approved-inputs.tar`,
**899,993,600 bytes**, SHA-256
`0a74cd4ee4def587889b373d11f29aa938cce91a0c21f3f501d7b328d62ce596` (89 files).
It contains pinned sample artifacts and attributed exports, and excludes SQL Server code/tools.

<!-- costs:start -->
| Added data on live engine | Observed bytes |
|---|---:|
| MySQL `bts_ontime` allocated database blocks | 231,673,856 |
| MySQL `wideworldimporters` allocated database blocks | 783,147,008 |
| MySQL `wideworldimporters_dw` allocated database blocks | 364,470,272 |
| PostgreSQL `wideworldimporters_dw` database | 211,539,647 |
| SQLite `wideworldimporters_dw.sqlite`, each of `/data` and `/shared` | 171,114,496 |

Observed additional database/file storage totals **1,933,059,775 bytes** across these five pairs,
including both SQLite copies. This excludes shared WAL, engine overhead and rollback copies.
The 899,993,600-byte input archive, extracted exports, stage files, dumps, new complete images,
old retained images and cold backups require additional preparation space; exact per-dataset
stage/dump/export footprints and complete image sizes are in the receipt.

| Measured successful operation | Seconds |
|---|---:|
| SQL Server export | 114 |
| Both WWI MySQL builds including source conversion/checks/dumps | 286.75 |
| Warehouse PostgreSQL build/verify | 53.13 |
| Warehouse SQLite build/verify | 39.19 |
| Whole configured MySQL image | 1641.39 |
| Whole configured PostgreSQL image | 1564.71 |
| Whole configured SQLite image | 326.52 |
| Replacement stack startup | 269.27 |
| Initial five-pair running validation | 200.15 |
| Five pair resets and post-reset full validation | 793.04 |

BTS load itself was 17.0 seconds; its complete original build duration was not captured.
Whole-image timings include the unchanged corpus and are not marginal timings for only these
datasets. Build before the live outage; reserve startup and verification time separately, plus
cold backups and DataIntent checks. These observations are not a downtime guarantee. The aborted
slow-reader conversion and failed stale-checksum attempts are separate retained costs.
<!-- costs:end -->

## Isolation and limits

Every container command used the supplied isolated environment and a checked store/socket.
Only the owner's specifically requested read-only default-store inspection clears those overrides.
It compares IDs, image IDs, nanosecond start times and running states to the supplied live baseline.
No live deployment, volume, network, image or forwarding service was changed.

<!-- isolation:start -->
**Passed:** final isolated `podman ps -a` contains exactly 12 expected isolated containers,
with no SQL Server export container. All eight application services remain running. The read-only
default-store comparison at 2026-11-17T10:58:42.220915+00:00
matches all three live IDs, image IDs, nanosecond start times and running states to the supplied
`live-before.txt`. Exact selected fields are committed in the receipt; no environment secrets
are published. No proxy-service command was executed.
<!-- isolation:end -->

Oracle native checks, DataIntent suites, live cutover/rollback, Docker/BuildKit execution and other
architectures are **Not run**. The report claims no vendor support beyond the cited documentation
and actual repository behavior. The original unavailable airport snapshot cannot be reconstructed
or compared row-by-row. Historical failed attempts are retained in the receipt; no gate was relaxed.
