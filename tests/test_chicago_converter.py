"""CSV booleans must be parsed before their MySQL 0/1 projection, across year files."""
import csv
import importlib.util
from pathlib import Path


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
