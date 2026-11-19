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

**Historical policy from the first correction, superseded below.** The live teardown
root cause is unknown. The first correction required all four checks,
for both stop and rollback down: all engines exited; no deployment container running;
no process holding any data mount; no leftover pasta/slirp4netns/rootlessport belonging
to that deployment. Inconclusive attribution blocks continuation. Helpers belonging
to a separate isolated store can remain only with recorded attribution. Existing
LAN forwarders were unchanged. For recovery use the current
[phase-specific state table](live-upgrade-runbook.md#teardown-and-rollback-states-and-gates)
and [native scanner policy](live-upgrade-runbook.md#conditional-rootless-network-teardown-failure-stop-rollback-stop-and-down),
which distinguish original cold-copy eligibility from failed-candidate removal.

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

**Historical round-two scanner policy, superseded by the round-three correction.**
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
(read **2026-11-18 19:03:41 UTC**): mapped subordinate IDs remain in scope. Historical, superseded by DL-088: a native-host UID/start-time inventory
distinguishes other owners before unshare translates their UIDs to overflow. Assumed-other owners get a second native credential check before a successful gate;
changed credentials refuse. Current mapped UIDs take precedence over inventory. Without
that independent evidence, an ambiguous overflow UID remains unresolved; a mapping
extent’s unmapped starting ID cannot prove that every ID in the extent is unmapped.

The revised procedure still has not run end to end on the live store or with
engine-size archives. Full live restoration, forwarded authentication/TLS,
kernel/AppArmor capture and the DataIntent acceptance suite remain Not run here.
The netns root cause remains unknown. As of 2026-11-18, acceptance remained held;
DataIntent owns its acceptance record.

## Round-three scanner correction, 2026-11-18 (historical)

The previous scanner policy is historical, not a recovery instruction. Use the
current [state table](live-upgrade-runbook.md#teardown-and-rollback-states-and-gates)
and the native scanner procedure in the runbook's teardown-error section. The
historical scanner walked the host initial namespace, compares mounts only on recorded
source devices/roots, classifies zombies/exited tasks, names unreadable operations,
and attributes helpers by recorded namespace or specific container cgroup. It
refuses evidence of deployment holders/helpers or unresolved mounts on a source's
device. It reports other owners, unreadable operations and unattributed
helpers without certifying them. Review those limits even after status 0.

The native scratch proof kept all existing stacks up. An unheld directory passed;
a deliberate host file holder and a scratch rootless bind holder each refused with
the named process, then passed after that owned process/container stopped. These
are scanner proofs, not an end-to-end live rollback or acceptance. DataIntent owns
the acceptance record; acceptance remained held as of 2026-11-18.

The eighteen persistent `FileNotFoundError` entries in the retained round-two
scan were checked read-only against their process state on 2026-11-18: all were
zombies (sixteen `python`, one `docker`, one `dpkg-preconfigu`). The current scanner
classifies these before attempting namespace or descriptor inspection. Native
inspection still encounters denied operations; its receipt records these by
process name, operation and error class, and status 0 certifies only inspectable
evidence. The original netns teardown cause remains unknown.

The [round-three correction receipt](validation/live-upgrade-review-r3-2026-11-18.json)
records S1–S8, T1–T5, reason-specific reds/greens and commits, the native scratch
proof, all-engine image checks, the repository gate and exact container isolation
comparison. The full original restoration and forwarded live sign-ins remain
unverified; no independent blessing is claimed by the authoring session.


## DL-088 bounded gate, 2026-11-18

The round-two inventory and round-three discovery policies above are historical.
DL-088 governs the current [record/verify gate and recovery routes](live-upgrade-runbook.md#teardown-and-rollback-states-and-gates).
Capture belongs before stop, survives container removal and a fresh shell, and
binds process start times, cgroups, helpers and canonical data identities to one
boot. Required inspection gaps HOLD; confirmed deployment survivors and readable
holders REFUSE. Shared helpers with independently verified remaining consumers
are reported. PASS states a bounded deployment claim, never host-wide quiescence.
Exhaustive discovery is separately diagnostic and its exit status cannot gate.
The netns root cause remains unknown. Native acceptance and test results for this
revision are recorded separately; prior scanner receipts do not prove DL-088.
As of 2026-11-18, DataIntent acceptance remains held; no independent blessing or
live restoration is claimed by this correction.


The [DL-088 receipt](validation/live-upgrade-review-r4-part2-2026-11-18.json)
records this session's tests, decision-rule removal controls and native outcomes.
The running isolated deployment's capture identified its shared helper and seven
dedicated helpers without process arguments. Scratch network-independent checks
proved process/exec survivors, partial removal and fresh-shell continuation,
subordinate-UID descriptor-only inspection (a real required `fd` PermissionError/HOLD),
a fault-injected unreadable required `stat` inspection (patched `Path.read_text`,
not a native operating-system denial), cross-filesystem aliases, equal path text on different filesystems, source
replacement and a zombie leader with a live worker. Expected REFUSE and HOLD
outcomes are successful tests, not cold-copy authorization.

**Historical part-two limitation:** the fresh scratch store's published bridge
failed when Pasta could not open its rootless network namespace (permission
denied); the earlier slirp attempt timed out. That rehearsal did not establish
the published-port lifecycle or the dedicated/shared helper-survivor cases.
This startup failure does not reproduce or explain the live teardown failure.

The [part-three native receipt](validation/live-upgrade-review-r4-part3-2026-11-18.json)
records the subsequent proof in the working isolated store, with a separate
scratch Compose project: two containers, a bridge network, one checked loopback
publication, a scratch named volume and a scratch bind source. Capture, stop,
phase-state verification and the process gate **Passed**, including partial
removal and continuation from a fresh shell. The native regression first exposed
a false HOLD: image EXPOSE entries without host bindings had been mistaken for
published ports. The corrected capture tests actual host bindings.

The project's recorded `rootlessport` was deliberately kept alive with SIGSTOP
through stop. Verification **Passed** by returning REFUSE specifically for
`dedicated helper survives`; SIGCONT released it, it exited, and verification
returned PASS. The recorded shared `slirp4netns` helper survived with ten
independently verified remaining consumers and caused no refusal. **Unsupported:**
the shared helper without another consumer. The isolated stack must remain
running and uses that same helper; a second scratch project cannot remove those
consumers. No zero-consumer native proof is claimed.

Cleanup removed the scratch project's containers, network and volume; no
container, network or volume named `dl088-proof-*` remained. All twelve isolated
containers retained their IDs, images, states and start times. Read-only inspection also matched the live
containers' IDs, images, states and start times to the retained cutover record.
The original netns root cause remains unknown. These results do not establish a
live restoration or DataIntent acceptance.

The alternative unchanged-original-data restart route is fixture-tested only.
It independently checks original data objects and rejects overlap with candidate
mounts; a reused shared volume cannot be represented as unchanged. No native or
live original-volume recreation is claimed. As of 2026-11-18, DataIntent acceptance
remains held; this authoring session supplies no independent reviewer blessing.


## DL-089 down-state evidence and recovery, 2026-11-18/19 UTC

The [round-five receipt](validation/live-upgrade-review-r5-2026-11-18.json)
records authoring-session tests and native rehearsals, not independent approval.
DL-089 amends DL-088 for a project already stopped when rollback begins. The
[runbook route table](live-upgrade-runbook.md#rollback-routes-when-the-project-is-already-down-dl-089)
selects an ordinary capture while anything runs, exact-original restart with
retained configuration when every original ID still exists, or a distinct
per-container evidenced down capture for candidates. Unreadable required evidence
HOLDs. All-down original-stop capture still HOLDs before a cold copy.

**Historical round-five policy description, superseded by the round-six and
round-seven corrections below.** Earlier applicable captures remain required alongside the current record, including
legacy timestamped captures without an index. Recovery cannot replace the first
stop's obligations with a narrower capture. Current-boot/store, generation/data
association and identifier continuity determine applicability; stale/incomplete
history is never substituted for current evidence. History traversal errors HOLD.

Native proof used a separate published bridge project in the isolated store. Mixed
running/exited state, all-down state, created containers, exits 0/137/23, missing
containers and partial removal passed their expected gates. A readable cold-directory
holder refused and then passed after release; a container started after capture
refused. The actual guarded stop/down/process-verification block ran from fresh
Bash. Both the ordinary and down-state records verified after **full** `down`.
An empty project listing with an explicit never-created/missing placeholder also
passed with current store-helper and readable-source evidence. This does not claim
a historical cgroup search for an unknown container ID or complete teardown outside
the identified cgroups.

A separate native original-restart rehearsal used tiny fresh PostgreSQL, MySQL and
SQLite databases in existing isolated images. After cold copies, configuration
rotation and clearing SQLite's shared files, a real console listener forced the
port refusal. The actual fresh-shell restart route restored the whole retained
configuration, restarted the same original IDs on the same mounts, waited for
SQLite health before consoles, and left the occupied console stopped. SQL/file
fingerprints remained equal, shared files were rebuilt, original credentials
worked, rotated credentials failed specifically at authentication, and the `.env`
digest matched the retained one. Running originals, missing/replaced original IDs
and an extra candidate each refused. Configured health probes used the documented
second-process fallback; no health state was edited. Recreating removed originals
through `original-override` remains fixture-tested, not natively replayed.

The read-only live capture at **2026-11-18 23:52:41 UTC** completed: eight containers,
the captured roles `process`: 246, `conmon`: 8 and `dedicated helper`: 7;
sixteen cgroups, four data sources and the shared `pasta.avx2` helper, with no capture HOLD.
It read narrow Podman metadata, `/proc` and filesystem identity only. It did not
stop or signal anything, read environments/arguments or credential values, write
to the live checkout/store, or claim the running deployment was quiescent.

A supplementary owned container with an inspected 8 MiB limit produced a real
native OOM kill (exit 137). Candidate-teardown state, evidenced down capture and
verification all Passed. Its container and volume were removed. This supplements
the primary rehearsal's earlier OOM Unsupported row; that original record is kept.
The replayable driver is
[`rehearse-quiescence-oom.py`](validation/rehearse-quiescence-oom.py).

**Unsupported natively:** a live task retained in an exited container's cgroup;
a reboot, which needs a separately approved
disposable host; and the shared helper with zero consumers while the isolated
stack remains running. These branches retain focused fixtures and reversal
coverage. A second scratch project cannot remove the isolated stack's consumers.
Prior native descriptor/alias/thread proofs remain in the round-four receipts;
the patched required-stat read is explicitly fault injection, while the required
subordinate-UID descriptor PermissionError/HOLD was a real native denial.

Each scratch attempt retained its evidence and removed only its own containers,
network and named volume. The receipt records the full suite, decision-removal
controls, image checks, exact unchanged-stack comparison and image-test volume
cleanup, including a secondary anonymous volume. The original live netns teardown
cause remains **unknown**. A transient scratch cgroup-search HOLD is not an
explanation for it. Full live restoration, engine-size archive replay, forwarded
live authentication/TLS and DataIntent acceptance remain unproved. As of
2026-11-18, the acceptance hold remained DataIntent's.

## Populated backup and recovery corrections (2026-11-19 UTC)

The [round-six receipt](validation/live-upgrade-review-r6-2026-11-19.json)
records X1–X4 and their focused red/green checks. Capture discovery now lists
only the retained root and direct `rollback-*` attempt directories. It never
walks cold-data payloads. Unreadable capture inventories still HOLD. Identifier
reuse supersedes only the affected historical process/cgroup row; other evidence
in that capture remains required. Current-capture reuse still HOLDs.

The round-six native replica used the audited first-run top-level names, an attempt under
that backup, and the runbook's `podman unshare cp -a` from stopped scratch engine
data. PostgreSQL's populated data directory has subordinate ownership and mode
0700. Two cold-data directories were genuinely unreadable in the host namespace.
Its PostgreSQL data was at `postgres/fixture`, rather than `postgres/18/docker`.
Its MySQL cold root was subordinate-owned mode 0700, whereas the real retained
MySQL and PostgreSQL roots are UID/GID 100998, mode 1777. The replica's PostgreSQL
root was owned by the host user, mode 0755. It had two observed unreadable
directories rather than the real backup's 28, different MySQL depth/ownership,
placeholder non-data files, fewer services and different networking. The gates
only stat cold roots and list capture locations; these differences did not test
payload compatibility. Round seven asserts the root metadata and PostgreSQL
path explicitly, while retaining the other stated limits.
No live cold-data contents were read or copied. The earlier empty-directory
rollback-gate composition is superseded by
[`rehearse-original-restart.py`](validation/rehearse-original-restart.py) and
[`rehearse-rollback-replica.py`](validation/rehearse-rollback-replica.py).

**Round-six native results:** the exact-original restart; both guarded restart-policy
blocks on scratch IDs; fresh-shell rollback stop/down and restore gate; population
gate and actual four-tree population; pre-up gate. The populated trees matched
bytes, numeric ownership and modes. Each process gate verified earlier capture
history. The old helper returned the expected history-inspection HOLD on this
same replica. Namespace adaptation changes project/container/volume names and
Compose paths, retaining the runbook's stop function and gate commands. This
executes gate fragments and population; it does not replay engine-size image
archives, the complete bootstrap, configuration rollback or a live restoration.
This replica took the down-state route. Its policy pause ran on stopped/created
containers already set to `no`, so it did not prove the policy change required
on running `unless-stopped` services. The round-seven ordinary-route proof
replaces that limited policy claim.

The down-state full cgroup search is shared across rows and history checks.
ENOENT/ENODEV on a path that does not name a recorded container means absent;
unreadable or unresolved recorded scope still HOLDs. Mixed captures now state
the down-evidence limit. A reaped process is vanished, while other required read
errors remain HOLDs. Thirteen rule-removal controls each failed their targeted
regression, as required.

Unchanged-data recovery selects the saved console images and restores the
retained CloudBeaver workspace into a stopped replacement before starting it.
The shell regression selects CloudBeaver with a nonempty saved workspace.
Missing candidate engine mounts refuse the unchanged-data override. Its native
engine/console recreation remains **Not run**. Bootstrap and dispatch retain route
HOLD reports and status; completed or partial original restart phases refuse
teardown dispatch. The bootstrap's original-restart branch is exercised by tests.

The receipt records 842 suite tests, 54 documentation checks and all three engine
image checks Passed, plus exact isolation/cleanup comparisons. The image wrapper's
cleanup initially Failed on an observed volume already removed by the tests.
Creation-event association, matching creation timestamps, zero mounts and no
remaining references proved the three remaining test volumes before removal;
two observed volumes were already absent. Completed cleanup and isolation Passed.
The live netns teardown cause remains **unknown**; these scratch stops and downs
did not reproduce that error. Live restoration, forwarded live sign-ins and
DataIntent acceptance were **Not run** here. The previously documented native
reboot, exited-cgroup live-task and zero-shared-consumer cases remain Unsupported.
As of 2026-11-19 UTC, no new DataIntent acceptance decision was supplied.

## Ordinary route and history corrections (2026-11-19 UTC)

The [round-seven receipt](validation/live-upgrade-review-r7-2026-11-19.json)
records reason-specific reds, greens and rule-removal controls. Required cgroup
traversal now propagates enumeration errors even when membership files remain
readable. Historical mixed captures retain their process/data obligations, but
the current capture alone owns current-generation listing completeness. A new
container after the current capture still HOLDs. Retained `conmon` associations
include start time, so a reused PID alone cannot identify a survivor. ESRCH at
neighbouring process reads means vanished; required permission denials still HOLD.
Discovery excludes abort and image-load rehearsal directories.

Every original startup route saves its phase before its first effect. A regression
starts an original engine, fails the next health wait, reloads context in a fresh
shell, and requires dispatch to HOLD before teardown. Abort after pause/capture
HOLD accepts running exact originals without authorizing a copy. Both abort and
exact-original restart restore `unless-stopped` through guarded scoped updates.
The policy regression executes restoration and its failure branch.

The ordinary-route native proof used four running scratch services. Dispatch
selected `ordinary-capture`; the actual policy blocks changed running containers
from `unless-stopped` to `no`, restored the policy and paused again before capture.
The actual stop, state gate, `down` and restore gate ran together in one fresh
shell. Population and the pre-up gates each ran in another fresh shell, using the
saved context without per-fragment phase injection.
All three process gates Passed with applicable history checked. Four populated
restoration trees matched cold-copy bytes, numeric ownership and modes. The old
history helper still HOLDs on this replica's unreadable cold data. Cleanup removed
only the owned project and restoration volumes; the isolated stack was unchanged.

The cold copies were made with the runbook's `podman unshare cp -a` while the
scratch engines were stopped, before restarting them for the ordinary-route proof.
The PostgreSQL and MySQL cold roots are asserted as UID/GID 100998, mode 1777;
PostgreSQL's subordinate-owned 0700 data directory is at `postgres/18/docker`.
The real roots were checked read-only by names/modes/owners, without contents.
Remaining differences: seven unreadable directories versus 28 in the real backup;
smaller fresh databases; different MySQL internal ownership and directory depth;
four services rather than the full stack; engine data bind mounts rather than the
live anonymous volumes; scratch shared slirp4netns with other consumers rather than
live Pasta with none; SQLite cold root 0700 rather than 0755; different bridge
ports; and placeholders
for some non-data retained names. This proves the exercised bounded gates and
population, not full bootstrap, configuration/image restoration or compatibility
of the live payloads. No live cold contents were read or copied.

The DL-089 native cases in the round-five receipt were recorded by
2026-11-19 00:21:14 UTC, before the subsequent `down_evidence` rewrites. They remain
historical evidence. The round-seven receipt separately records the current
one-shot down/OOM harness reruns and their outcomes; it does not promote the older
runs to current-head proof. The historical assertion/test gaps were repaired by
archiving each fix's parent locally, applying only its test and retaining the red;
a planted bug separately proves the recorded-cgroup-vanish regression. Pushed
history was preserved. These are authoring-session checks, not independent approval.
