# DL-077 version 1 feasibility gates

20 November 2026 · DL-108 item 12 · design revision `0896ebc8205f3b04063afcd1e11d7b09ab146c7a`

The design names 58 gates, 52 engine-only and six needing the PostgreSQL hook
prototype. All 58 test entry points were invoked. G-19b reached its native
filesystem assertion and control. The other 57 stopped before their assertions
when the isolated Podman store could not be opened. Neither a PostgreSQL nor a
MySQL behavior was observed. There were no Failed or Unsupported **gates** in
this run. The native feasibility requirement for design review remains open.

The worktree did not contain an `AGENTS.md` at the applicable locations.
The repository rules reproduced in the task were followed.

## Gate results

Each gate ID links to the command's executable. The Podman preflight shown below
applies to every row that stopped before an assertion. The last column is the
consequence of a failure as written in section 8.1, for reference when the gate
can be run.

| Gate | Kind | Result | Observed | Control | What the design withholds on failure |
|---|---|---|---|---|---|
| [G-1a](../../tests/gates/G-1a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | every PostgreSQL template, copy, and reset from a template |
| [G-1b](../../tests/gates/G-1b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | every PostgreSQL template, copy, and reset from a template |
| [G-1c](../../tests/gates/G-1c) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **every use of a template as pristine:** PostgreSQL copies, template resets, and rule 2's registration |
| [G-2a](../../tests/gates/G-2a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the read group and the owner's writing: all PostgreSQL copies and reset-made working copies |
| [G-2b](../../tests/gates/G-2b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the closed defaults of pull request #14 on every copy and reset-made working copy |
| [G-2c](../../tests/gates/G-2c) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **the strict profile on every copy and reset-made working copy** |
| [G-2d](../../tests/gates/G-2d) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | 4.1's `CONNECT` table; the copy's own comment as its proof |
| [G-23](../../tests/gates/G-23) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | a copy's owner writing its copy: PostgreSQL copies |
| [G-7a](../../tests/gates/G-7a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | on PostgreSQL: every `copy` command that changes anything; `reset` of one database |
| [G-7b](../../tests/gates/G-7b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | nothing by itself: it fixes where the lock is taken. If the key did conflict across databases, the design is unchanged. |
| [G-8a](../../tests/gates/G-8a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | template records; rule 2's registered template; a copy's proof |
| [G-8b](../../tests/gates/G-8b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | on PostgreSQL: `copy drop`, `copy sweep`, and the reconciliation's drop of a transient |
| [G-24p](../../tests/gates/G-24p) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the proof on PostgreSQL: `copy drop`, `copy sweep`, the reset's steps b and f |
| [G-24w](../../tests/gates/G-24w) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | `copy drop` and `copy sweep` on that engine |
| [G-3a](../../tests/gates/G-3a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | PostgreSQL's reset of one database |
| [G-3b](../../tests/gates/G-3b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | PostgreSQL's reset of one database |
| [G-3c](../../tests/gates/G-3c) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the door and the session decision on PostgreSQL |
| [G-26p](../../tests/gates/G-26p) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **PostgreSQL's reset from the image** |
| [G-9](../../tests/gates/G-9) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | on PostgreSQL: `copy create`; `reset` of one database |
| [G-32a](../../tests/gates/G-32a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | ending any session without `--discard sessions` |
| [G-32b](../../tests/gates/G-32b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **the default itself:** if a console holds sessions by itself, every default reset would refuse. That returns to the deciders. |
| [G-5a](../../tests/gates/G-5a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | P-1's reason. If the role can already, P-1 is still applied, and H-1 is recorded as not reproduced. |
| [G-5b](../../tests/gates/G-5b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | P-3, P-5 |
| [G-5c](../../tests/gates/G-5c) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | P-6; a declared writer |
| [G-6a](../../tests/gates/G-6a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | nothing: it shows the hazard that rule 4 is for |
| [G-6b](../../tests/gates/G-6b) | H | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | rule 4. **Only a failure to refuse the password change while it still reads selects 4.5's fallback.** |
| [G-4a](../../tests/gates/G-4a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | rule 1's reason. Whatever it shows, rule 3 confirms. |
| [G-4b](../../tests/gates/G-4b) | H | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | H-3's resolution, or the deciders |
| [G-29a](../../tests/gates/G-29a) | H | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **PostgreSQL copies, here and from elsewhere.** Returns to the deciders. |
| [G-29b](../../tests/gates/G-29b) | H | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **PostgreSQL copies, here and from elsewhere.** Returns to the deciders. |
| [G-29c](../../tests/gates/G-29c) | H | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **PostgreSQL copies, here and from elsewhere.** Returns to the deciders. |
| [G-29d](../../tests/gates/G-29d) | H | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the claim that rule 2 binds namespace owners only |
| [G-35p](../../tests/gates/G-35p) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | default 2 on PostgreSQL |
| [G-10a](../../tests/gates/G-10a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | every MySQL template and copy |
| [G-10b](../../tests/gates/G-10b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | every MySQL template and copy |
| [G-10c](../../tests/gates/G-10c) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the claim that only an administrator can open a template |
| [G-11a](../../tests/gates/G-11a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | every grant the product makes on MySQL |
| [G-11b](../../tests/gates/G-11b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | MySQL namespaces; a MySQL owner's credential used away from the service |
| [G-11c](../../tests/gates/G-11c) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | `demo`'s narrowing; declared readers and writers; `demo_reads` |
| [G-13](../../tests/gates/G-13) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | MySQL copies of each dataset that uses a kind that fails |
| [G-15a](../../tests/gates/G-15a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | on MySQL: every `copy` command that changes anything; `reset` of one database |
| [G-15b](../../tests/gates/G-15b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | `copy drop` and `copy sweep` on MySQL |
| [G-24m](../../tests/gates/G-24m) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the proof on MySQL: `copy drop`, `copy sweep`. With no proof no MySQL copy can be removed, so **MySQL copies are not offered.** |
| [G-26m](../../tests/gates/G-26m) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **MySQL's reset of one database** |
| [G-27a](../../tests/gates/G-27a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | MySQL's reset of one database, where a writer is declared |
| [G-27b](../../tests/gates/G-27b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | MySQL's reset of one database, where a writer is declared |
| [G-16](../../tests/gates/G-16) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | nothing: it selects the branch of 4.5 |
| [G-17a](../../tests/gates/G-17a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | `copy create` on MySQL |
| [G-17b](../../tests/gates/G-17b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | MySQL's reset of one database |
| [G-18a](../../tests/gates/G-18a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | the `binary_log` key: withdrawn, and the log stays on |
| [G-18b](../../tests/gates/G-18b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | **nothing of this work:** a failure here is a defect of the image as it is, and returns to the deciders |
| [G-35m](../../tests/gates/G-35m) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | default 2 on MySQL |
| [G-33a](../../tests/gates/G-33a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | item 9's rule, on that engine |
| [G-33b](../../tests/gates/G-33b) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | `copy` and `reset` commands on that engine, beside anything that replaces a volume. **Without it, `megasamples up --discard engine` and a whole engine's reset say that callers elsewhere must be stopped first.** |
| [G-19a](../../tests/gates/G-19a) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | every SQLite `copy` command |
| [G-19b](../../tests/gates/G-19b) | E | Passed | Untouched copy matched. The replacement differed and was put back without overwriting. None of 1,000 new files shared the inode. | Shown | the proof on SQLite: `copy drop`, `copy sweep` |
| [G-19c](../../tests/gates/G-19c) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | SQLite `copy create`; SQLite's reset of one database |
| [G-20](../../tests/gates/G-20) | E | Not run | Podman preflight exited 1. Gate driver exited 77. | Control not shown | every SQLite `copy` command that changes anything |

## Command evidence

The command for each row was `tests/gates/<gate-id>`, with
`DL077_GATE_TARGET` pointing to a private scratch manifest identifying the
specified isolated environment. Each of the 57 blocked launchers sourced
`env.sh` and produced the same Podman result before opening a test container.

```text
$ podman info --format '{{.Store.GraphRoot}}'
exit 1
Failed to obtain podman configuration: set sticky bit on: chmod /run/user/1000/libpod: read-only file system
```

G-19b ran on a private directory under `/tmp`, with real filesystem calls.

```text
$ tests/gates/G-19b
untouched copy: same file
control rejected replacement: the moved file is not the retained file
put-back preserved the replacement without overwriting
1000 newly created files: none shared the retained inode
exit 0
```

| Check | Result | Observed output |
|---|---|---|
| Initial `free -m` | Passed | The `available` column reported 23,472 MiB, above the 15 GiB threshold. No stack start was attempted. |
| Isolated `podman ps -a --format '{{.Names}} {{.ID}} {{.Status}}'`, with `env.sh`, before and after | Failed | Both attempts exited 1 with the same read-only error shown above. Neither emitted a container list. |
| Live `podman ps -a --format '{{.Names}} {{.ID}} {{.Status}}'`, without `env.sh`, before and after | Failed | Both read-only attempts exited 1 with the same error and emitted no container list. Equality of these empty outputs provides no isolation proof. |
| `findmnt -no OPTIONS -T` for the isolated `run` and `tmp` directories | Passed | Both mounts reported `ro,nosuid,nodev,relatime`. Neither directory was cleared. |
| `unshare --user --map-root-user true` | Failed | `unshare: write failed /proc/self/uid_map: Operation not permitted`. |
| `python3 -m compileall -q tests/gates` | Passed | Exit 0, no output. The 58 executable gate IDs match the design. |
| `make -C tests/gates/prototype` | Failed | `make: pg_config: No such file or directory`; exit 2. The six H launchers were invoked before the C prototype was written, but their target checks prevented a native red. The prototype was never loaded. |
| `git add tests/gates docs/validation/dl-077-v1-gates.md` | Failed | Git could not create `.git/index.lock` on the read-only mount. The local branch could not be updated. |
| `git diff --cached --check` with a temporary Git index | Passed | The staged gate files and validation record passed the whitespace check. |
| GitHub tree creation for branch publication | Failed | The tool reported `MCP tool call requires approval, but approval policy is never`. |
| Baseline and restored stack fingerprints at `e61335f` | Not run | The isolated store could not be opened. Neither image identities nor dataset fingerprints could be captured. No stack was started, stopped, modified or restored. |

## Test coverage still to verify

The native tests and prototype require execution on the owned isolated stack to
verify their fixtures and assertions. G-32a drives two CloudBeaver catalog
navigation sessions and inspects the PostgreSQL backends after SQL activity. A
statement submitted through the SQL editor has yet to be exercised. G-16 uses
DbGate's shipped driver and stored demo connection settings for that console's
probe. No G-16 password-change outcome or usable refusal mechanism was established.
