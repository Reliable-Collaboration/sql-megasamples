---
type: Dataset
title: Enron email corpus (CMU, May 7, 2015 version)
description: About 517k real corporate emails from 150 Enron custodians, distributed by CMU as a maildir-style tree of RFC 822 files; converted to messages/recipients/mailbox tables with FULLTEXT.
resource: https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz
tags:
- tier-core
- tier-extended
- dataset
- text-corpus
- email
- personal-data
- public-record
- text-group
status: stable
trust: verified
generated:
  by: claude-code/claude-fable-5-1
  at: "2026-09-02T20:25:00Z"
verified:
- by: claude-code/claude-opus-5
  at: "2026-09-03T00:00:00Z"
- by: claude-code/claude-fable-5-1
  at: "2026-09-02T20:25:00Z"
stale_after: "2027-09-01"
sources:
- resource: https://www.cs.cmu.edu/~enron/
  title: Enron Email Dataset (CMU)
  accessed: "2026-09-02"
  version: May 7, 2015
- resource: https://www.cs.cmu.edu/~enron/DELETIONS.txt
  title: DELETIONS.txt
  accessed: "2026-09-02"
- resource: https://raw.githubusercontent.com/lintool/Enron2mbox/master/README.md
  title: Enron2mbox README
  accessed: "2026-09-02"
- resource: https://raw.githubusercontent.com/angel-hernandez91/enron-emails/master/README.md
  title: enron-emails README
  accessed: "2026-09-02"
- resource: https://www.ah-ruhe.de/enron-email-data/
  title: repaired Shetty/Adibi MySQL dump page
  accessed: "2026-09-02"
- resource: https://raw.githubusercontent.com/enrondata/enrondata/master/edrm-v2.0.0/README.md
  title: EDRM v2 README
  accessed: "2026-09-02"
- resource: https://enrondata.readthedocs.io/en/latest/data/edrm-enron-email-datasets/
  title: EnronData.org EDRM page
  accessed: "2026-09-02"
---

# Identity
Enron Email Dataset, "May 7, 2015 Version", prepared by the CALO project (SRI) and distributed by William W. Cohen at CMU ([source](/sources/cmu-enron-email-dataset-page.md)). Proposed MySQL database name: **`enron`**.

# Source artifact
* URL: https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz — `tar.gz`; observed `Content-Length: 443254787` (443.3 MB / 422.7 MiB), `Last-Modified: Thu, 07 May 2015 20:35:29 GMT`. The page text says "about 1.7Gb, tarred and gzipped", which does not match the download; **Inferred:** 1.7 GB is the extracted size (a third-party README reports a 1.4 GB `maildir`).
* No auth, no click-through. **No checksum is published** anywhere on the page; the executor computes and pins `sha256` on first download ([open question](/questions/enron-tarball-checksum-and-message-count.md)).
* Older versions (2004, 2009, 2011) are withdrawn and "you are requested to replace it with the newer version" — never build from them; the 2015 version already excludes the 30 files listed in [DELETIONS.txt](/sources/cmu-enron-deletions-txt.md).
* Known other versions, not used: (a) ISI/USC Shetty and Adibi 2004 MySQL dump — page offline (Cloudflare 403; a 2013 Wayback snapshot exists, [evidence](/sources/wayback-isi-adibi-enron-availability.md)); a "repaired" copy of that MySQL 4 dump (tables `employeelist`, `message`, `recipientinfo`, `referenceinfo`) is redistributed at [ah-ruhe.de](/sources/ah-ruhe-enron-email-data.md) without a license statement; (b) EDRM/ZL "Enron Email Data Set v2" — PST/MIME/EDRM XML **with attachments**, 149 custodians, 79 GB on [archive.org](/sources/archive-org-edrm-enron-v2-xml-metadata.md); EDRM withdrew v1/v2 for remaining PII ([EnronData.org](/sources/enrondata-readthedocs-edrm-datasets.md)). We use CMU: smallest, attachment-free, has the removal history.

# Built and measured (2026-09-03)
The tarball is **443,254,787 bytes**, sha256 `b3da1b3fe0369ec3140bb4fbce94702c33b7da810ec15d718b3fadf5cd748ca7` (CMU publishes none), holding **517,401 message files in 150 mailboxes** — confirming the two third-party counts — and **1,421,183,736** uncompressed message bytes, which supports the record's inference that the page's "about 1.7Gb" is the extracted tree rather than the download. None of the `DELETIONS.txt` paths is present, and the converter asserts that on every build.

**The tar's member order is not alphabetical**, so the subset rule cannot be applied by reading until full: the converter takes the member list in one streaming pass, chooses from it, and reads the chosen members in a second pass. Neither pass extracts the archive.

**Core subset as built**: the alphabetically first mailboxes under 40 MB are `allen-p`, `arnold-j`, `arora-h`, `badeer-r`, `bailey-s` — 5 of 150, 23,750,767 bytes, **9,941 messages and 38,832 recipients**, loading in 4.4 s at **36.5 MB** in InnoDB.

**The corpus is much cleaner than expected.** Parsing all 517,401 messages (not a sample): **0** bodies need the cp1252 fallback, **0** messages lack a `Date` or carry an unparseable one, and **0** `Message-ID` values repeat across 517,401 distinct ones. Only 30 messages carry any `email` header defect. Declared charsets are `us-ascii` (479,286), `ansi_x3.4-1968` (38,086 — an ASCII alias) and absent (29). Because uniqueness was measured rather than assumed, `message` declares `UNIQUE(message_id)`, which the plan had deferred. See the [header question](/questions/enron-header-anomalies-charset-dates-message-id.md) and the [checksum question](/questions/enron-tarball-checksum-and-message-count.md), both now answered.

# Native format and friendlier forms
A directory tree `maildir/<custodian>/<folder>/<n>.`, one RFC 822 message per file, no attachments (CMU page). It is not a real Maildir (no `cur/new`), so Python's `mailbox` module needs restructuring; a plain file walk + `email.parser` is simpler ([tool](/tools/text-enron-maildir-parsing.md)). CMU publishes no CSV/SQL form.

# Shape
* 150 custodian directories (CMU: "about 150 users"); **517,401 message files** (two independent third-party counts: [Enron2mbox](/sources/github-lintool-enron2mbox-readme.md), [enron-emails](/sources/github-angel-hernandez91-enron-emails-readme.md)); ~3,311 custodian/folder combinations (Enron2mbox mbox count).
* Proposed tables (all utf8mb4):
  * `mailbox(mailbox_id SMALLINT PK, name VARCHAR(64) UNIQUE)` — 150 rows.
  * `message(id INT PK, mailbox_id, folder VARCHAR(255), path VARCHAR(255) UNIQUE, message_id VARCHAR(255), date_utc DATETIME NULL, date_raw VARCHAR(64), from_address VARCHAR(255), from_raw VARCHAR(1000), subject TEXT, body MEDIUMTEXT, body_sha1 CHAR(40), x_from/x_to/x_cc/x_bcc TEXT, x_folder VARCHAR(255), x_origin VARCHAR(64), x_filename VARCHAR(255), charset_fallback TINYINT, header_defects SMALLINT)` — 517,401 rows.
  * `recipient(message_id INT, kind ENUM('to','cc','bcc'), position SMALLINT, address VARCHAR(255), display_name VARCHAR(255))` — row count unknown; **Inferred:** 2-4 million (executor derives).
  * Optional `address(address VARCHAR(255) PK, is_enron BOOL)` lookup — enron-emails reports 83% of mail from Enron addresses.
* Encoding: files are predominantly 7-bit ASCII (enron-emails README); **Inferred:** a minority carry Latin-1/Windows-1252 bytes and quoted-printable; decode per declared charset, fall back to cp1252, flag the row ([question](/questions/enron-header-anomalies-charset-dates-message-id.md)). Non-ASCII content is therefore sparse — the encoding test is "no U+FFFD in bodies unless `charset_fallback=1`".

# Conversion path
Custom Python loader (`email` stdlib → TSV → `LOAD DATA LOCAL INFILE`), deterministic path order; see [decision](/decisions/enron-conversion-path.md) and [tool](/tools/text-enron-maildir-parsing.md). No off-the-shelf MySQL converter with a known license was found (ah-ruhe.de dump has none; converters on GitHub target SQLite/Mongo/Postgres).

# Upgrade coverage, 2026-11-16

The full corpus exceeds PostgreSQL's native full-text vector size for at least one message: the
isolated port observed 1,491,766 bytes against a 1,048,575-byte maximum. PostgreSQL's
[documented limits](https://www.postgresql.org/docs/18/textsearch-limitations.html), read
2026-11-16 20:45:06 UTC, confirm this restriction. The upgrade candidate records
`enron_full.message.ft_message` as unsupported on PostgreSQL; it preserves every message body
and its original count/checksum expectations. Core Enron, MySQL FULLTEXT and SQLite FTS5 keep
their indexes. The exception appears by name in generated port records and the image registry.

# Type-mapping hazards
* `Date` headers carry numeric offsets with zone comments like `-0700 (PDT)` (**Inferred**); store UTC `DATETIME` plus `date_raw`; a handful of bogus years (1979/1980/2044) are expected — keep them, do not coerce (**Inferred**).
* **Upgrade verification, 2026-11-16:** the original converter used the host timezone, and the shipped fingerprints and date-range expectations contain America/Chicago wall times despite the legacy `date_utc` name. The converter now chooses that zone explicitly, including daylight saving and offset-free headers, preserving the existing corpus on hosts configured for UTC. `date_raw` retains the source header. The earlier UTC description above was an inference, not the shipped behavior.
* Recipient lists can run to thousands of addresses on broadcast mails; hence the child table rather than a `to` column.
* `subject` may exceed 255 chars → `TEXT`. `message_id` is not declared UNIQUE until uniqueness is verified.
* FULLTEXT on `message.subject, message.body` (InnoDB): build after load; `innodb_ft_min_token_size=3` default drops 1-2 letter tokens; document.
* CMU's placeholder addresses `user@enron.com` / `no_address@enron.com` are data, not errors.

# Programmable objects
None upstream. We add read-only views: `v_message_with_recipients` (`JSON_ARRAYAGG` of the `to` addresses — **not** `GROUP_CONCAT`, which silently truncates at `group_concat_max_len` = 1024 bytes and would cut exactly the broadcast mails this record calls out; the same reason it was rejected for checksums, see [checksum method](/decisions/test-checksum-method.md)), `v_mailbox_folder_counts`. No triggers/procedures.

# Indexing
PK `message.id`; `UNIQUE(path)`; `INDEX(mailbox_id, folder)`; `INDEX(date_utc)`; `INDEX(from_address)`; `INDEX(body_sha1)`; `FULLTEXT(subject, body)`; `recipient`: `PK(message_id, kind, position)`, `INDEX(address)`.

# Tests and expected values
* `COUNT(*) FROM mailbox` = 150; `COUNT(*) FROM message` = number of files under `maildir/` (expected 517,401; the executor records the actual `find maildir -type f | wc -l`).
* `SELECT COUNT(*) FROM message WHERE path IN ('richey-c/inbox/10.','skilling-j/1584.','gay-r/sent/12.')` = 0 (deleted files must be absent).
* `message.path='allen-p/inbox/1.'` exists (**Inferred:** first custodian alphabetically).
* Checksum of the tarball equals the pinned sha256 from the first build.

# The full corpus (2026-09-04, task X-05)
All 150 mailboxes in their own database, `enron_full`: **517,401 messages and 4,254,342 recipients,
2,373.8 MB in InnoDB**, loading in 129 s. The core `enron` stays as it was -- five mailboxes under
40 MB -- because it is baked into the image. Same schema, more rows, so a separate database rather
than an append.

**The header-anomaly question, answered over the whole corpus rather than five mailboxes**:
**0** messages need the cp1252 fallback, **0** have an unparseable `Date`, **0** `Message-ID` values
repeat -- all 517,401 are distinct, so the `UNIQUE(message_id)` this record declares holds at full
scale. 30 messages carry a header defect that `email` reports.

Two things measured here that the five-mailbox subset could not show:

* **`compat32` does not always return a string.** For a header carrying an encoded word or raw 8-bit
  bytes it returns an `email.header.Header` instead, and the corpus has them. None of the five core
  mailboxes does, so this surfaced only as an `AttributeError` on `.replace` deep inside recipient
  parsing. Every header now goes through one coercion.
* **Every message's Cc and Bcc address sets are identical** -- 0 exceptions in 517,401 messages, and
  the counts match exactly at 562,364 each. That is a property of how CMU assembled the corpus, not
  of the conversion, and it is worth knowing before anyone reads meaning into the Bcc column.

**Dates run from 1979-12-31 to 2044-01-04**, and the raw headers say so: the 1979 rows carry
`Mon, 31 Dec 1979 16:00:00 -0800 (PST)` verbatim. 1,042 of 517,401 messages fall outside 1998-2002.
The record's "a few bogus years" is now a number. Largest mailboxes: kaminski-v 28,465,
dasovich-j 28,234, kean-s 25,351.

# Tier assignment
* Full corpus: **extended**. Evidence: 443 MB compressed download, ~1.4 GB extracted text ([enron-sqlite3 README](/sources/github-ftrain-enron-sqlite3-readme.md) reports a ~5 GB SQLite with FTS); **Inferred:** 2-3 GB in InnoDB with FULLTEXT.
* Core option: a deterministic subset — e.g. the alphabetically first mailboxes whose cumulative extracted size stays under 40 MB — shipped as `enron` in the image, with the full corpus loadable at start via the same loader. Average mailbox ≈ 1.4 GB / 150 ≈ 9 MB (**Inferred**), so 3-5 mailboxes fit.

# License and attribution
[Enron public record](/licenses/enron-public-record.md) — no license text exists; FERC public record redistributed by CMU with a privacy request. README wording: "Enron Email Dataset (May 7, 2015 version), collected and prepared by the CALO Project (SRI International) and distributed by William W. Cohen, Carnegie Mellon University, https://www.cs.cmu.edu/~enron/. Originally made public by the U.S. Federal Energy Regulatory Commission. No license is stated; the data contains personal information of real people; please be sensitive to their privacy. Attachments are not included. Messages removed at the request of affected employees (see DELETIONS.txt) are not present. Provenance caveat: 2026 reports question the authenticity of some messages ([Zenodo](/sources/zenodo-nakamura-enron-authenticity-2026.md))."

# Open questions
* [Tarball checksum and exact message count](/questions/enron-tarball-checksum-and-message-count.md)
* [Charset, date and Message-ID anomalies](/questions/enron-header-anomalies-charset-dates-message-id.md)
* [ISI MySQL dump snapshot content](/questions/enron-isi-mysql-dump-availability.md)
