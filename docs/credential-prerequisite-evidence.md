# Configured reset credentials and cutover prerequisite (DL-079)

This draft records completed evidence while the exhaustive isolated validation continues.
The live deployment and socket forwarders have not been operated. Templates, database copies
and their CLI are outside this prerequisite and remain a later rollout.

The native pre-fix MySQL dataset reset **Failed** as expected with a non-default configured
root password. Its query helper received access denied, and its count helper silently returned
an empty mapping. The corrected native `make reset R=mysql:pubs` **Passed** and verified all
11 tables. PostgreSQL's authenticated TCP dataset reset also **Passed**.

Two native password rotations **Passed** for MySQL demo/admin/root@localhost/root@% and
PostgreSQL demo/admin/postgres: each new password connected and each previous password was
refused by authentication. The second set exercised quotes, backslashes, dollar signs, spaces
and colons through `.env` and Compose recreation. Values remain private and untracked.

The code gate **Passed: 256 tests**, generated documentation, and reproducible port records
for 31 loaded port datasets. Private client SQL-file/LOCAL INFILE and binary/Unicode/newline/tab
dump/restore checks **Passed** on a disposable copy. Credential files/directories and the isolated
socket have the required private permissions. PostgreSQL PID1 environment contents were checked;
MySQL PID1 contents are **Unsupported** because the process denies the tested proc reads.
No generated password has been found by the active process/public-environment and container/task
log canary observers.

The complete selector resets, all image/readiness checks, all console checks and fresh runtime
counts/fingerprints are being collected. This draft makes no completion claim for those gates.
The final report will include their receipts, exact image IDs and the candidate transfer digest.

The live runbook now generates all four overrides into mode-0600 `.env`, verifies new/previous
passwords through native authentication, identifies the private handoff location, and verifies
original image/configuration archives and cold copies by digest before rollback.

Credential implementation sources read **2026-11-18 00:55:49 UTC**:
[MySQL option files](https://dev.mysql.com/doc/refman/9.7/en/option-files.html),
[PostgreSQL pass files](https://www.postgresql.org/docs/18/libpq-pgpass.html),
[Compose interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
Engine release sources read **2026-11-18 01:07:54 UTC**:
[MySQL](https://dev.mysql.com/doc/relnotes/mysql/9.7/en/),
[PostgreSQL](https://www.postgresql.org/docs/release/18.7/),
[SQLite](https://sqlite.org/releaselog/3_54_1.html).
