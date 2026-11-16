#!/usr/bin/env python3
"""Dell DVD Store 3 (MySQL kit) -> the megasamples conventions.

Alone among these datasets the upstream scripts are already MySQL, so there is no dialect to
translate. What the converter does is rename the database, lower-case the identifiers (the naming
convention, and MySQL is case-sensitive for table names on Linux), put PRODUCTS on InnoDB, point the
loads at the build server's mount, and leave the two review tables to the extended tier -- they are
190 MB of the repository's 197 MB.

Record: knowledge/datasets/dell-dvd-store.md
"""
import os, re, shutil, sys

DATABASE = "dvdstore"
SCRIPTS = ["mysqlds3_create_db.sql", "mysqlds3_create_ind.sql", "mysqlds3_create_sp.sql"]
# deferred to the extended tier with their indexes; see the record's tier assignment
EXTENDED_TABLES = {"reviews", "reviews_helpfulness"}
# the extended tier: 190 MB of the repository's 197 MB, loaded on demand into an existing dvdstore
EXTENDED_LOADS = [("reviews", ["reviews.csv"]),
                  ("reviews_helpfulness", ["review_helpfulness.csv"])]
# table -> the CSVs the upstream load scripts read into it, in their order
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
LOADS = [("customers", ["us_cust.csv", "row_cust.csv"]),
         ("products", ["prod.csv"]),
         ("inventory", ["inv.csv"]),
         ("membership", ["membership.csv"]),
         ("orders", [f"{m}_orders.csv" for m in MONTHS]),
         ("orderlines", [f"{m}_orderlines.csv" for m in MONTHS]),
         ("cust_hist", [f"{m}_cust_hist.csv" for m in MONTHS])]


def lower_outside_literals(sql):
    """Lower-case everything except the contents of string literals.

    Identifiers here are all upper-case and so are the keywords, which MySQL does not care about;
    the literals do matter -- CATEGORIES is seeded with 'Action', 'Animation' and the rest.
    """
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in "'\"":
            j = i + 1
            while j < n and sql[j] != ch:
                j += 2 if sql[j] == "\\" else 1
            out.append(sql[i:j + 1]); i = j + 1; continue
        out.append(ch.lower()); i += 1
    return "".join(out)


def split_statements(sql, delimiter=";"):
    """Split on the delimiter outside string literals, honouring DELIMITER changes."""
    statements, current, i, n = [], [], 0, len(sql)
    while i < n:
        m = re.match(r"(?im)^[ \t]*delimiter[ \t]+(\S+)[ \t]*$", sql[i:])
        if m and (i == 0 or sql[i - 1] == "\n"):
            statements.append("".join(current)); current = []
            delimiter = m.group(1)
            i += m.end()
            continue
        if sql[i] in "'\"":
            quote, j = sql[i], i + 1
            while j < n and sql[j] != quote:
                j += 2 if sql[j] == "\\" else 1
            current.append(sql[i:j + 1]); i = j + 1; continue
        if sql.startswith(delimiter, i):
            statements.append("".join(current)); current = []
            i += len(delimiter); continue
        current.append(sql[i]); i += 1
    statements.append("".join(current))
    return [s.strip() for s in statements if s.strip()]


def main():
    downloads, dest = sys.argv[1], sys.argv[2]
    context = os.path.dirname(os.path.abspath(dest))
    inside = f"/context/{os.path.basename(context)}"
    extended = "--reviews" in sys.argv

    kept, dropped, procedures = [], [], 0
    for name in SCRIPTS:
        text = lower_outside_literals(open(os.path.join(downloads, name), encoding="utf-8").read())
        for statement in split_statements(text):
            statement = re.sub(r"(?s)/\*.*?\*/", "", statement)
            statement = "\n".join(l for l in statement.split("\n")
                                  if not l.lstrip().startswith("--")).strip()
            if not statement:
                continue
            if re.match(r"(?i)^(use|drop\s+database|create\s+database)\b", statement):
                continue                                  # this build names the database itself
            target = re.search(r"(?i)\b(?:table|index\s+\w+\s+on|procedure)\s+(?:ds3\.)?(\w+)",
                               statement)
            touched = re.findall(r"(?i)\b(reviews|reviews_helpfulness)\b", statement)
            # bool(): `a or (b and c)` yields None when both are falsy, and `None != False` is
            # True, which would skip every statement that matched neither test
            is_extended = bool(touched or (target and target.group(1) in EXTENDED_TABLES))
            # the extended run emits *only* the review objects, into an existing database
            if is_extended != extended:
                if not extended:
                    dropped.append(target.group(1) if target else "statement")
                continue
            statement = re.sub(r"(?i)\bds3\.", "", statement)
            statement = re.sub(r"(?i)\bengine\s*=\s*myisam\b", "ENGINE = InnoDB", statement)
            procedures += bool(re.match(r"(?i)^create\s+procedure", statement))
            kept.append(statement)

    loads, copied = [], 0
    for table, files in (EXTENDED_LOADS if extended else LOADS):
        for filename in files:
            shutil.copyfile(os.path.join(downloads, filename), os.path.join(context, filename))
            copied += 1
            loads.append(f"LOAD DATA LOCAL INFILE '{inside}/{filename}' INTO TABLE `{table}`\n"
                         f"  CHARACTER SET utf8mb4 FIELDS TERMINATED BY ',' "
                         f"OPTIONALLY ENCLOSED BY '\"';")

    if extended:
        out = [f"""-- Dell DVD Store 3 review tables (extended tier), prepared by
-- datasets/{DATABASE}/convert.py. These are 190 MB of the repository's 197 MB and are loaded into an
-- existing `{DATABASE}` database on demand -- they are not baked into the image.
SET NAMES utf8mb4;
SET SESSION foreign_key_checks = 0;
USE `{DATABASE}`;
DROP TABLE IF EXISTS `reviews_helpfulness`;
DROP TABLE IF EXISTS `reviews`;
"""]
    else:
        out = [f"""-- Dell DVD Store 3, prepared by datasets/{DATABASE}/convert.py from the upstream MySQL
-- kit (GPL-2.0-or-later). See datasets/{DATABASE}/LICENSE.
SET NAMES utf8mb4;
SET SESSION foreign_key_checks = 0;
DROP DATABASE IF EXISTS `{DATABASE}`;
CREATE DATABASE `{DATABASE}` DEFAULT CHARACTER SET utf8mb4;
USE `{DATABASE}`;
"""]
    tables = [s for s in kept if re.match(r"(?i)^create\s+table", s)]
    seed = [s for s in kept if re.match(r"(?i)^insert\b", s)]
    rest = [s for s in kept if s not in tables and s not in seed]
    out += [s + ";" for s in tables]
    out.append(f"\n-- {'-' * 60}\n-- data\n")
    out += [s + ";" for s in seed]
    out += loads
    out.append(f"\n-- {'-' * 60}\n-- indexes, constraints and stored procedures\n")
    for s in rest:
        out.append(f"DELIMITER $$\n{s}$$\nDELIMITER ;" if re.match(r"(?i)^create\s+procedure", s)
                   else s + ";")
    out.append("SET SESSION foreign_key_checks = 1;\n")
    open(dest, "w", encoding="utf-8").write("\n".join(out))

    print(f"  . prepared {len(tables)} tables, {procedures} procedures, "
          f"{len(rest) - procedures} indexes/constraints")
    print(f"  . staged {copied} CSV file(s)")
    if extended:
        print("  . extended tier: reviews and reviews_helpfulness, loaded into an existing dvdstore")
    else:
        print(f"  . left to the extended tier: {', '.join(sorted(EXTENDED_TABLES))} "
              f"({len(dropped)} statements)")
        print("  . dropped trigger restock: upstream ships it commented \"Doesn't work yet!!!\" and "
              "it inserts hard-coded values")


if __name__ == "__main__":
    main()
