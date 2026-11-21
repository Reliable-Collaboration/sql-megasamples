The candidate is reviewed in [PR #14](https://github.com/Reliable-Collaboration/sql-megasamples/pull/14), on `fix/strict-read-account`. **Leave the PR open; the deciders choose deployment timing.** The original merged revision used for the isolated rehearsal is `2cf1f3e9538ea2e90ef23f8715c5e08e4c7de848`.

The [machine-readable evidence](../validation/strict-read-2026-11-18.json) contains native observations, per-database grants, exact routine signatures, commands, reset receipts, canonical fingerprint results, image identities, credential-rotation results and isolation comparisons. It exports completed checks only. Raw logs and private credential files stay in the ignored local `build/strict-read/` directory; published log receipts give actual sizes and SHA-256 hashes.

| Engine/account | Before | Candidate |
| --- | --- | --- |
| PostgreSQL `demo` | TEMP in 30 of 31 connectable inventoried databases; public large-object creation rights; executable user routines in 11 databases | TEMP denied everywhere; all four large-object creation/import families denied; no executable user routine; 1,663 explicit reading signatures |
| PostgreSQL `admin` | Writer and database-owner rights, including inherited routine execution | Previous effective execution rights preserved exactly on existing routines; explicit TEMP in every database for writer workloads, including temporary-table sample routines |
| PostgreSQL `postgres` | Superuser | Superuser; existing effective routine rights unchanged |
| MySQL `demo` | Exactly `SELECT, SHOW VIEW ON *.*` | Identical; no temporary-table, stored-routine EXECUTE, DML, DDL, grant or administrative privilege |
| MySQL `admin` and root accounts | Existing writer and administrative grants | Unchanged; root socket and published TCP identities tested separately |
| SQLite | Files, no server account | Unchanged |

The isolated database count differs from the reported live probe because the isolated configuration contains additional datasets and maintenance databases. The receipt lists each database. Both PostgreSQL templates are initialized; native future-database tests cover template1 and template0, later schemas, both existing creators, a new routine owner, procedures, definer routines, and deliberately private defaults.

Every one of the 1,663 routines remaining executable by PostgreSQL `demo` appears in the [complete inventory with an individual reason](../validation/strict-read-executable-routines.md). These are initdb reading/computation functions, nonvolatile operator/cast implementations and selected information-schema readers. No user routine, VOLATILE routine, SECURITY DEFINER routine, XID allocator, large-object creator, advisory-lock function, configuration setter or administrative function is admitted. Two employee views use equivalent read expressions so they no longer need session-changing helper routines. Writer helpers remain available to writers. [Policy implementation and rationale](strict-read-account.md).

**Failed:** the strict-rule expectation that MySQL refuses named-lock acquisition: `demo` can acquire one. **Unsupported:** MySQL account grants do not enforce a blanket ban on stateful built-ins. The native boundary probe confirms that SELECT-only `demo` can acquire and release `GET_LOCK`; it releases the lock and verifies it is free. Direct sample stored-routine calls remain refused. An additional statement/function restriction layer would be needed for the strict rule to include this MySQL behavior. [MySQL locking functions](https://dev.mysql.com/doc/refman/9.7/en/locking-functions.html) and [privileges](https://dev.mysql.com/doc/refman/9.7/en/privileges-provided.html), read 2026-11-18 09:56:36 UTC. SQLite server-account enforcement is also Unsupported: [SQLite omitted features](https://www.sqlite.org/omitted.html), read 2026-11-18 10:56:21 UTC.

**Failed:** the no-password-output rule was violated during SQL and Dockerfile source inspections, which displayed the repository's published bootstrap credentials. No values are repeated here. Private configured-canary scans are reported separately; passing those checks does not undo this rule failure.

Additional generated-routine checks: **Passed** for actual `admin` and `postgres` connections. Each created a range type with five generated routines; `demo` can execute none, and the writer can use its constructor. **Failed (diagnostic setup):** initial attempts under a new role without explicit writer execution rights were refused during type creation, leaving no committed objects. No production change was needed. The [upstream implementation](https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/src/backend/commands/typecmds.c), read 2026-11-18 10:47:41 UTC, creates these constructors with the bootstrap owner; the closed postgres defaults cover them.

**Failed:** reading the two MySQL employee views changes `@max_date` from unset to set in the demo session, despite the absence of direct stored-routine EXECUTE grants. The final native probe evaluates both view columns without recording their data values. An initial diagnostic projection using MD5 was refused; it was replaced by NULL predicates to isolate the view/session-state criterion. These view helpers and the named-lock built-in remain MySQL strict-rule gaps. This PR does not claim a strict statement profile for MySQL.

**Passed:** additional read-only MySQL index-path diagnostics: the parent primary-index count matches 9,887,613 expected rows, and the full foreign-key anti-join through the child primary index finds zero orphans. The original unmodified canonical foreign-key check also completed and passed. No canonical assertion was skipped or weakened; its native plan is retained.

The MySQL view probe also records both views as `SQL SECURITY DEFINER`. [MySQL stored-object security](https://dev.mysql.com/doc/refman/9.7/en/stored-objects-security.html), read 2026-11-18 11:29:48 UTC, explains why the helper runs with the view owner’s privileges even when direct invocation by demo is refused.

The connected test-first baseline was **Failed as expected**: 94 failed, 94 passed in 51.23s. The rebuilt candidate was **Passed**: 254 passed in 81.33s (0:01:21). The additional private-default and read-view regressions were exercised before their respective fixes; retained log receipts identify those runs.

| Native checkpoint | Reset | Permission tests | Complete-table baseline comparison |
| --- | --- | --- | --- |
| `pairs` | Passed | 254 passed in 18.24s | Passed, all three engines |
| `dataset-flags` | Passed | 254 passed in 16.73s | Passed, all three engines |
| `append-selectors` | Passed | 254 passed in 21.37s | Passed, all three engines |
| `every-pair` | Passed | 254 passed in 26.46s | Passed, all three engines |
| `mysql` | Passed | 254 passed in 24.59s | Passed, all three engines |
| `postgres` | Passed | 254 passed in 27.65s | Passed, all three engines |
| `sqlite` | Passed | 254 passed in 27.97s | Passed, all three engines |
| `all` | Passed | 254 passed in 25.86s | Passed, all three engines |

The `every-pair` reset command contains all 95 configured selectors; engine scopes cover MySQL, PostgreSQL and SQLite, and `all` recreates all three. Pair, dataset-flag and append-selector forms are also exercised. These checks use every complete table at every checkpoint, with exact within-engine equality to the original baseline. Canonical repository cross-engine fingerprints remain separate checks.

**Passed:** rotation/recreation, current credential acceptance and previous credential rejection for seven account/route combinations, private health files, count helpers, 254 post-rotation native tests and all post-rotation complete-table fingerprints. MySQL root TCP and Unix-socket identities are distinct checks.

| Canonical repository read matrix | Original baseline | Candidate | Restored main |
| --- | --- | --- | --- |
| mysql | Passed, 33 pairs | Passed | Passed |
| postgres | Passed, 31 pairs | Passed | Passed |
| sqlite | Passed, 31 pairs | Passed | Passed |

Each canonical matrix runs counts, digests, foreign-key/index checks and views against frozen expectations. MySQL/PostgreSQL reads authenticate as `demo`; SQLite files have no server account. Both runtime SQLite copies match the verified build file. The two rewritten employee views have identical observed canonical fingerprints to the baseline and pass the native no-session-setting-change test.

**Passed:** stored-routine and trigger scenarios for PostgreSQL `admin` and `postgres`, and MySQL `admin` and root, through those actual accounts. Existing effective PostgreSQL routine rights match before/after for each existing routine; MySQL demo/admin/root grants match before/after.

**Passed:** the whole repository gate (`make check`), 512 passed in 46.52s; all three native CLI image gates report zero failures. The earlier ordinary gate had 258 passing tests with the 254 opt-in native tests skipped; the final gate enables them.

**Passed:** the isolated stack is restored to merged `main` `2cf1f3e9538ea2e90ef23f8715c5e08e4c7de848`, with the original environment restored byte-for-byte. All eight application services are running. Engine image identities before and after are identical:

| Engine | Restored image ID |
| --- | --- |
| postgres | `41ab1eb7a3451ad2b319993cd452528d381eeeea3a35ce658c62aab721940fc3` |
| mysql | `20ecf18761195a5c900e9370b3e4d996ecfefdb20c2a555d827110ba9a2f3134` |
| sqlite | `090695cab2b5085144862daaedc9839036058f5ec0387a866c653eb8b9670ebb` |

All five console image IDs also match their saved identities. Complete-table fingerprints match the original baseline on all engines, and the restored canonical matrix passes for all 95 pairs. Exact canonical table-fingerprint comparisons are retained per engine.

mysql: 393 canonical table fingerprint groups match exactly; 0 raw view fingerprint groups differ. Observed raw view fingerprint groups also match.

postgres: 341 canonical table fingerprint groups match exactly; 0 raw view fingerprint groups differ. Observed raw view fingerprint groups also match.

sqlite: 341 canonical table fingerprint groups match exactly; 0 raw view fingerprint groups differ. Observed raw view fingerprint groups also match.

**Passed:** final isolated `podman ps -a` contains only the twelve inherited project containers in the isolated graph root. The owner-requested default-store read-only listing/inspection matches all three live container IDs, image IDs, full nanosecond start times and running states to `live-before.txt`. No proxy-service actions were performed. The receipt records the comparison time and both listings.

**Passed:** configured private-canary process/argument and container-log scans; this claim does not include the separately recorded published-bootstrap output failures.

**Not run:** live cutover, DataIntent project suites, Docker/BuildKit execution, other architectures, generated benchmarks and other unconfigured dataset/engine combinations. The 95-pair claim concerns the supplied loaded configuration. No claim is made that these account grants implement a general SQL statement classifier or resist deliberate privilege changes by trusted administrators. Software source URLs and read times are retained in the [source receipt](../validation/strict-read-sources.json); this change adds no engine-version or vendor-support claim.
