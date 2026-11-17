---
type: Tool
title: Python conversion stack
description: Pinned Python packages for converters, verifiers and generators, chosen for permissive licenses and MySQL 9.7 compatibility.
resource: /tools/python-conversion-stack.md
tags:
- python
- tools
- licenses
status: stable
trust: verified
stale_after: "2026-12-01"
generated:
  by: claude-code/claude-fable-5-1
  at: "2026-09-02T21:00:18Z"
verified:
- by: claude-code/claude-fable-5-1
  at: "2026-09-02T21:00:18Z"
sources:
- resource: /sources/pypi-pymysql.md
  accessed: "2026-09-02"
- resource: /sources/pypi-sqlglot.md
  accessed: "2026-09-02"
- resource: /sources/pypi-pyarrow.md
  accessed: "2026-09-02"
- resource: /sources/pypi-lxml.md
  accessed: "2026-09-02"
- resource: /sources/pypi-duckdb.md
  accessed: "2026-09-02"
- resource: /sources/mysql-connector-python-preface.md
  accessed: "2026-09-02"
- resource: /sources/build-machine-environment-2026-09-02.md
  accessed: "2026-09-02"
---

# Facts

This dated package table is historical. The current project pins are in repository-root `pyproject.toml`, `uv.lock` and `clients.lock.yaml`; current validation is in `docs/client-upgrade-evidence.md`. `pyarrow` and `mwxml` are knowledge-only references, not current project dependencies. Architecture claims below are historical; current execution coverage is recorded in that receipt.

| Package | Version (2026-09-02) | License | Role |
|---|---|---|---|
| Python | 3.14.4 on the build host; container image `python:3.13-slim` (**Inferred** availability; 3.13 chosen because pyarrow supports 3.10–3.14 and 3.13 is the most widely packaged) | PSF | runtime |
| `uv` | 0.12.6 on host | Apache-2.0/MIT (**Inferred**, not read) | env + lockfile (`uv.lock` committed) |
| `PyMySQL[rsa]` | 1.2.0 | MIT | client for verify.py and loaders; `[rsa]` extra is required for `caching_sha2_password` ([PyPI](/sources/pypi-pymysql.md)) |
| `duckdb` | see [PyPI duckdb](/sources/pypi-duckdb.md) | MIT | Parquet/CSV normalisation, TPC-H/TPC-DS generators ([DuckDB record](/tools/duckdb.md)) |
| `pyarrow` | 25.0.1 | Apache-2.0 | Parquet footer/schema inspection only (DuckDB does the heavy lifting) |
| `lxml` | 6.1.3 | [BSD-3-Clause](/licenses/bsd-3-clause.md) | Stack Exchange XML (`iterparse`), AdventureWorks XML columns validation |
| `sqlglot` | 30.17.0 | MIT | first-pass DDL/query transpilation T-SQL/Oracle → MySQL for TPC-DS queries and AdventureWorks views; output is always reviewed and tested because "SQLGlot is a transpiler, not a validator" ([PyPI](/sources/pypi-sqlglot.md)). **Statements only.** Tried on routine bodies at V-02 and rejected on evidence: given AdventureWorks' twelve-line `ufnGetStock` it dropped the `RETURNS int` type, turned `IF (@ret IS NULL) SET @ret = 0` into an empty string, and parsed `RETURN @ret` as a column alias — printing `Unsupported If block syntax` and emitting output anyway. `megasamples/sources/tsqlbody.py` does routine bodies instead |
| `mwxml` | 0.3.8 (see [mediawiki parsing](/tools/mediawiki-xml-dump-parsing.md)) | MIT | Wikipedia XML |
| `PyYAML` | latest | MIT (**Inferred**, not read) | manifest and test files |

Rejected: `mysql-connector-python` — its software license was not confirmed this session (the manual preface only covers the documentation, [record](/sources/mysql-connector-python-preface.md)); PyMySQL covers every need.

# Limits
* No host installs beyond `uv`-managed virtualenvs (already present); everything else runs in the `loader` image.
* Converters are pure Python + DuckDB; no compiled extensions beyond the wheels above, so arm64 builds work.
