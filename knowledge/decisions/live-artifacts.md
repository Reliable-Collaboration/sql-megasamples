---
type: Decision
title: "A live feed is taken as served: its dataset's tests describe a snapshot, and hold a build to floors and structure"
description: The maintainer's decision of 2026-09-17 for artifacts whose upstream changes (chicago_crimes, a query against the city's portal) -- a build downloads what the feed serves that day, records what it got and never re-pins; the dataset's tests are floors and structure rather than a snapshot's bytes; nothing is mirrored, so the repository stays small and bakes in no stale data.
resource: /decisions/live-artifacts.md
tags:
- decision
- downloads
- chicago
- verification
status: stable
trust: verified
generated:
  by: claude-code/claude-fable-5-1
  at: "2026-09-17T04:30:00Z"
verified:
- by: claude-code/claude-fable-5-1
  at: "2026-09-17T04:30:00Z"
sources:
- resource: /datasets/chicago-crimes.md
  title: The dataset record, with the drift observed on 2026-09-03 and 2026-09-09
- resource: /decisions/no-release-assets.md
  title: The decision this one keeps -- nothing is mirrored
- resource: /licenses/chicago-data-portal-terms.md
  title: The portal's terms, which permit reuse with the verbatim disclaimer
---

# Question

A clean-room build of the corpus from GitHub on 2026-09-16 stopped on `chicago_crimes`: the city's 2024 extract no longer matched the size and digest the manifest pinned (74,888,189 bytes served against 74,885,948 pinned). The pin had already moved once, on 2026-09-10, and the README told a reader to accept the drift by hand and re-pin every expectation. Every fresh machine would meet the same stop on the city's schedule. What should a build do with an artifact whose upstream is a live feed?

# Options considered

* **Keep pinning the bytes and accept drift by hand** (the state before). Lost: every fresh build fails until a human decides; the documented numbers move with each acceptance; "verified" comes to mean "as of whenever you built it".
* **Mirror a snapshot as a release asset and list it under `mirrors`**, which the fetch already supports. Lost: the repository grows by 75 MB per snapshot and bakes in data that goes stale; the maintainer's words: "We want the data to evolve, someone running the default settings should download the latest and use that. This keeps our repo smaller, and doesn't bake in stale data."
* **Take the feed as served, and make the tests describe a snapshot rather than pin it.** Chosen.

# Evidence

The city amends past years (the record above: 259,267 rows on 2026-09-02, 259,268 on 2026-09-03, 259,607 on 2026-09-09; the extract served on 2026-09-16 was 2,241 bytes larger again). A short or truncated download shows as a row count below the snapshot's, which a floor catches; a schema change shows in the structural stages, which are held exactly. The ports are checked against the hub on the same machine, so the three engines still hold the same rows.

# Outcome

* `manifest.yaml`: `live: true` on the 26 `chicago_crimes/` artifacts. `megasamples/fetch.py` takes what a live feed serves, records the observed digest and size in the marker and the `.meta.json`, never rewrites the manifest (whose `sha256` and `size_bytes` now describe the snapshot the tests were written against), keeps what a machine fetched once, and fetches again under `MEGASAMPLES_REFRESH_LIVE=1`.
* `datasets/chicago_crimes/dataset.yaml` and `chicago_crimes_full/dataset.yaml`: `live: true`. `megasamples/verify.py` holds a live dataset to floors on counts, to column sets on the content digests of tables and views, runs the smoke queries without comparing their results, and holds everything structural exactly.
* The catalogue and the README's databases table say which dataset is a live feed; the README's downloads section says what a build does with it.
* `tests/test_fetch.py`: a live artifact is taken as served, kept, and refetched on request; and the progress line of a fetched job, which crashed every worker on a fresh clone until 2026-09-16 (`fix/fetch-start-time`).

# Status

accepted (2026-09-17; the maintainer's decision, quoted above).
