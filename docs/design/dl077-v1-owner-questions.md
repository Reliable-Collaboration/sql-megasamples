# Version 1, slices 1 and 2: the owner questions

**For the two deciders (DL-104).** The slice 1 and 2 review loop closed at round 14 (`tests/dl077-v1-loop.md`). Fourteen questions in its five workstream briefs are owner decisions: they set an on-disk format, a public contract, the security posture, or what a person sees. Each workstream is designed and built only after its answers, one at a time.

Each question below has:
- the question;
- the facts, and the brief they come from;
- the options, each with its consequences for a person using sql-megasamples, for DataIntent, and for the format or security posture where relevant, and how reversible it is;
- a recommendation, and why.

The briefs have the detail:
- WS1, start certification: [`dl077-ws1-start-certification.md`](dl077-ws1-start-certification.md)
- WS2, orphan scan: [`dl077-ws2-orphan-scan.md`](dl077-ws2-orphan-scan.md)
- WS3, removal outcomes: [`dl077-ws3-removal-outcomes.md`](dl077-ws3-removal-outcomes.md)
- WS4, native suite binding: [`dl077-ws4-native-suite-binding.md`](dl077-ws4-native-suite-binding.md)
- WS5, container and volume lifecycle: [`dl077-ws5-container-volume-lifecycle.md`](dl077-ws5-container-volume-lifecycle.md)

"DataIntent" means RCC DataIntent as a consumer of these images and commands, mainly of `copy`'s and `reset`'s machine output.

## The answers asked for, in one place

| # | WS | Question | Recommended |
|---|---|---|---|
| 1 | 1 | How are password overrides applied before the server listens? | Keep the private start, made exact |
| 2 | 1 | Non-root starts: supported or refused? | Refused before any launch |
| 3 | 1 | Start refusals: a stable code? | A stable code in each line, exit 1 kept |
| 4 | 1 | The read-policy marker and extension version | Freeze at 1 for the release; bump both, and refuse older, on any later change |
| 5 | 1 | An image `HEALTHCHECK` | Yes |
| 6 | 1 | What a failed start leaves after a password change | The keys stay as applied, and the log names them |
| 7 | 2 | `reset --status` exit on an incomplete scan | Exit 0, with an opt-in failing flag |
| 8 | 2 | `up` on an incomplete scan | Warn only, showing partial findings |
| 9 | 2 | An invalid database after an interrupted drop | Its own warning code |
| 10 | 3 | An unsettled cleanup step's result field | Name the steps |
| 11 | 3 | Copies with an unknown outcome or never reached | Two new lists; exits unchanged |
| 12 | 4 | Authenticating to an unproven listener | No: prove by container ID first |
| 13 | 5 | `make down` before slice 3 | State it, and print one warning |
| 14 | 5 | What `status clean` may remove | The label only; list name matches |

## WS1: start certification

### 1. How are password overrides applied before the server listens?

**Facts.** The images ship with an initialised data directory and factory passwords. When `POSTGRES_PASSWORD`, `DEMO_PASSWORD` or `ADMIN_PASSWORD` is set, the wrapper starts a private server on its local socket, applies the passwords, and stops it; then the public server starts. Rounds 3 to 6 found routes around that private start: other arguments, a custom socket, and a failure after a change. Today both launches are certified (WS1 facts F, G, J, L).

**Options.**
- **A. Keep the private start, made exact.** It runs on an image-chosen socket directory, with the public launch's data directory and preload certified, and refuses any argument that would move its socket or data.
  - A person: credentials change before any TCP listener exists, as today.
  - DataIntent: no change.
  - Reversible: yes.
- **B. The public server applies them at its first start, before it listens on TCP.** Start it socket-only, apply, then restart it with TCP.
  - A person: one start becomes two.
  - DataIntent: no change.
  - Reversible: yes. It removes the private start but adds a restart with the same risks.
- **C. Apply passwords only after the public start, over the socket.** The factory keys work on TCP for a moment.
  - Security posture: a window with known factory credentials on the network.
  - Not recommended.

**Recommendation: A.** It keeps the property that matters, no TCP listener before the new keys, and closes the routes the reviews found without a new start sequence.

### 2. Non-root starts: supported or refused?

**Facts.** As a non-root user (`--user postgres`), the container exits before the public server starts, because the health passfile is root's to write. With overrides, the private start has already applied them (WS1 fact A; README).

**Options.**
- **A. Refuse before any launch,** with a clear message, when not root.
  - A person: one rule, no partial effects.
  - DataIntent: none.
  - Reversible: yes; support can be added later.
- **B. Support it:** move the passfile to a path the user can write.
  - A person: a supported non-root route that must be tested on every start path.
  - Security posture: the passfile's ownership and mode move with it.
  - Reversible: hard once documented.

**Recommendation: A.** Nothing in version 1 needs non-root starts. Refusing early removes the partial password change, and B can come later as its own design.

### 3. Start refusals: a stable code?

**Facts.** Each refusal is one line of free text, then exit 1. Supervisors and DataIntent would match the text (WS1 question 6).

**Options.**
- **A. Free text, as today.**
  - A person: reads the message.
  - A supervisor: matches English that can change.
- **B. A stable code in each line,** such as `megasamples-start: marker-missing: …`, documented, with exit 1 kept.
  - A person: the same message.
  - DataIntent: a contract to match.
  - Reversible: adding codes is not reversible once relied on, but it costs little.
- **C. A distinct exit code per rule.**
  - It conflicts with the server's own exit statuses, and supervisors see codes, not reasons.

**Recommendation: B.** It is cheap, and matching becomes safe. Freeze the code list with the release.

### 4. The read-policy marker and extension version: an on-disk format

**Facts.** A data directory carries a marker (`1`), and the image's `read_policy` extension has version 1. The version-1 script changed during development (round 5's loaded report, round 6's revoke), but the marker did not. So a volume from an earlier development build certifies, then fails its healthcheck (WS1 fact H, question 7). No release has shipped version 1 yet.

**Options.**
- **A. Freeze marker 1 and extension version 1 at the release.** After the release, any change to the extension script or its grants bumps both. The image refuses an older marker and names the upgrade route; there is no automatic migration.
  - A person: development-build volumes are unsupported; after the release, an incompatible volume is refused, never half-started.
  - Format: one rule for every later change.
  - Reversible: the rule can later gain a migration.
- **B. As A, with in-place migration:** at start, `ALTER EXTENSION … UPDATE` and re-applying grants as the superuser, before the public start.
  - A person: old volumes just work.
  - Format: each version needs a tested migration script.
  - Security posture: the start runs DDL on user data.
- **C. Bump now to 2,** so development volumes are refused.
  - It protects only task and development builds, which are disposable.

**Recommendation: A.** Before the release there are only disposable volumes. After it, refusing is the safe default, and migration (B) can be added when a real upgrade needs it.

### 5. An image `HEALTHCHECK`?

**Facts.** The healthcheck is defined in the generated Compose file only. A container started by hand has no health signal, and a bypassed entrypoint is then invisible (WS1 fact M).

**Options.**
- **A. Yes: the image carries the same check.**
  - A person: `docker run` shows health too.
  - Note: Podman keeps `HEALTHCHECK` only for images built in Docker format (`--format docker`), so the build must use it.
  - Compose can still override it.
  - Reversible: yes.
- **B. No: Compose only,** stated in the README as today.

**Recommendation: A.** It is the only signal for a hand-run container, and it costs one Dockerfile line and a build-format check.

### 6. What a failed start leaves after a password change

**Facts.** The private start applies each override in turn. If a later step fails (the public start, the passfile, a lost connection), the new keys stay in force (WS1 fact L, question 9).

**Options.**
- **A. The keys stay as applied, and the log names which roles changed.**
  - A person: the keys in force are the ones in `.env`, which the operator set on purpose; a retry with the same `.env` is a no-op.
  - Reversible: yes.
- **B. Roll back on failure,** by reading each role's password hash first and restoring it.
  - A person: an all-or-nothing start.
  - Security posture: old hashes are handled and restored by the wrapper.
  - More code on the start path.
- **C. Apply passwords only after the public start is certified.** This ties to question 1, option B.

**Recommendation: A.** The new keys are the operator's intended keys, so keeping them is not harm, and saying which were applied removes the uncertainty. B adds risk to the start path for little gain.

## WS2: orphan scan

### 7. `reset --status` exit on an incomplete scan

**Facts.** The PostgreSQL orphan scan (DL-119's detective control) reports `complete` or `incomplete` in `reset --status`'s JSON, and the command exits 0 either way, per design 3.5a (WS2 question 3).

**Options.**
- **A. Exit 0, as today.** The JSON says `incomplete`.
  - DataIntent: must read the field.
- **B. A distinct non-zero exit for an incomplete scan.**
  - A supervisor: notices it without parsing.
  - DataIntent: a contract change; `status` is no longer "did the command run".
- **C. Exit 0, plus an opt-in flag (`--fail-on-incomplete`)** that exits non-zero.
  - Both kinds of caller are served.
  - Reversible: additive.

**Recommendation: C.** It keeps 3.5a's contract, and supervisors that want a failing status can ask for one.

### 8. `up` on an incomplete scan

**Facts.** `up` prints the scan's warnings. An incomplete scan shows no directory at all, and `up` never fails on it (WS2 question 4).

**Options.**
- **A. Warn only, as today.**
- **B. Warn, showing what the partial scan did find, with an "incomplete" banner.**
  - A person: sees every orphan found, and that the list may not be whole.
  - Reversible: yes.
- **C. Fail `up`.**
  - A person: the stack does not start over a reporting gap.
  - The scan is detective, not a gate (DL-119).

**Recommendation: B.** It shows everything that is known, and never blocks a start on a report.

### 9. An invalid database after an interrupted drop

**Facts.** In PostgreSQL 15 and later, an interrupted `DROP DATABASE` leaves a catalog row marked invalid, with its directory partly removed. Today the scan does not report it. It is the drop-side twin of DL-119's create window (WS2 question 5, fact G).

**Options.**
- **A. Not reported.**
- **B. Its own warning code (`invalid-database`),** with the removal route: the database can still be dropped.
  - A person: knows what it is and what to do.
  - DataIntent: a new warning code.
  - Reversible: additive.
- **C. Reported as an orphan.**
  - It merges two different causes and remedies.

**Recommendation: B.**

## WS3: removal outcomes

### 10. An unsettled cleanup step's result field

**Facts.** After an engine has confirmed a copy removed, a later step can fail: the ledger or sidecar delete, SQLite's retained link, or the directory sync. Today the result says `ledger: unsettled` (WS3 question 2).

**Options.**
- **A. Keep `ledger: unsettled`.**
  - It says the wrong thing when the failed step was the link or the sync.
- **B. Name the steps,** for example `unsettled: ["sidecar", "sync"]`, and keep `ledger` for its own step.
  - DataIntent: one field to read.
  - Reversible: no once frozen, but this is before the freeze.

**Recommendation: B.** It is an interface field before the freeze. Naming the step is what a caller needs in order to settle it.

### 11. Copies with an unknown outcome or never reached

**Facts.**
- A sweep that stops lists the copies it removed and kept, but not the copies it never reached.
- A lost reply to a committed `DROP` has no per-copy outcome of its own.
- Exit 8 already says "something may have changed" (WS3 question 5).

**Options.**
- **A. Keep two lists.** Unreached and unknown copies are in neither.
- **B. Add an `unknown` list** for an outcome the command cannot confirm, and an `unreached` list for copies a stopped sweep never reached. The exit codes and the meaning of `removed` and `kept` do not change.
  - DataIntent: two more keys to handle.
  - Reversible: additive.
- **C. As B, but fold them into `kept`.** This changes `kept`'s meaning.

**Recommendation: B.** Every copy then appears exactly once (WS3's R1), with no change to any exit code or existing field.

## WS4: native suite binding

### 12. Authenticating to an unproven listener: security posture

**Facts.** The native suite connects over published TCP ports to containers it checked by ID. A container replaced later could reuse the port. Proving a per-instance marker needs a connection first (WS4 question 4). The credentials are the fixtures' synthetic ones, in an isolated store.

**Options.**
- **A. Yes.** Authenticate, then prove the marker before any write.
  - The fixture's credentials can reach a listener that is not the checked instance.
- **B. No.** Prove the instance through `docker exec` on the checked container ID, and connect over TCP only through a path tied to that ID, such as a port forward created by ID.
  - No credential ever goes to an unproven listener.
- **C. Like B, but for writes only;** reads use plain TCP.

**Recommendation: B.** It is the stricter posture at small cost, since the suite already holds the container ID. The suite is test tooling, but it is the pattern others copy.

## WS5: container and volume lifecycle

### 13. `make down` before slice 3

**Facts.** Slice 3's accepted design ([114-2F]) puts each engine's data on a named volume and makes `down` keep volumes. Until then, the data is in anonymous volumes, and `down` discards the working data, as the README and help now say. This question is only about the interim, and does not reopen [114-2F] (WS5 question 2).

**Options.**
- **A. State it,** as the README and help do, and print one warning line when `down` runs.
  - A person: is told every time.
  - Scripts are unaffected.
- **B. Ask for confirmation on a terminal,** with `--yes` for scripts.
  - A person: one more prompt; scripts must change.
- **C. Refuse without `--discard engine`,** bringing slice 3's flag forward.
  - A person: a new flag that slice 3 then gives a different meaning (`down` keeps data there).

**Recommendation: A.** The behaviour is temporary, and a prompt or flag would be undone or repurposed by slice 3.

### 14. What `status clean` may remove

**Facts.**
- `status clean` removes the containers labelled `megasamples.transient=true`, with their anonymous volumes.
- It also matches some names from before the label existed: build, test and audit containers.
- Those name-only matches are removed today, and their volumes are kept.
- On a shared daemon, such a name could belong to another project.
- The label has existed since 2026-09-04.
- Slice 3's U-5 does not decide this (WS5 question 4).

**Options.**
- **A. The label only.** Name-only matches are listed by `status clean`, with a removal hint, and not removed.
  - A person: an old pre-label container is removed by hand, once.
  - Security posture: no foreign container is touched.
- **B. The label, or a name match whose image is megasamples' own,** such as a `sql-megasamples-*` image.
  - Fewer manual steps.
  - Removes on evidence that a copied image name could fake.
- **C. As today:** name-only matches are removed and their volumes kept.
  - A foreign container is still removed, and its volume left dangling.

**Recommendation: A.** Pre-label containers are rare and old, and removing nothing without the label is the only rule that cannot harm another project.
