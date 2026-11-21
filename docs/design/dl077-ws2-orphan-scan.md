# Workstream 2: completeness of the PostgreSQL orphan scan (DL-119)

**Status:** brief, not yet built. The area went hot in review rounds 3, 4 and 5 (`tests/dl077-v1-loop.md`).

The scan is DL-119's detective control. It reports each data directory with no database, through `megasamples up` and `reset --status postgres`.

## The rule to be designed whole

The scan answers `complete` only when it has observed, from one data directory of one server instance, every directory that could hold a database and the catalog it is compared with. Otherwise it answers `incomplete`. Never `complete` with a gap, and never a traceback.

## Invariants

- **O1. One instance.** Every observation in one scan comes from the same container instance, the same server process and the same volume. A replacement or a restart during the scan, even under the same container ID, makes it `incomplete`.
- **O2. Every location inspected or reported.** Each location PostgreSQL could place a database directory in is either listed successfully or reported unreadable:
  - `base/`;
  - every tablespace in the catalog;
  - every link under `pg_tblspc`.

  Crediting a location requires a successful listing of it.
- **O3. Ordering is stated.** The directories are read before the catalog. A directory whose database is being created or dropped can appear once. A rerun settles it, and the README's removal route starts by stopping both.
- **O4. Each observation is checked.** Every command's exit status and output shape is checked, and a malformed or failed observation makes the scan `incomplete`.
- **O5. Read only.** The scan changes nothing.

## Decision table

| Fact | Values |
|---|---|
| A. Container | the same instance throughout; replaced between reads; restarted under the same ID (a new postmaster); gone |
| B. `base/` | listable; searchable but not listable; missing |
| C. Each entry under `base/` | a numeric directory; non-numeric; removed during the scan; present but unmeasurable |
| D0. `pg_tblspc` itself | listable; not listable |
| D. Each `pg_tblspc` link | resolves and is listable; dangling; resolves, not listable; its `PG_*` directory missing or unreadable |
| E. Each catalogued tablespace | has a link; has none |
| E2. Each `pg_tblspc` link | has a catalog row; has none |
| F. Each observation (listing, `pg_database`, `pg_tablespace`) | succeeds; fails; returns nothing; returns malformed output; times out (300 s for the listing) |
| G. A database | created or dropped during the scan; **invalid after an interrupted drop** (PostgreSQL 15+: the row stays with `datconnlimit = -2`, its directory partly removed); neither |

The outcomes to decide are `complete` with these warnings, or `incomplete` with this reason.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 1 | S4 | a copy owner's statement timeout or cancel during `copy`'s `CREATE DATABASE` may leave a directory with no catalog row | handled as DL-113 says: 480 caller interrupts left none, and every committed copy was closed; a planted `base/424242` is reported (`h3-interrupts-control.log`); not a proof that the window is closed. That return to the deciders was DL-113's disposition, now historical: DL-119, the later decision, accepts this cancel-or-timeout leftover as a stated limit with the detective control (the next row), and is the current rule for it |
| 2 | S2-3 | the same cancel or timeout at the commit boundary | **decided by DL-119**: a stated limit, with the detective control in `up` and `reset --status postgres`, the README's removal route, the planted-orphan test and the 480-attempt regression |
| 3 | S3-2, O3-5 | a concurrent drop crashed the parser; the tablespace path lacked `PG_*` | fixed |
| 4 | S4-3 | a dangling or unlistable tablespace, or partial `du` output, gave `complete` | fixed |
| 4 | O4-3 | the concurrent-drop test matched text | fixed: behaviour test |
| 5 | Sol P2-4 | `base/` searchable but unreadable: no rows, and `pg_default` credited | **input** |
| 5 | Sol P2-5 | the container replaced between the listing and the catalog: two volumes mixed | **input** |
| 6 | Sol P2-3 (S6-3) | add the smallest stopgap that reports `incomplete` for S5-4 and S5-5, because DL-119 relies on the scan to disclose a gap | **input**, with **no stopgap**: the coordinator's round 6 decision (`tests/dl077-v1-loop.md`, "Round 6: stopgaps"). It reopens with a supported caller acting on `complete` without the README's removal route |
| 6 | Sol P2-7 | a restart under the same container ID; `pg_tblspc` not listable; malformed or empty results per observation; faults between reads | **input** (facts A, D0, F; question 6; test plan) |
| 6 | Opus 5 | an invalid database after an interrupted drop; a link with no catalog row; timeouts; faults at each read | **input** (facts E2, F, G; question 5; test plan) |
| 7 | Sol 2 | the basic warning cannot be derived: no fact says whether a directory's OID has a catalog row; an empty location is not told apart from missing output; round 1 S4 and round 2 S2-3 not named | **input**: the directory-to-catalog match for `base/` and tablespaces; empty versus missing; both CLI routes asserted; a different leftover class names its warning and whether the README's removal route applies. Round 1 S4 and round 2 S2-3 are now their own rows above |
| 8 | Sol P3-6 | the S4 and S2-3 cases and their dispositions (the planted orphan, the reporting in `up` and `reset --status`, the removal route) were not carried | **input**: both rows added; the design keeps each disposition or says why it changes |
| 9 | Sol P3-7, Opus N2 | round 6 S6-3 was not in these inputs; the S4 row lacked two parts of its disposition | **input**: the S6-3 row; the S4 row now carries the closed copies and the return to the deciders |
| 10 | Sol P3-7 (S10-P3-7) | the S4 row gave DL-113's escalation as current beside the S2-3 row's DL-119 rule for the same cancel-or-timeout case | **input**: the S4 row marks DL-113's escalation historical, and the S2-3 row's DL-119 disposition is the current rule |
| 11 | Sol P3-11 | the round 10 finding was not in this table | **input**: the row above |

## Questions the design must answer

1. How is the instance pinned? By container ID, with a check that the ID still runs after the last read, or with an in-container marker the scan reads first and last?
2. Is the listing done by one script that reports each location's own status, so that Python credits only what was positively listed?
3. Should `reset --status` exit non-zero when the scan is `incomplete`? It is 0 today, per design 3.5a. **Owner decision:** it is a contract for supervisors.
4. **Owner decision:** does `up` ever block or fail on an incomplete scan, or only warn? Are partial warnings shown when incomplete? It only warns today, and an incomplete scan shows no directory.
5. **Owner decision:** is an invalid database (an interrupted drop) reported, and how: as its own warning code, as an orphan, or not at all? It is the drop-side twin of DL-119's create window.
6. How does a restart under the same container ID get detected? By the postmaster start time (`pg_postmaster_start_time()`) read first and last, or by the container's start time?

## Test plan

- **A model test:** a fake filesystem and catalog generated from the decision table, run through the real listing script under `sh` with shims for `du`, `ls` and permissions, and the real parser. Every combination of A to G is asserted.
- **Native rows:**
  - `base/` made unlistable;
  - a tablespace made unreadable;
  - a dangling link;
  - a container replaced between reads, by stopping it and starting another under the same name, via a fault hook between the listing and the catalog read.
- **Fault planting at each observation step,** and between every pair of reads and at the final identity check: failure, empty output, malformed output and timeout. Both CLI outputs are asserted (`up`'s warning and `reset --status`'s document).
- **Carried regressions:** S2-3 and DL-119's 480-attempt run, and the S3-7/S4-9 accounting limit of the H-3 probe's control.
- **Reversals:** each crediting rule removed fails a row.
