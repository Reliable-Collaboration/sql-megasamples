---
type: Dataset
title: Chicago crimes 2001 to present
description: The City of Chicago's 8.6 M-row reported-crime extract plus the 434-row IUCR code lookup; a single year (2024, 259,267 rows) is proposed for the core tier.
resource: https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-Present/ijzp-q8t2
tags:
- tier-core
- tier-extended
- csv
- socrata
- chicago
status: stable
trust: verified
generated:
  by: claude-code/claude-fable-5-1
  at: "2026-09-02T20:30:00Z"
verified:
- by: claude-code/claude-opus-5
  at: "2026-09-03T00:00:00Z"
- by: claude-code/claude-fable-5-1
  at: "2026-09-02T20:30:00Z"
sources:
- resource: https://data.cityofchicago.org/api/views/ijzp-q8t2.json
  title: Socrata view metadata for ijzp-q8t2
  accessed: "2026-09-02"
  version: truth last modified Wed, 02 Sep 2026 11:37:15 GMT; 8,627,693 rows
- resource: /sources/chicago-crimes-socrata-metadata.md
  title: Portal metadata and SODA measurements
  accessed: "2026-09-02"
- resource: /sources/chicago-iucr-codes-dataset.md
  title: IUCR code lookup (c7ck-438e)
  accessed: "2026-09-02"
- resource: https://www.chicago.gov/city/en/narr/foia/data_disclaimer.html
  title: City of Chicago Data Terms of Use
  accessed: "2026-09-02"
stale_after: "2026-12-01"
---

# Identity
"Crimes - 2001 to Present" (`ijzp-q8t2`) on the City of Chicago Data Portal: one row per reported incident (one row per victim for homicides), extracted from the Chicago Police Department's CLEAR system, block-level redacted, excluding the most recent seven days. Database name: **`chicago_crimes`**.

# Source artifact
* **Bulk CSV export:** `https://data.cityofchicago.org/api/views/ijzp-q8t2/rows.csv?accessType=DOWNLOAD` - returns `200`, `Content-Type: text/csv; charset=utf-8`, `Content-disposition: attachment; filename=Crimes_-_2001_to_Present.csv` and **`Content-Length: 0`** (chunked; the size is never advertised). Verified working on 2026-09-02, so the endpoint survived the Socrata -> Tyler "Data & Insights" rebranding; no deprecation notice was found.
* **SODA 2.1 API:** `https://data.cityofchicago.org/resource/ijzp-q8t2.csv` (or `.json`) with `$limit` / `$offset` / `$where` / `$order` / `$select`. A `$limit=50000` request returned `200`. **Always pass `$order=id`** - the export and the default API order are not stable, and `$offset` paging without an explicit order can duplicate and skip rows.
* **Row count on 2026-09-02:** `$select=count(*)` -> **8,627,693**. Grows daily; the portal reports data through "minus the most recent seven days".
* **Size:** no upstream figure. Measured 191.4 bytes/row over the first 15,672 exported rows -> **~1.65 GB** uncompressed for the full export (**inferred**).
* **Lookup:** IUCR codes `https://data.cityofchicago.org/api/views/c7ck-438e/rows.csv?accessType=DOWNLOAD` - **434 rows**.
* **Auth / click-through:** none. An app token is optional for SODA and only raises throttling limits.
* **Checksums:** none published. Record `sha256` plus the row count and `X-SODA2-Truth-Last-Modified` at fetch time - the underlying data changes daily, so a checksum only pins *your* snapshot.

# Built and measured (2026-09-03, core subset)
The 2024 subset loads **259,268** crimes and the **434**-row IUCR lookup in 3.3 s at **75.7 MB** in InnoDB, with 10 smoke queries and 3 plan tests pinned.

**The snapshot moved while this was being built.** Research counted 259,267 rows on 2026-09-02; the fetch on 2026-09-03 returned 259,268, with `X-SODA2-Truth-Last-Modified: Thu, 03 Sep 2026 11:00:44 GMT`. That is the documented behaviour, not an error, and it is why the snapshot's identity is the sha256, the row count and that header together. Until R-02 publishes the subset as a release asset, a rebuild on a later day will legitimately differ.

Two things the plan left conditional are now settled by measurement: `case_number` is **not** unique (259,239 distinct values across 259,268 rows), so it is not a key; and **no crime carries an IUCR code missing from the lookup**, so the foreign key onto `iucr` is declared. 1,744 rows have NULL latitude and longitude, and 259,267 of 259,268 blocks are truncated to the hundred block, which is the address-derivation prohibition visible in the data.

The City's mandatory disclaimer is carried in the generated SQL header **and** in the `crimes` table comment, so it travels with the schema rather than only with a licence file; a smoke test asserts it is there.

# Native format and friendlier forms
Already CSV. The API form is friendlier for a bounded subset: one `$where=year=2024` request stream is 259,267 rows instead of 8.6 million.

# Shape
**`crimes`** - 22 export columns:
`ID`, `Case Number`, `Date`, `Block`, `IUCR`, `Primary Type`, `Description`, `Location Description`, `Arrest`, `Domestic`, `Beat`, `District`, `Ward`, `Community Area`, `FBI Code`, `X Coordinate`, `Y Coordinate`, `Year`, `Updated On`, `Latitude`, `Longitude`, `Location`.

Null counts across all 8,627,693 rows (portal column statistics): `Ward` 614,812; `Community Area` 613,723; `X`/`Y`/`Latitude`/`Longitude` 98,693 each; `Location Description` 16,587; `District` 47; all others 0.

**`iucr`** - 434 rows: `iucr`, `primary_description`, `secondary_description`, `index_code`, `active`.

**Encoding:** `charset=utf-8` in the header, but **no byte above 0x7F appeared in 15,672 sampled export rows**: `Block`, `Description`, `Primary Type` and `Location Description` are upper-case ASCII in practice. `Description` values do contain `/` and `-` (`MANUFACTURE / DELIVER - CRACK`). `utf8mb4` is still the right column charset.

# Conversion path
[DuckDB reader -> typed CSV -> `util.importTable`](/decisions/large-tabular-conversion-path.md). For the **core** subset, the simpler path is a single SODA request with `$where=year=2024&$order=id&$limit=...` written straight to CSV; the IUCR lookup goes in through the DuckDB MySQL extension.

Target DDL: `ID` -> `INT UNSIGNED PRIMARY KEY`; `Case Number` -> `VARCHAR(16)`; `Date`/`Updated On` -> `DATETIME`; `Block` -> `VARCHAR(64)`; `IUCR` -> `CHAR(4)`; `Primary Type`/`Description`/`Location Description` -> `VARCHAR`; `Arrest`/`Domestic` -> `TINYINT(1)`; `Beat` -> `CHAR(4)`; `District` -> `CHAR(3)`; `Ward` -> `TINYINT UNSIGNED NULL`; `Community Area` -> `TINYINT UNSIGNED NULL`; `FBI Code` -> `VARCHAR(3)`; `X`/`Y Coordinate` -> `INT NULL`; `Latitude`/`Longitude` -> `DECIMAL(11,8)`/`DECIMAL(12,8)` NULL; `Location` **dropped** (pure duplication of lat/lon).

# The full archive, as the extended tier (2026-09-03, task X-03)
2001 through 2024 — **8,240,594 rows in `crimes_all`**, taking `chicago_crimes` from 100 MB to
**2,031.9 MB**, appended in 70.8 s. The core `crimes` table (calendar year 2024) stays exactly as it
was and is a strict subset: 259,268 rows on both sides, and **every one of those ids is present in
`crimes_all`**.

Fetched as one CSV per year rather than one 8-million-row request: a year is 40–90 s and ~130 MB that
`fetch.py` can retry and resume, and each year's digest is separately recorded. `$order=id` is
mandatory for stable paging, and `$limit` is set to 600,000 — well above the largest year (486,839 in
2002) — so a file that comes back at exactly the limit means truncation, which the converter checks
for. 2.2 GB of CSV in total; the conversion through DuckDB takes 5 s.

**Hazard 4 is real and does not need routing around.** The SODA CSV output carries `location` with
embedded newlines — each row spans three physical lines, so 2001 is 1,451,731 lines for 485,974 rows.
DuckDB reads them correctly because it is a real CSV parser, and the column is dropped in the
projection since it duplicates latitude and longitude. Asking SODA to omit it with `$select` instead
**triples** the request time (21 s to 67 s for one year), which is worth knowing before reaching for
the obvious fix.

**Hazard 5 confirmed at archive scale**: `id` is unique across all 8,240,594 rows; `case_number` has
8,240,009 distinct values, so 585 are repeats. And every IUCR code in 24 years of data is present in
the current 434-row lookup, so the foreign key is declared rather than omitted — a better result than
expected for a code list that has been revised over two decades.

Null counts, against the portal's own column statistics (which cover the whole archive including
2025–26, so the numbers should be a little lower here and are): `ward` 614,811 of a published
614,812; `community_area` 613,713 of 613,723; coordinates 95,681 of 98,693; `location_description`
14,702 of 16,587; **`district` 47, exactly the published figure** — every one of them predates 2025.

**On drift.** The claim to make carefully: these digests are not guaranteed, because `updated_on`
runs to 2026-09-02, one day before this build, so the portal is still revising historical records.
But over short intervals it is stable, and that was measured rather than assumed — 2024 fetched for
this set came back **byte-identical** to the copy the core dataset had already fetched through a
different `$limit`, and 2001 re-fetched identically ten minutes after its first download. R-02's
release asset is what makes the set verifiable by anyone other than the maintainer.

# Type-mapping hazards
1. **Date format `MM/DD/YYYY hh:mm:ss AM`** in the CSV export (`07/29/2022 03:39:00 AM`) - needs `STR_TO_DATE(x,'%m/%d/%Y %h:%i:%s %p')`, and note `%h` (12-hour) with `%p`, not `%H`. The **SODA API returns ISO-8601 instead** (`2001-01-01T10:40:00.000`), so the two ingest paths need different parsers. Both are naive local times with no timezone.
2. **Leading-zero identifiers**: `Beat` = `0733`, `District` = `007`, `IUCR` = `0110`, `FBI Code` = `01A`. All must be strings; `FBI Code` is not even numeric.
3. **Booleans arrive as the literals `true`/`false`** in the export - `LOAD DATA` into a `TINYINT(1)` silently stores 0 for both unless converted.
4. **`Location` contains embedded newlines in the SODA CSV output** (the value spans three lines) though not in the `rows.csv` export. Dropping the column sidesteps this; if kept, the parser must handle multi-line quoted fields.
5. **`Case Number` is NOT unique** - 8,627,693 rows but only **8,627,064 distinct** values (verified). `ID` is unique and is the documented "Unique identifier for the record". Do not make `Case Number` a key.
6. **Empty coordinates** on 98,693 rows; `Location` is empty on the same rows.
7. **The export is not ordered by `ID`** and its order is not stable between requests.
8. **`Ward` and `Community Area` are typed differently by the portal** (`ward` number, `community_area` text) despite both being small integers; `community_area` may be an empty string rather than null in some vintages.
9. The eight `:@computed_region_*` columns exist in the view but not in `rows.csv` - do not build DDL from the view metadata.

# Programmable objects
None upstream. This project adds a view `v_crime_iucr` joining `crimes` to `iucr` (showing that `Primary Type`/`Description` are denormalised copies of the lookup - a good normalisation lesson), `SQL SECURITY INVOKER`. No procedures/triggers. The three referenced boundary datasets (Community Areas `cauq-8yn6`, Police Beats `aerh-rz74`, Police Districts `fthy-xz3r`) are **shapefile/KML only, with no tabular columns**, so no geography tables are created.

# Indexing
* `PRIMARY KEY (ID)` - the only true natural key.
* `KEY (Date)` - every temporal query.
* `KEY (IUCR)` - FK-like into `iucr.iucr`; a real `FOREIGN KEY` is plausible but **Inferred:** historical rows may carry retired IUCR codes absent from the current 434-row lookup, so verify with a left-join count before declaring it.
* `KEY (Primary Type)` (~35 distinct values, still useful for the classic `GROUP BY` demo), `KEY (Arrest)` skipped as too low-cardinality.
* `KEY (Beat)`, `KEY (District)`, `KEY (Community Area)` for the geography drill-downs.
* No unique index on `Case Number` (proven non-unique).

# Tests and expected values
* Core subset: `SELECT COUNT(*) FROM crimes` -> **259,267** for `year = 2024` (verified count on 2026-09-02; it can still change because CPD amends old records, so the executor records the count and the fetch date together).
* `SELECT COUNT(*) FROM iucr` -> **434**.
* `SELECT COUNT(*) FROM crimes WHERE latitude IS NULL` -> non-zero (proves hazard 6 survived the load).
* `SELECT COUNT(DISTINCT id) = COUNT(*)` -> true.
* Full extract (extended): 8,627,693 rows as of 2026-09-02 - a moving target, so the test asserts a floor rather than equality.

# Tier assignment
* **Core: calendar year 2024, 259,267 rows** (2023 = 263,449 and 2025 = 237,695 are equally usable). **Inferred:** ~50 MB uncompressed CSV and roughly **60-90 MB** as an InnoDB table with six secondary indexes - at or slightly over the strict 50 MB line but inside the "medium core" allowance in [the tier model](/decisions/tier-model.md), and it is the single most recognisable public dataset in the whole image. If the budget bites, drop to a half-year. The 434-row `iucr` table ships with it unconditionally.
* **Extended: the full 2001-present extract.** ~1.65 GB of CSV, 8.6 M rows; `make load-chicago_crimes` streams the export.

# License and attribution
[Chicago data portal terms](/licenses/chicago-data-portal-terms.md). Redistribution is permitted; the **mandatory disclaimer** paragraph must be reproduced verbatim in the README and image documentation, together with the CPD's own accuracy disclaimer and the prohibition on deriving specific addresses. The user also accepts an indemnity, and the City may demand that distribution stop.

# Open questions
* Whether every `IUCR` value in the loaded subset exists in the 434-row lookup (one left join).
* Whether the 2024 subset stays at 259,267 rows between builds - CPD revises history, so the test should assert a tolerance rather than an exact equality. Cheapest check: re-run the `$select=count(*)&$where=year=2024` query at build time and compare with the manifest.

# Snapshot re-pinned (2026-09-10)
The portal's 2024 extract grew between 2026-09-03 and 2026-09-09: 74,811,578 bytes (259,267 rows)
became 74,885,948 bytes (sha256 `5e67e3861a76…`, 259,607 rows), the city having amended the year.
No release asset mirrors the earlier bytes -- the project publishes only the repository -- so the
manifest and every expectation (counts, digests, views, smoke results) now pin the 2026-09-09
extract, verified on MySQL with 0 failures and re-ported. The next amendment fails the digest
check by design; `MEGASAMPLES_ACCEPT_DRIFT=1` accepts the newer bytes, re-pins the manifest, and
`megasamples verify chicago_crimes --pin` moves the expectations after the MySQL build.

# A live feed, by decision (2026-09-17)
The extract served on 2026-09-16 was 74,888,189 bytes, 2,241 more than the 2026-09-09 snapshot,
and a clean-room build from GitHub stopped on it. The maintainer decided the data should evolve:
a build takes what the portal serves that day, the tests describe the 2026-09-09 snapshot and
hold a build to floors and structure, and nothing is mirrored ([the decision](/decisions/live-artifacts.md)).
