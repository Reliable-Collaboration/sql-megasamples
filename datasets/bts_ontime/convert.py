#!/usr/bin/env python3
"""BTS Reporting Carrier On-Time Performance (January 2025) -> MySQL.

One month of domestic flight segments: 539,747 rows and 109 columns, plus the three code lookups.
The CSV is read with DuckDB and written as contract TSV; the lookups are small enough to read in
Python, which is what lets one of them be transcoded (see below).

The record lists eleven hazards for this file and every one is real. The ones that shape this
converter:

* Every line ends with a trailing comma, so the header parses as **110** fields with an unnamed
  empty one. It is declared and dropped rather than left for a parser to invent a name for.
* Clock columns are quoted zero-padded strings -- `"0659"`, `"0053"` -- so they stay `CHAR(4)`;
  reading them as integers turns `"0053"` into 53. `"2400"` really occurs (33 times in `DepTime`,
  245 in `ArrTime`, 58 in `WheelsOff`, 202 in `WheelsOn`, never in a scheduled column). The record
  expected that to need special-casing; it does not, because MySQL's `TIME` runs past 24 hours and
  `MAKETIME(24, 0, 0)` is simply `24:00:00`. Four generated columns expose the parsed times.
* Integral quantities are written as decimals (`Cancelled` = `0.00`, `Distance` = `2475.00`), so
  every numeric column is cast explicitly. All 31 numeric columns were checked for a fractional
  part first: there is none, so the narrow integer types are lossless.
* `L_AIRPORT.csv` is **not UTF-8**. The refreshed 320,236-byte snapshot still has one `0xCD` byte,
  the `Í` of "Scarlett MartÍnez International" in Panama, which makes the file Latin-1 and makes a UTF-8 read fail outright. The
  record inferred these lookups were ASCII-transliterated and asked for a re-check; they are not.

Record: knowledge/datasets/bts-ontime.md
"""
import csv, os, sys

import duckdb

DATABASE = "bts_ontime"
FLIGHTS = "ontime.csv"
ZIP = "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2025_1.zip"
MEMBER = "On_Time_Reporting_Carrier_On_Time_Performance_(1987_present)_2025_1.csv"
LOOKUPS = [("L_AIRPORT.csv", "l_airport", "cp1252", 5, 120),
           ("L_AIRLINE_ID.csv", "l_airline_id", "utf-8", 7, 120),
           ("L_UNIQUE_CARRIERS.csv", "l_unique_carriers", "utf-8", 7, 120)]

# (upstream column, MySQL type). The MySQL name is the upstream name lower-cased -- the project's
# rule -- and nothing here needs renaming. Ranges were measured before the widths were chosen.
COLUMNS = [
    ("Year", "SMALLINT"), ("Quarter", "TINYINT"), ("Month", "TINYINT"),
    ("DayofMonth", "TINYINT"), ("DayOfWeek", "TINYINT"), ("FlightDate", "DATE NOT NULL"),
    ("Reporting_Airline", "VARCHAR(7)"), ("DOT_ID_Reporting_Airline", "INT"),
    ("IATA_CODE_Reporting_Airline", "VARCHAR(7)"), ("Tail_Number", "VARCHAR(10)"),
    ("Flight_Number_Reporting_Airline", "VARCHAR(5)"),
    ("OriginAirportID", "INT"), ("OriginAirportSeqID", "INT"), ("OriginCityMarketID", "INT"),
    ("Origin", "CHAR(3)"), ("OriginCityName", "VARCHAR(60)"), ("OriginState", "CHAR(2)"),
    ("OriginStateFips", "CHAR(2)"), ("OriginStateName", "VARCHAR(60)"), ("OriginWac", "SMALLINT"),
    ("DestAirportID", "INT"), ("DestAirportSeqID", "INT"), ("DestCityMarketID", "INT"),
    ("Dest", "CHAR(3)"), ("DestCityName", "VARCHAR(60)"), ("DestState", "CHAR(2)"),
    ("DestStateFips", "CHAR(2)"), ("DestStateName", "VARCHAR(60)"), ("DestWac", "SMALLINT"),
    ("CRSDepTime", "CHAR(4)"), ("DepTime", "CHAR(4)"), ("DepDelay", "SMALLINT"),
    ("DepDelayMinutes", "SMALLINT"), ("DepDel15", "TINYINT"), ("DepartureDelayGroups", "TINYINT"),
    ("DepTimeBlk", "VARCHAR(9)"), ("TaxiOut", "SMALLINT"), ("WheelsOff", "CHAR(4)"),
    ("WheelsOn", "CHAR(4)"), ("TaxiIn", "SMALLINT"),
    ("CRSArrTime", "CHAR(4)"), ("ArrTime", "CHAR(4)"), ("ArrDelay", "SMALLINT"),
    ("ArrDelayMinutes", "SMALLINT"), ("ArrDel15", "TINYINT"), ("ArrivalDelayGroups", "TINYINT"),
    ("ArrTimeBlk", "VARCHAR(9)"),
    ("Cancelled", "TINYINT"), ("CancellationCode", "CHAR(1)"), ("Diverted", "TINYINT"),
    ("CRSElapsedTime", "SMALLINT"), ("ActualElapsedTime", "SMALLINT"), ("AirTime", "SMALLINT"),
    ("Flights", "TINYINT"), ("Distance", "SMALLINT"), ("DistanceGroup", "TINYINT"),
    ("CarrierDelay", "SMALLINT"), ("WeatherDelay", "SMALLINT"), ("NASDelay", "SMALLINT"),
    ("SecurityDelay", "SMALLINT"), ("LateAircraftDelay", "SMALLINT"),
    ("FirstDepTime", "CHAR(4)"), ("TotalAddGTime", "SMALLINT"), ("LongestAddGTime", "SMALLINT"),
    ("DivAirportLandings", "TINYINT"), ("DivReachedDest", "TINYINT"),
    ("DivActualElapsedTime", "SMALLINT"), ("DivArrDelay", "SMALLINT"), ("DivDistance", "SMALLINT"),
] + [c for n in range(1, 6) for c in (
    (f"Div{n}Airport", "CHAR(3)"), (f"Div{n}AirportID", "INT"), (f"Div{n}AirportSeqID", "INT"),
    (f"Div{n}WheelsOn", "CHAR(4)"), (f"Div{n}TotalGTime", "SMALLINT"),
    (f"Div{n}LongestGTime", "SMALLINT"), (f"Div{n}WheelsOff", "CHAR(4)"),
    (f"Div{n}TailNum", "VARCHAR(10)"))]

INTEGER = ("TINYINT", "SMALLINT", "INT", "BIGINT")
# the four clock columns worth having parsed; 2400 needs no special case because MySQL TIME
# runs to 838:59:59
TIMES = [("CRSDepTime", "crs_dep_time"), ("DepTime", "dep_time"),
         ("CRSArrTime", "crs_arr_time"), ("ArrTime", "arr_time")]


def projection(column, mysql):
    """The DuckDB expression. Everything is read as text, so every narrowing is written down."""
    q = f'"{column}"'
    if mysql.startswith("DATE"):
        return f"CAST({q} AS DATE)"
    if mysql.startswith(INTEGER):
        # '0.00' will not cast straight to an integer, and the values were checked to be integral
        return f"CAST(TRY_CAST({q} AS DOUBLE) AS BIGINT)"
    return q


def write_lookup(downloads, context, filename, table, encoding):
    """Read one lookup and write it as UTF-8 TSV. Returns (rows, bytes re-encoded)."""
    path = os.path.join(downloads, filename)
    raw = open(path, "rb").read()
    outside = sum(1 for b in raw if b > 0x7F)
    text = raw.decode(encoding)
    rows = list(csv.reader(text.splitlines()))[1:]
    with open(os.path.join(context, f"{table}.tsv"), "w", encoding="utf-8", newline="") as fh:
        for row in rows:
            if not row:
                continue
            fh.write("\t".join(c.replace("\\", "\\\\").replace("\t", " ") for c in row[:2]) + "\n")
    return len(rows), outside


def main():
    downloads, dest = sys.argv[1], sys.argv[2]
    context = os.path.dirname(os.path.abspath(dest))
    inside = f"/context/{os.path.basename(context)}"
    flights = os.path.join(downloads, FLIGHTS)
    if not os.path.exists(flights):
        extract(os.path.join(downloads, ZIP), flights)
    con = duckdb.connect()
    src = flights.replace("'", "''")
    reader = (f"read_csv('{src}', header=true, all_varchar=true, null_padding=true)")

    header = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {reader}").fetchall()]
    named = [c for c, _ in COLUMNS]
    if header[:len(named)] != named:
        sys.exit(f"upstream column list changed: {set(header) ^ set(named)}")
    if len(header) != len(named) + 1:
        sys.exit(f"expected {len(named)} named columns plus one trailing empty, got {len(header)}")

    rows = con.execute(f"SELECT COUNT(*) FROM {reader}").fetchone()[0]
    totals = con.execute(
        f"SELECT SUM(TRY_CAST(Distance AS DOUBLE)), SUM(TRY_CAST(ArrDelayMinutes AS DOUBLE)), "
        f"SUM(TRY_CAST(Cancelled AS DOUBLE)), SUM(TRY_CAST(Diverted AS DOUBLE)) FROM {reader}"
    ).fetchone()

    select = ", ".join(f'{projection(c, t)} AS "{c.lower()}"' for c, t in COLUMNS)
    con.execute(f"COPY (SELECT {select} FROM {reader}) TO "
                f"'{os.path.join(context, 'ontime.tsv').replace(chr(39), chr(39) * 2)}' "
                "(FORMAT CSV, DELIMITER '\t', HEADER false, NULLSTR '\\N', QUOTE '', ESCAPE '')")

    lookups = []
    for filename, table, encoding, _, _ in LOOKUPS:
        n, high = write_lookup(downloads, context, filename, table, encoding)
        lookups.append((table, n, encoding, high))

    columns = ",\n".join(f"  `{c.lower()}` {t}" for c, t in COLUMNS)
    generated = "\n".join(
        f"  `{name}` TIME GENERATED ALWAYS AS (CASE WHEN `{src_col.lower()}` IS NULL "
        f"OR `{src_col.lower()}` = '' THEN NULL ELSE "
        f"MAKETIME(CAST(LEFT(`{src_col.lower()}`, 2) AS UNSIGNED), "
        f"CAST(RIGHT(`{src_col.lower()}`, 2) AS UNSIGNED), 0) END) VIRTUAL,"
        for src_col, name in TIMES)
    lookup_ddl = "\n\n".join(
        f"""CREATE TABLE `{table}` (
  `code` VARCHAR(7) NOT NULL,
  `description` VARCHAR(120) NOT NULL,
  PRIMARY KEY (`code`)
) COMMENT = 'BTS lookup {filename}';"""
        for filename, table, _, _, _ in LOOKUPS)
    lookup_loads = "\n".join(
        f"LOAD DATA LOCAL INFILE '{inside}/{table}.tsv' INTO TABLE `{table}`\n"
        f"  CHARACTER SET utf8mb4 (`code`, `description`);"
        for _, table, _, _, _ in LOOKUPS)
    names = ", ".join(f"`{c.lower()}`" for c, _ in COLUMNS)

    out = f"""-- BTS Reporting Carrier On-Time Performance, January 2025, prepared by
-- datasets/{DATABASE}/convert.py. Upstream: U.S. Bureau of Transportation Statistics (public
-- domain). See datasets/{DATABASE}/LICENSE.
SET NAMES utf8mb4;
SET SESSION foreign_key_checks = 0;
DROP DATABASE IF EXISTS `{DATABASE}`;
CREATE DATABASE `{DATABASE}` DEFAULT CHARACTER SET utf8mb4;
USE `{DATABASE}`;

{lookup_ddl}

-- No natural primary key: BTS re-uses a flight number on a route after a schedule change, and the
-- archive has historically held exact duplicate rows. (Neither occurs in this month -- the tuple
-- below is unique across all 539,747 rows and there are no duplicate rows -- but that is a property
-- of one month, not of the table, so the key stays a surrogate and the tuple gets a plain index.)
-- Origin/Dest are NOT foreign keys onto l_airport: BTS re-uses airport codes over time, which is
-- why it also publishes OriginAirportSeqID.
CREATE TABLE `ontime` (
  `flight_id` INT NOT NULL AUTO_INCREMENT,
{columns},
{generated}
  PRIMARY KEY (`flight_id`),
  KEY `ix_ontime_flightdate` (`flightdate`),
  KEY `ix_ontime_origin` (`origin`),
  KEY `ix_ontime_dest` (`dest`),
  KEY `ix_ontime_carrier` (`reporting_airline`),
  KEY `ix_ontime_segment` (`flightdate`, `reporting_airline`,
                           `flight_number_reporting_airline`, `origin`, `dest`, `crsdeptime`)
) COMMENT = 'one row per scheduled domestic flight segment, January 2025';

-- {'-' * 60}
-- data

{lookup_loads}
LOAD DATA LOCAL INFILE '{inside}/ontime.tsv' INTO TABLE `ontime`
  CHARACTER SET utf8mb4 ({names});

-- {'-' * 60}
-- view

CREATE SQL SECURITY INVOKER VIEW `v_ontime_delay` AS
SELECT f.`flightdate`, f.`reporting_airline`, c.`description` AS `carrier`,
       f.`flight_number_reporting_airline` AS `flight_number`,
       f.`origin`, o.`description` AS `origin_airport`,
       f.`dest`, d.`description` AS `dest_airport`,
       f.`crs_dep_time`, f.`dep_time`, f.`depdelayminutes`,
       f.`crs_arr_time`, f.`arr_time`, f.`arrdelayminutes`,
       f.`cancelled`, f.`cancellationcode`, f.`diverted`
FROM `ontime` f
LEFT JOIN `l_unique_carriers` c ON c.`code` = f.`reporting_airline`
LEFT JOIN `l_airport` o ON o.`code` = f.`origin`
LEFT JOIN `l_airport` d ON d.`code` = f.`dest`;

SET SESSION foreign_key_checks = 1;
"""
    open(dest, "w", encoding="utf-8").write(out)

    print(f"  . {rows:,} flight segments, {len(COLUMNS)} columns "
          f"(+1 trailing empty field per line, dropped)")
    print(f"  . source totals: distance {totals[0]:,.0f}, arrival delay minutes {totals[1]:,.0f}, "
          f"cancelled {totals[2]:,.0f}, diverted {totals[3]:,.0f}")
    for table, n, encoding, high in lookups:
        note = f", {high} byte(s) above 0x7F re-encoded from {encoding}" if high else ""
        print(f"  . {table}: {n:,} rows{note}")


def extract(zip_path, out_path):
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        with z.open(MEMBER) as fh, open(out_path, "wb") as w:
            while True:
                chunk = fh.read(1 << 22)
                if not chunk:
                    break
                w.write(chunk)
    print(f"  . extracted {os.path.basename(out_path)} ({os.path.getsize(out_path):,} bytes)")


if __name__ == "__main__":
    main()
