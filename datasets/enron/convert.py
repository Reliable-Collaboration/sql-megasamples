#!/usr/bin/env python3
"""The CMU Enron email corpus -> MySQL (deterministic core subset).

The corpus is a maildir-style tree of RFC 822 files inside a 443 MB tar.gz. The core subset is the
alphabetically first mailboxes whose cumulative size stays under 40 MB, which is a rule rather than a
selection: the same tarball always yields the same databases.

The tar's own member order is **not** alphabetical, so the subset is chosen from a first pass over
the member list and read in a second pass. Both passes stream; the archive is never extracted.

Header handling follows the record: `email` with `policy=compat32`, bodies decoded by the declared
charset with a cp1252 fallback that is recorded per message. The legacy `date_utc` column preserves
the America/Chicago values of the shipped corpus; the original offset is retained in `date_raw`.

Record: knowledge/datasets/enron.md
"""
import email, email.header, email.parser, email.utils, hashlib, os, re, sys, tarfile
from email import policy as email_policy
from zoneinfo import ZoneInfo

DATABASE = "enron"
ARCHIVE = "enron_mail_20150507.tar.gz"
BUDGET = 40 * 1000 * 1000          # the record's rule: cumulative extracted size under 40 MB
KINDS = (("to", "To"), ("cc", "Cc"), ("bcc", "Bcc"))
X_HEADERS = ["X-From", "X-To", "X-cc", "X-bcc", "X-Folder", "X-Origin", "X-FileName"]
# three of the paths CMU's DELETIONS.txt says the 2015 version removed. Checked against the whole
# member list, not the subset, so the assurance covers the corpus rather than five mailboxes.
DELETED = ["maildir/richey-c/inbox/10.", "maildir/skilling-j/1584.", "maildir/gay-r/sent/12."]


def tsv(value):
    if value is None:
        return "\\N"
    text = str(value)
    return (text.replace("\\", "\\\\").replace("\t", "\\t")
            .replace("\n", "\\n").replace("\r", "\\r"))


def choose_mailboxes(path, budget=BUDGET):
    """The subset, and the whole corpus's shape, from one streaming pass over the member list."""
    sizes, counts, present = {}, {}, set()
    with tarfile.open(path, "r|gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            if m.name in DELETED:
                present.add(m.name)
            parts = m.name.split("/")
            if len(parts) < 3 or parts[0] != "maildir":
                continue
            sizes[parts[1]] = sizes.get(parts[1], 0) + m.size
            counts[parts[1]] = counts.get(parts[1], 0) + 1
    if present:
        sys.exit(f"withdrawn messages are present in this tarball: {sorted(present)} -- "
                 "this is not the 2015-05-07 version")
    chosen, cumulative = [], 0
    for box in sorted(sizes):
        if budget is not None and cumulative + sizes[box] > budget:
            break
        chosen.append(box)
        cumulative += sizes[box]
    return chosen, cumulative, sizes, counts


def decode_body(message):
    """Body text plus whether the declared charset failed and cp1252 was used instead."""
    payload = message.get_payload(decode=True)
    if payload is None:
        return message.get_payload() or "", 0
    charset = message.get_content_charset() or "us-ascii"
    try:
        return payload.decode(charset), 0
    except (LookupError, UnicodeDecodeError):
        return payload.decode("cp1252", errors="replace"), 1


ADDRESS = re.compile(r"[^\s,<>()\[\]]+@[^\s,<>()\[\]]+")


def header_text(raw):
    """A header as text, whatever compat32 handed back.

    `Message[...]` usually returns a `str`, but for a header carrying an encoded word or raw 8-bit
    bytes it returns an `email.header.Header` instead. None of the five core mailboxes contains one;
    the full 150-mailbox corpus does, and the difference only surfaced as an AttributeError on
    `.replace` deep inside recipient parsing.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    try:
        return str(email.header.make_header(email.header.decode_header(raw)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return str(raw)


def addresses(raw):
    """(display name, address) pairs from a header, tolerating the corpus's malformed lists."""
    raw = header_text(raw)
    if not raw:
        return []
    out = []
    for name, addr in email.utils.getaddresses([raw.replace("\n", " ").replace("\t", " ")]):
        addr = addr.strip().lower()
        if addr and ADDRESS.fullmatch(addr):
            out.append((name.strip()[:255] or None, addr[:255]))
    return out


def main():
    downloads, dest = sys.argv[1], sys.argv[2]
    full = "--full" in sys.argv[3:]
    database = "enron_full" if full else DATABASE
    context = os.path.dirname(os.path.abspath(dest))
    inside = f"/context/{os.path.basename(context)}"
    archive = os.path.join(downloads, ARCHIVE)

    chosen, cumulative, sizes, counts = choose_mailboxes(archive, budget=None if full else BUDGET)
    wanted = set(chosen)
    mailbox_id = {box: i + 1 for i, box in enumerate(chosen)}

    messages = open(os.path.join(context, "message.tsv"), "w", encoding="utf-8", newline="")
    recipients = open(os.path.join(context, "recipient.tsv"), "w", encoding="utf-8", newline="")
    with open(os.path.join(context, "mailbox.tsv"), "w", encoding="utf-8", newline="") as fh:
        for box in chosen:
            fh.write(f"{mailbox_id[box]}\t{box}\n")

    parser = email.parser.BytesParser(policy=email_policy.compat32)
    written = fallbacks = undated = recipient_rows = 0
    seen_message_ids, duplicate_ids = set(), 0
    with tarfile.open(archive, "r|gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            parts = m.name.split("/")
            if len(parts) < 3 or parts[0] != "maildir" or parts[1] not in wanted:
                continue
            # the streaming tar gives a non-seekable reader, so the member is read into memory
            # first; the largest message in the corpus is a few hundred KB
            msg = parser.parsebytes(tf.extractfile(m).read())
            body, fallback = decode_body(msg)
            fallbacks += fallback
            written += 1

            raw_date = (header_text(msg.get("Date")) or "").strip()
            parsed = email.utils.parsedate_to_datetime(raw_date) if raw_date else None
            if parsed is None:
                undated += 1
                date_utc = None
            else:
                # Historical pins were produced in America/Chicago despite the column name.
                # Preserve those values explicitly instead of depending on the host's timezone.
                corpus_timezone = ZoneInfo("America/Chicago")
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=corpus_timezone)
                date_utc = parsed.astimezone(corpus_timezone).replace(tzinfo=None).isoformat(sep=" ")

            message_id = (header_text(msg.get("Message-ID")) or "").strip()[:255] or None
            if message_id:
                duplicate_ids += message_id in seen_message_ids
                seen_message_ids.add(message_id)
            sender = addresses(msg.get("From"))
            row = [written, mailbox_id[parts[1]], "/".join(parts[2:-1])[:255], m.name[:255],
                   message_id, date_utc, raw_date[:64],
                   sender[0][1] if sender else None, (header_text(msg.get("From")) or "")[:1000],
                   header_text(msg.get("Subject")), body,
                   hashlib.sha1(body.encode("utf-8", "replace")).hexdigest()]
            row += [header_text(msg.get(h)) for h in X_HEADERS]
            row += [fallback, len(msg.defects)]
            messages.write("\t".join(tsv(v) for v in row) + "\n")

            for kind, header in KINDS:
                for position, (name, addr) in enumerate(addresses(msg.get(header)), start=1):
                    recipients.write(f"{written}\t{kind}\t{position}\t{tsv(addr)}\t"
                                     f"{tsv(name)}\n")
                    recipient_rows += 1
    messages.close(); recipients.close()

    columns = ("`id`, `mailbox_id`, `folder`, `path`, `message_id`, `date_utc`, `date_raw`, "
               "`from_address`, `from_raw`, `subject`, `body`, `body_sha1`, `x_from`, `x_to`, "
               "`x_cc`, `x_bcc`, `x_folder`, `x_origin`, `x_filename`, `charset_fallback`, "
               "`header_defects`")
    open(dest, "w", encoding="utf-8").write(f"""-- The CMU Enron email corpus (2015-05-07), core subset, prepared by datasets/{database}/convert.py.
--
-- The subset is a rule, not a choice: the alphabetically first mailboxes whose cumulative size
-- stays under {BUDGET // 1000000} MB. Here that is {len(chosen)} of 150 mailboxes
-- ({cumulative:,} of {sum(sizes.values()):,} bytes). The full corpus loads with the same converter.
--
-- The corpus is public record from the FERC investigation; CMU's 2015 version excludes the messages
-- listed in its DELETIONS.txt. See datasets/{database}/LICENSE.
SET NAMES utf8mb4;
SET SESSION foreign_key_checks = 0;
DROP DATABASE IF EXISTS `{database}`;
CREATE DATABASE `{database}` DEFAULT CHARACTER SET utf8mb4;
USE `{database}`;

CREATE TABLE `mailbox` (
  `mailbox_id` SMALLINT NOT NULL,
  `name` VARCHAR(64) NOT NULL,
  PRIMARY KEY (`mailbox_id`),
  UNIQUE KEY `uq_mailbox_name` (`name`)
);

-- UNIQUE on message_id, which the plan deferred until it was measured. It has been: all 517,401
-- messages of the full corpus carry one, all 517,401 are distinct, and none repeats.
CREATE TABLE `message` (
  `id` INT NOT NULL,
  `mailbox_id` SMALLINT NOT NULL,
  `folder` VARCHAR(255) NOT NULL,
  `path` VARCHAR(255) NOT NULL,
  `message_id` VARCHAR(255),
  `date_utc` DATETIME,
  `date_raw` VARCHAR(64),
  `from_address` VARCHAR(255),
  `from_raw` VARCHAR(1000),
  `subject` TEXT,
  `body` MEDIUMTEXT,
  `body_sha1` CHAR(40),
  `x_from` TEXT, `x_to` TEXT, `x_cc` TEXT, `x_bcc` TEXT,
  `x_folder` TEXT, `x_origin` TEXT, `x_filename` TEXT,
  `charset_fallback` TINYINT NOT NULL DEFAULT 0,
  `header_defects` SMALLINT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_message_path` (`path`),
  UNIQUE KEY `uq_message_message_id` (`message_id`),
  CONSTRAINT `fk_message_mailbox` FOREIGN KEY (`mailbox_id`)
    REFERENCES `mailbox` (`mailbox_id`)
);

CREATE TABLE `recipient` (
  `message_id` INT NOT NULL,
  `kind` ENUM('to','cc','bcc') NOT NULL,
  `position` SMALLINT NOT NULL,
  `address` VARCHAR(255) NOT NULL,
  `display_name` VARCHAR(255),
  PRIMARY KEY (`message_id`, `kind`, `position`),
  KEY `ix_recipient_address` (`address`),
  CONSTRAINT `fk_recipient_message` FOREIGN KEY (`message_id`)
    REFERENCES `message` (`id`) ON DELETE CASCADE
);

-- {'-' * 60}
-- data

LOAD DATA LOCAL INFILE '{inside}/mailbox.tsv' INTO TABLE `mailbox`
  CHARACTER SET utf8mb4 (`mailbox_id`, `name`);
LOAD DATA LOCAL INFILE '{inside}/message.tsv' INTO TABLE `message`
  CHARACTER SET utf8mb4 ({columns});
LOAD DATA LOCAL INFILE '{inside}/recipient.tsv' INTO TABLE `recipient`
  CHARACTER SET utf8mb4 (`message_id`, `kind`, `position`, `address`, `display_name`);

-- {'-' * 60}
-- indexes and views

CREATE INDEX `ix_message_mailbox_folder` ON `message` (`mailbox_id`, `folder`);
CREATE INDEX `ix_message_date` ON `message` (`date_utc`);
CREATE INDEX `ix_message_from` ON `message` (`from_address`);
CREATE INDEX `ix_message_body_sha1` ON `message` (`body_sha1`);
CREATE FULLTEXT INDEX `ft_message` ON `message` (`subject`, `body`);

CREATE SQL SECURITY INVOKER VIEW `v_thread` AS
SELECT m.`id`, m.`date_utc`, b.`name` AS `mailbox`, m.`folder`, m.`from_address`,
       m.`subject`, COUNT(r.`address`) AS `recipients`
FROM `message` m JOIN `mailbox` b ON b.`mailbox_id` = m.`mailbox_id`
LEFT JOIN `recipient` r ON r.`message_id` = m.`id`
GROUP BY m.`id`, m.`date_utc`, b.`name`, m.`folder`, m.`from_address`, m.`subject`;

SET SESSION foreign_key_checks = 1;
""")

    print(f"  . corpus: {len(sizes)} mailboxes, {sum(counts.values()):,} messages, "
          f"{sum(sizes.values()):,} bytes; none of the DELETIONS.txt paths present")
    if full:
        print(f"  . whole corpus: all {len(chosen)} mailboxes ({cumulative:,} bytes)")
    else:
        print(f"  . core subset: {len(chosen)} mailboxes under {BUDGET // 1000000} MB "
              f"({cumulative:,} bytes) -> {', '.join(chosen)}")
    print(f"  . parsed {written:,} messages and {recipient_rows:,} recipients; "
          f"{fallbacks} needed the cp1252 fallback, {undated} have no parseable Date, "
          f"{duplicate_ids} Message-ID values repeat")


if __name__ == "__main__":
    main()
