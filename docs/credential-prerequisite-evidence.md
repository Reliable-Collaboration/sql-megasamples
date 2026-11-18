# Configured reset credentials and cutover prerequisite (DL-079)

The configured-credential reset, password propagation and full corrected-build rehearsal
**Passed** in the isolated stack. The [machine-readable receipt](validation/credential-prerequisite-2026-11-18.json)
records commands, outcomes, timings, counts, canonical fingerprints, image IDs and evidence digests.
The live deployment and socket forwarders were not operated. DL-077 templates/copies and their
CLI remain a later task and second rollout.

## Credentials and native rotation

Before the fix, the native `make reset R=mysql:pubs` **Failed** with a non-default configured
root password. The direct query received access denied and the count helper silently returned
an empty mapping. The exact Make exit code was not retained; no numeric exit code is claimed.
After the fix the same reset **Passed**, restoring all 11 tables. PostgreSQL's authenticated
TCP dataset reset also **Passed**. The original 23 credential regressions failed before their
fixes; two additional verifier regressions caught loopback TCP selecting the wrong root account.
All **25 credential tests** now pass without weakening their assertions.

| Engine/account | Current password | Previous password | Native evidence |
|---|---|---|---|
| MySQL `demo@%` | Passed | Refused: Passed | Published TCP, both A/original and B/A rotations |
| MySQL `admin@%` | Passed | Refused: Passed | Published TCP, both rotations |
| MySQL `root@%` | Passed | Refused: Passed | Published TCP, both rotations |
| MySQL `root@localhost` | Passed | Refused: Passed | Unix socket, B accepted; A and original refused |
| PostgreSQL `demo` | Passed | Refused: Passed | Published TCP, both rotations |
| PostgreSQL `admin` | Passed | Refused: Passed | Published TCP, both rotations |
| PostgreSQL `postgres` | Passed | Refused: Passed | Published TCP, both rotations |
| SQLite server accounts | Unsupported | Unsupported | File-based engine has no server accounts |

Native inventory also matched exactly these seven login accounts and found no temporary test accounts.
Each refusal required an authentication error, rather than a connection failure. Every accepted
identity is retained in the receipt. The original local-root TCP observation actually selected
`root@%`; it is retained honestly and supplemented by the socket test. The reusable verifier
now requires the exact identity. Both Compose generators now forward their superuser override,
and reset/count helpers share `config.passwords()`. The second rotation exercised apostrophes,
double quotes, backslashes, dollar signs, spaces and colons through private `.env` and recreation.

MySQL clients use private option files; PostgreSQL clients use `PGPASSFILE` paths and authenticated
network addresses. SQL-file, LOCAL INFILE, binary/Unicode/newline/tab dump/restore and cleanup on
a disposable source **Passed**. `.env`, the daemon socket and client/health files are mode 0600;
client directories are mode 0700. PostgreSQL PID1 contents contained no password. Reading MySQL
PID1 environment contents is **Unsupported** because both tested readers were denied; its mode
0400/public-access checks Passed. Startup/console metadata remains inspectable by the daemon
owner. Existing generated help pages and console workspaces contain credentials and remain
private; no screenshots were retained.

The process/public-environment and task/container-log canaries **Passed**, with no configured
random password found in sampled arguments, publicly readable environments or scanned logs.
Sampling is not an assertion that every short-lived process was observed. Protected environment
contents are not publicly readable, and the MySQL PID1 limitation above remains explicit.

## Corrected-build validation

| Validation | Result | Evidence |
|---|---|---|
| Whole repository `make check` | Passed | 258 tests, generated documentation and reproducible loaded port records |
| Asset audit | Passed | Repository publication/asset checks |
| Full runtime matrix | Passed | 95 supported pairs: MySQL 33, PostgreSQL 31, SQLite 31 |
| Counts and canonical fingerprints | Passed | Per-pair actual observations in receipt; frozen live-feed records retained |
| SQLite byte equality | Passed | All 28 physical files equal verified build, `/data` and shared console copy |
| Every reset scope | Passed | Mixed pairs, each whole engine, all engines, all 95 selectors, dataset flags and shared-database append selectors |
| Reset fidelity/count helpers | Passed | Same-count text/binary changes restored, added objects removed, exact FK definitions and both SQLite copies checked |
| All three image suites | Passed | Unchanged copy/server budgets; full suite results and commands retained |
| Readiness gates | Passed | MySQL 43.5/3.2 s, PostgreSQL 39.0/0.3 s, SQLite 22.4/0.1 s copy-run/query intervals |
| Five consoles | Passed | Landing gate; both accounts in phpMyAdmin/Adminer/DbGate; all 32 CloudBeaver connections |
| Endpoint permissions | Passed | Configured sign-ins, wrong-password refusal, readonly denial, admin writes and temporary account lifecycle |
| Candidate transport | Passed | Exact eight image IDs survived export/load; running applications remained unchanged |
| Runbook syntax/digest fixture | Passed | Eight shell blocks, nine embedded Python fragments; cold-copy digest detects byte/mode/symlink changes |
| Isolation | Passed | Isolated store contains only expected rehearsal containers; all eight application services running; live baseline identical |
| Four port combinations | Unsupported | BTS and WWI OLTP on PostgreSQL/SQLite; fresh native translator refusals retained |

Fingerprints use the repository's canonical column sets and `(n, x, s)` observations. Existing
verification limits remain: unordered aggregate views can be count-only, and SQLite computed
decimal comparisons omit documented inexact columns. No checks were weakened for this task.
The physical corpus is 30 MySQL databases and 28 each on PostgreSQL/SQLite; logical dataset
counts include append selectors and should not be mistaken for physical database counts.

The first concurrent full image-build attempt Failed during context transport; the unnecessary
MySQL rebake client was interrupted. The tested runtime images instead add the changed wrappers
to the exact recorded immutable DL-074 parent images. All image suites and the entire runtime
matrix were rerun on those resulting IDs. The private-client fixture initially omitted server
LOCAL INFILE enablement; enabling it only on the disposable fixture resolved that check. An
initial candidate-manifest export assumed SQLite had a TCP port; the already-written archive
was verified without rewriting it, and the corrected transport probe Passed. These earlier
attempts remain in the receipt rather than being presented as successful commands.

## Exact candidate and handoff

The isolated stack uses the implementation software tree identified in the receipt. Its final
evidence commits change validation/report files only. Before merging, the software tree is
checked against the exported candidate; after merging, the same images and source tree must
remain in use. Every configured dataset stays loaded for DataIntent's interim comparison.

| Engine | Tested image ID |
|---|---|
| MySQL | `20ecf18761195a5c900e9370b3e4d996ecfefdb20c2a555d827110ba9a2f3134` |
| PostgreSQL | `41ab1eb7a3451ad2b319993cd452528d381eeeea3a35ce658c62aab721940fc3` |
| SQLite | `090695cab2b5085144862daaedc9839036058f5ec0387a866c653eb8b9670ebb` |

The eight-image archive remains privately in the clone at
`build/credential-upgrade/candidate-images.tar`, mode 0600, **70,269,314,560 bytes**,
SHA-256 `528d83747267dfa531a696892fd0172be7aa561e99f7cea0ae1d4488aef30b53`.
It contains the factory images, not current volumes or `.env`. The live runbook imports this
exact candidate and checks the archive, software tree and each image ID before use; it does
not silently rebuild after DataIntent's comparison.

The canonical isolated credential file is
`/home/rcc-vstudio/working/sql-megasamples-upgrade/.env`, mode 0600. MySQL listens only at
`127.0.0.1:13306`, PostgreSQL at `127.0.0.1:15432`, and consoles at ports 18080–18084.
Give DataIntent the file location and merged revision privately, never password values in notes.
The [live runbook](live-upgrade-runbook.md) specifies the future live `.env` location, all four
password overrides, native new/previous-password verification, and rollback inputs retained by
digest: the original 9.7.2 image archive and image IDs, private configuration archive, and cold
copies with deterministic stream digests including ownership/modes and symlink targets.
Actual live backups have not been created by this task.

## Sources and verification limits

Implementation sources read **2026-11-18 00:55:49 UTC**:
[MySQL option files](https://dev.mysql.com/doc/refman/9.7/en/option-files.html),
[PostgreSQL password files](https://www.postgresql.org/docs/18/libpq-pgpass.html), and
[Compose interpolation/precedence](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
The inherited target versions, also checked natively on the running candidate, are MySQL 9.7.4,
PostgreSQL 18.7 and SQLite 3.54.1. Release sources read **2026-11-18 01:07:54 UTC**:
[MySQL release notes](https://dev.mysql.com/doc/relnotes/mysql/9.7/en/),
[PostgreSQL 18.7](https://www.postgresql.org/docs/release/18.7/), and
[SQLite 3.54.1](https://sqlite.org/releaselog/3_54_1.html).
No version pin changed in this prerequisite. The receipt cites the repository source and read
time for each unsupported port refusal; the earlier [LTS audit](lts-upgrade-evidence.md) retains
sources/read times for unchanged client pins and support selections.

**Not run:** DataIntent's interim comparison/suites; live cutover, actual live configuration/cold
backups and rollback; LAN-forwarder operations; native Oracle verification pending terms;
full generated/user-fetched benchmarks; Docker/BuildKit, other platforms/architectures and hosted
CI; new browser screenshots. The runbook was syntax/fixture checked, not executed live. MySQL
PID1 contents and SQLite server-account authentication remain Unsupported as described above.
