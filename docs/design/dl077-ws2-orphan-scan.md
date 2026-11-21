# Workstream 2: completeness of the PostgreSQL orphan scan (DL-119)

**Status:** brief, not yet built. The area went hot in review rounds 3, 4 and 5 (`tests/dl077-v1-loop.md`).

The scan is DL-119's detective control. It reports each data directory with no database, through `megasamples up` and `reset --status postgres`.

## The rule to be designed whole

The scan answers `complete` only when it has observed, from one data directory of one server instance, every directory that could hold a database and the catalog it is compared with. Otherwise it answers `incomplete`. Never `complete` with a gap, and never a traceback.

## Invariants

- **O1. One instance.** Every observation in one scan comes from the same container instance and the same volume. A replacement during the scan makes it `incomplete`.
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
| A. Container | the same instance throughout; replaced between reads; gone |
| B. `base/` | listable; searchable but not listable; missing |
| C. Each entry under `base/` | a numeric directory; non-numeric; removed during the scan; present but unmeasurable |
| D. Each `pg_tblspc` link | resolves and is listable; dangling; resolves, not listable; its `PG_*` directory missing or unreadable |
| E. Each catalogued tablespace | has a link; has none |
| F. Catalog read | succeeds; fails; returns nothing |
| G. A database | created or dropped during the scan; neither |

The outcomes to decide are `complete` with these warnings, or `incomplete` with this reason.

## Inputs: every finding so far

| Round | Finding | Gist | Disposition so far |
|---|---|---|---|
| 3 | S3-2, O3-5 | a concurrent drop crashed the parser; the tablespace path lacked `PG_*` | fixed |
| 4 | S4-3 | a dangling or unlistable tablespace, or partial `du` output, gave `complete` | fixed |
| 4 | O4-3 | the concurrent-drop test matched text | fixed: behaviour test |
| 5 | Sol P2-4 | `base/` searchable but unreadable: no rows, and `pg_default` credited | **input** |
| 5 | Sol P2-5 | the container replaced between the listing and the catalog: two volumes mixed | **input** |

## Questions the design must answer

1. How is the instance pinned? By container ID, with a check that the ID still runs after the last read, or with an in-container marker the scan reads first and last?
2. Is the listing done by one script that reports each location's own status, so that Python credits only what was positively listed?
3. Should `reset --status` exit non-zero when the scan is `incomplete`? It is 0 today, per design 3.5a. **Owner decision:** it is a contract for supervisors.
4. Does `up` ever block or fail on an incomplete scan, or only warn? It only warns today.

## Test plan

- **A model test:** a fake filesystem and catalog generated from the decision table, run through the real listing script under `sh` with shims for `du`, `ls` and permissions, and the real parser. Every combination of A to G is asserted.
- **Native rows:**
  - `base/` made unlistable;
  - a tablespace made unreadable;
  - a dangling link;
  - a container replaced between reads, by stopping it and starting another under the same name, via a fault hook between the listing and the catalog read.
- **Reversals:** each crediting rule removed fails a row.
