"""CSV booleans must be parsed before their MySQL 0/1 projection, across year files."""
import csv
import importlib.util
from pathlib import Path
import sys


def test_full_archive_boolean_projection(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "datasets/chicago_crimes/convert.py"
    spec = importlib.util.spec_from_file_location("chicago_converter", path)
    converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(converter)
    monkeypatch.setattr(converter, "YEARS", range(2001, 2003))
    source = tmp_path / "input"
    (source / "full").mkdir(parents=True)
    output = tmp_path / "output"
    output.mkdir()
    columns = [name for name, _, _ in converter.CRIME_COLUMNS] + ["location"]
    for i, year in enumerate(converter.YEARS):
        row = dict.fromkeys(columns, "")
        row.update(id=i + 1, case_number=f"TEST-{i}", date=f"{year}-01-01T00:00:00",
                   block="TEST BLOCK", iucr="0110", primary_type="TEST", description="TEST",
                   arrest="true" if i else "false", domestic="false" if i else "true",
                   beat=1, district=1, ward=1, community_area=1, fbi_code="01A",
                   x_coordinate=0, y_coordinate=0, year=year, updated_on=f"{year}-01-01T00:00:00",
                   latitude=0, longitude=0, location="\n,\n(0, 0)")
        with (source / "full" / f"crimes_{year}.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerow(row)
    (source / "iucr.csv").write_text('IUCR\n0110\n08A\n')
    converter.full(str(source), str(output / "chicago_crimes_full.sql"))
    rows = [line.split("\t") for line in (output / "crimes_all.tsv").read_text().splitlines()]
    assert [(r[8], r[9]) for r in rows] == [("0", "1"), ("1", "0")]


def test_core_csv_boolean_projection(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "datasets/chicago_crimes/convert.py"
    spec = importlib.util.spec_from_file_location("chicago_core_converter", path)
    converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(converter)
    columns = [name for name, _, _ in converter.CRIME_COLUMNS]
    row = dict.fromkeys(columns, "")
    row.update(id=1, case_number="TEST", date="2024-01-01T00:00:00", block="TEST",
               iucr="0110", arrest="false", domestic="true", beat=1, district=1,
               ward=1, community_area=1, year=2024, updated_on="2024-01-01T00:00:00")
    with (tmp_path / converter.CRIMES).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)
    (tmp_path / converter.IUCR).write_text(
        'IUCR,PRIMARY DESCRIPTION,SECONDARY DESCRIPTION,INDEX CODE,ACTIVE\n'
        '0110,TEST,TEST,I,false\n08A,TEST,TEST,I,true\n')
    monkeypatch.setattr(sys, "argv", [str(path), str(tmp_path), str(tmp_path / "out.sql")])
    converter.main()
    crime = (tmp_path / "crimes.tsv").read_text().splitlines()[0].split("\t")
    assert (crime[8], crime[9]) == ("0", "1")
    codes = [line.split("\t") for line in (tmp_path / "iucr.tsv").read_text().splitlines()]
    assert [(row[0], row[-1]) for row in codes] == [("0110", "0"), ("08A", "1")]
