# First live upgrade and runbook corrections (DL-086)

The coordinator executed the runbook at `2cf1f3e9` on **2026-11-18**. The upgraded
service was verified as described below. As of **2026-11-18**, acceptance was held for a
DataIntent test failure outside this service; the acceptance record is DataIntent’s.
Independent approval of this revised procedure remained pending as of that date.


The private maintenance record is `build/live-upgrade-backups/20261118T133807Z/` in
the deployment checkout. Only its defect records and receipts were read for this
change. No private `.env`, `containers.json`, dump or data file from that backup
was inspected or copied. The public [correction receipt](validation/live-upgrade-corrections-2026-11-18.json)
records source-receipt hashes and the isolated validation results. Private backup
contents and credential values are not published.

## Executed service checks and their limits

`phase-b-6/phase-b-receipt.json` and `phase-b-6/live-end-state.json` retain the final
container/image identities and inherited runtime queries from attempt 5. They record
native account rotation, complete registry/count checks, SQLite file hashes and the
five supported added-dataset fingerprint/structural checks. They do **not** establish
a complete live rerun of the isolated fingerprint matrix, successful DataIntent suites,
certificate validation or a complete live rollback restoration.

The forwarded checks were **host protocol proofs**: PostgreSQL answered an SSLRequest;
MySQL sent the upgraded server greeting. Forwarded authenticated SQL was **Not run**.
Local authenticated account tests do not close that gap. The corrected procedure
requires client sign-ins from the host network after protocol checks (host clients or a
prepared tools container with `--network host`). Host `psql` and `mysql` are absent
in this documentation environment; no host installation or live connection was attempted.

| Runtime recorded after cutover | Release source | Source read (UTC) |
|---|---|---|
| PostgreSQL 18.7 (previously 18.6) | [Release notes](https://www.postgresql.org/docs/release/18.7/) | 2026-11-18 17:06:28 |
| MySQL 9.7.4 (previously 9.7.2) | [Release notes](https://dev.mysql.com/doc/relnotes/mysql/9.7/en/) | 2026-11-18 17:06:28 |
| SQLite 3.54.1 | [Release record](https://sqlite.org/releaselog/3_54_1.html) | 2026-11-18 17:06:28 |

MySQL's selected line is LTS ([release policy](https://dev.mysql.com/doc/refman/9.7/en/mysql-releases.html),
read 2026-11-18 17:13:34 UTC). PostgreSQL major 18 is supported under its major-version
policy ([version table](https://www.postgresql.org/support/versioning/), read
2026-11-18 17:13:34 UTC); PostgreSQL does not designate a separate LTS product line.
The earlier [LTS audit](lts-upgrade-evidence.md) retains all unchanged client/runtime
pins and the source URL/read time for each historical version or support selection.

## Corrections and regression evidence

| Defect | Replayed correction | Validation |
|---|---|---|
| 1. Multi-image save archived the first configuration under every tag | One docker archive per unique full image ID; hash the actual config referenced by `manifest.json` | **Failed (expected red):** old save omitted the second image. **Passed:** corrected saves identify both distinct configurations. |
| 2. Rollback checked/loaded the malformed archive | Check the entire per-image digest/configuration set before loading anything; load, explicitly re-tag every mapping, retain tag-to-ID checks; rehearse the full rollback set before downtime | **Failed (expected red):** old load mapped the second tag to the first image. **Passed:** corrected load restored each ID/tag. Corruption refused before any load in unit tests. |
| 3. Compose stop failed during SQLite network teardown | Stop on failure; permit coordinator continuation only after the four recorded checks | Reproduction attempts below; cause unknown. Cold copies must follow confirmed stop, not merely a Compose error. |
| 4. Unrelated process occupied the console port | Check every configured endpoint before downtime, after stop and again before console startup | **Failed (expected red):** old runbook omitted the gate. **Passed:** owned scratch listener refused; same port accepted after closing it. Project exemptions use only running containers' port fields. |
| 5. Rollback down failed during MySQL network teardown | Apply the same four checks before restoring branch/configuration/data | Reproduction attempts below; cause unknown. No blanket ignore, sudo or host-service workaround. |
| 6. Fourteen generated models were absent | Bundle compared-build metadata with digests, copy only missing matching files, audit the entire selected set before downtime | **Failed (expected red):** old runbook lacked the gate. Scratch checkout with its warehouse model removed was refused. **Passed:** transfer/repair and complete digest checks. Existing differing files cannot be overwritten. |
| 7. Forward verification ran inside an engine container | Probe protocols and sign in with clients on the host; take endpoint from private configuration/listening sockets | **Passed:** host-local synthetic PostgreSQL/MySQL protocol fixtures. Actual first-run host protocol proofs are inherited from the receipt. **Not run:** new live probes and forwarded client authentication. |

The unchanged six initial helper tests Passed before continuation. Three preparation
assertions then Failed against the old runbook. A further red test identified the
verifier's dependency on selected `build/live/*.observed.yaml`; the metadata bundle
now includes those observations as well as port models and optional SQLite drop lists.
A separate red test caught using native Podman in the tools-container port inspection;
that inspection now uses the selected Docker socket, while the bind probes run in
the tools container's host network namespace.

The authoring session's own review found that the inherited `ms_tool` function omitted interactive stdin.
A regression and an actual harmless heredoc in the isolated tools container both
**Failed (expected red)** before `podman exec -i` was added; both then **Passed**.
The runbook now checks a stdin execution marker and requires nonempty logical dumps.
Podman's [exec reference](https://docs.podman.io/en/latest/markdown/podman-exec.1.html),
read 2026-11-18 17:27:30 UTC, confirms that stdin is otherwise closed. The authoring session also
caught discarded teardown exit codes and missing shell recovery instructions.
Both status regressions and the fresh-shell recovery regression Failed before the
fix and Passed afterwards. Actual Compose exit codes are retained beside the logs;
a mode-0600 Bash context snapshot restores only selected non-secret variables and
the tooling function. These additional review findings do not renumber the seven
defects in the original live record.

Run the archive rehearsal **on the host**, from the upgrade clone:

```sh
. /home/rcc-vstudio/working/sql-megasamples-upgrade-env/env.sh
test "$CONTAINERS_STORAGE_CONF" = /home/rcc-vstudio/working/sql-megasamples-upgrade-env/storage.conf
mkdir -p build/dl086
python3 docs/validation/rehearse-live-upgrade.py
```

It asserts the graphroot, reads two existing isolated console images, seeds fresh
scratch stores and runs both old and corrected commands there. It starts no engine
and uses no database volume. It preserves the malformed fixture and successful
receipts under `build/dl086/rehearsal-*/`. Validation of the corrected runbook and helper has run only in scratch, never on the live store or the engine-size images. The complete revised runbook has not been replayed end to end.
The two-image regression is deliberately small; the runbook separately requires rehearsal of the **complete actual rollback
set** before downtime. That future live rehearsal was **Not run** by this task.
The first live run's full-set scratch rehearsal is recorded in the private phase-A
and rollback-load receipts. Live rollback reached the failed candidate Compose `down`;
branch/configuration restore, corrected live image load, new rollback volume creation and
cold-volume restoration were **Not run**. The coordinator subsequently continued cutover.
A complete live restoration remains unverified.

Podman's [save reference](https://docs.podman.io/en/latest/markdown/podman-save.1.html),
read 2026-11-18 17:06:28 UTC, explains that additional positional names are tags
unless multi-image mode is enabled. The corrected helper avoids that ambiguity.

## Network teardown investigation

Fresh scratch-store Compose startup with Pasta **Failed** opening the rootless network
namespace with permission denied. A scratch slirp4netns startup stalled and was
terminated; neither attempt reached stop/down. Those are startup limitations,
not reproductions of the live teardown failure. Only this task's scratch processes,
fixture containers and networks were cleaned up. Scratch image stores/receipts remain.
The separate isolated stop/down attempt and its result are in the correction receipt.
Three cycles of Compose up/stop/up/down with an owned console-image fixture and
ephemeral port **Passed** in the isolated store, with no teardown permission error.
The existing stack stayed running, so this does not reproduce removal of its last
rootless-network consumer.

**The live teardown root cause is unknown.** The runbook requires all four checks,
for both stop and rollback down: all engines exited; no deployment container running;
no process holding any data mount; no leftover pasta/slirp4netns/rootlessport belonging
to that deployment. Inconclusive attribution blocks continuation. Helpers belonging
to a separate isolated store can remain only with recorded attribution. Existing
LAN forwarders are unchanged.

## Documentation checks

The README's password/default/rotation/reset guidance was checked against
`.env.example`, `.gitignore`, `config.passwords()`, the Compose generators,
`megasamples/reset.py`, `megasamples/credentials.py`, and the existing native-password
verifier. Its LAN examples prompt for the read account's configured password and
keep the address outside Git. The examples' client flags were checked against
[psql](https://www.postgresql.org/docs/18/app-psql.html) and
[mysql](https://dev.mysql.com/doc/refman/9.7/en/mysql-command-options.html), both read
2026-11-18 17:13:34 UTC. They were not authenticated against live forwards here.
The runbook's metadata list was checked against the PostgreSQL/SQLite adapters,
`verify.live_hub_observed()` and `registry.image_counts()`.

Repository gate, full configured image suites, runbook syntax checks and final
isolation results are recorded in the correction receipt. Previous evidence pages
remain dated isolated reports, with this follow-up linked explicitly. No runtime
image, dependency pin, dataset expectation or credential value changes in this PR.

The strict password-output rule **Failed** during source inspection: repository
factory defaults and fixture credentials were displayed. No private credential value
was displayed or copied. The receipt
records this process failure without repeating any value.

The narrowed PostgreSQL account guidance was checked against `engines/postgres/init/`,
`megasamples/engines/postgres/image_test.py` and PostgreSQL's
[privilege definitions](https://www.postgresql.org/docs/18/ddl-priv.html) and
[large-object interface](https://www.postgresql.org/docs/18/largeobjects.html), read
**2026-11-18 18:03:54 UTC**. Sample-table write refusal does not revoke `TEMPORARY`,
large-object creation or routine execution. This change documents those limits;
it does not claim account hardening has been deployed.

## Correction follow-up on 2026-11-18

The [follow-up receipt](validation/live-upgrade-review-r1-2026-11-18.json) records
regressions for retained service-named archives, actual restored ID/tag pairs, complete-set
corruption refusal, host socket fixtures, executable preparation gates and recovery context.
A disabled preparation command and an ID-based loader against the service-named layout each
made the strengthened tests fail. At that revision, the scratch rehearsal stopped two owned fixtures and used the
then-required exited receipt and 137 acknowledgment. The state design below supersedes
that gate. That rehearsal used migrate/reset; the revised cleanup removes scratch images
and uses migrate with a final pause-PID check, avoiding reset’s machine deletion scope.

The additional netns attempt ran three owned-fixture Compose up/stop/up/down cycles in the
isolated store and did not reproduce the live error. The cause remains unknown. No live
teardown, full rollback, forwarded sign-in, kernel/AppArmor capture or DataIntent suite was
run by this follow-up. Kernel/AppArmor capture is an instruction for the next failure.

The README verifier command was run exactly with `PYTHONPATH=. .venv/bin/python` in the
isolated tools container, including the private previous-credential directory argument.
All configured accounts accepted the current password and refused the prior one specifically
by authentication. SQLite server authentication is Unsupported. A separate transactional
isolated PostgreSQL probe proved `demo` can create temporary tables and large objects and
execute routines; its changes were rolled back. Host `.venv/bin/python` was absent, so this
check does not claim the command ran natively on the host.


## Teardown design correction on 2026-11-18

The [states and gates design](live-upgrade-runbook.md#teardown-and-rollback-states-and-gates)
is the authority for originals, failed candidates and restored originals. Synthetic
fixtures retain only name/status/exit_code/running from the two first-run records.
Every service/state/phase cell is executable in `tests/test_teardown_gates.py`.
PostgreSQL/MySQL need a clean original stop; SQLite's observed 137 is expected;
OOM independently refuses cold-copy eligibility. Candidate teardown records created,
failed, OOM and missing containers and requires only not-running/PID 0.

Rollback uses an exclusive attempt directory and digest-checked configuration
extraction. Retained file digests and names remain unchanged in the synthetic
read-only-input test. Fully read-only parent directories refuse allocation; only
permission to add the new attempt directory is required. Bootstrap, early abort,
strict fresh-shell checks and continuation are executed through command stubs.
Python heredocs and `-c` bodies compile; every shell block passes `bash -n`.
The populated-volume checkpoint survives a pre-start refusal without repeating restore.
Once original startup begins, a separate saved phase holds any partial restart for
coordinator diagnosis; it cannot dispatch back into teardown/restoration.

The owner-scoped scanner reports other owners separately and refuses ambiguous
ownership, unreadable own processes, unresolvable mount roots and all remaining
network helpers. It resolves every host mount alias and includes file mappings
whose descriptors have closed. Its success-path gates also cover cold-copy,
configuration restoration and the four newly populated rollback volume targets.
There is no receipt-only helper exemption. On a shared host this strict gate may
remain refused even for an unrelated, attributed store; that is a readiness limit,
not evidence of a clean teardown.

The [second correction receipt](validation/live-upgrade-review-r2-2026-11-18.json)
records the actual host scan counts/classifications, red/green logs, commits,
suite/image outcomes and isolation proof. The scanner was run read-only on this
host against running isolated-stack mount records. Its execution Passed and its
quiescence decision Failed; no live stop or signals were attempted. Process
arguments, environments and private configuration were not collected in the receipt.

The scanner's field interpretation follows Linux's
[namespace owner interface](https://man7.org/linux/man-pages/man2/ioctl_nsfs.2.html),
[mountinfo](https://man7.org/linux/man-pages/man5/proc_pid_mountinfo.5.html) and
[file mappings](https://man7.org/linux/man-pages/man5/proc_pid_maps.5.html), all read
**2026-11-18 18:58:17 UTC**. Inspection refusals remain refusals; these sources
cannot prove that the host is quiescent. The UID-map fallback follows
[user namespace mapping rules](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)
(read **2026-11-18 19:03:41 UTC**): mapped subordinate IDs remain in scope. A native-host UID/start-time inventory
distinguishes other owners before unshare translates their UIDs to overflow. Assumed-other owners get a second native credential check before a successful gate;
changed credentials refuse. Current mapped UIDs take precedence over inventory. Without
that independent evidence, an ambiguous overflow UID remains unresolved; a mapping
extent’s unmapped starting ID cannot prove that every ID in the extent is unmapped.

The revised procedure still has not run end to end on the live store or with
engine-size archives. Full live restoration, forwarded authentication/TLS,
kernel/AppArmor capture and the DataIntent acceptance suite remain Not run here.
The netns root cause remains unknown. As of 2026-11-18, acceptance remained held;
DataIntent owns its acceptance record.
