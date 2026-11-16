"""Staged CSV paths follow the output dataset, including the review extension."""
import importlib.util
import re
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("extended", [False, True])
def test_load_paths_point_to_the_staged_csvs(tmp_path, monkeypatch, extended):
    path = Path(__file__).resolve().parents[1] / "datasets/dvdstore/convert.py"
    spec = importlib.util.spec_from_file_location("dvdstore_converter", path)
    converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(converter)
    monkeypatch.setattr(converter, "SCRIPTS", [])
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    name = "dvdstore_reviews" if extended else "dvdstore"
    target = tmp_path / "stage" / name
    target.mkdir(parents=True)
    files = [filename for _, names in (converter.EXTENDED_LOADS if extended else converter.LOADS) for filename in names]
    for filename in files:
        (downloads / filename).write_text("1,2\n")
    sql = target / (name + ".sql")
    monkeypatch.setattr(sys, "argv", [str(path), str(downloads), str(sql)] + (["--reviews"] if extended else []))
    converter.main()
    paths = re.findall(r"LOAD DATA LOCAL INFILE '([^']+)'", sql.read_text())
    assert paths == [f"/context/{name}/{filename}" for filename in files]
    assert all((target / Path(path).name).read_bytes() == (downloads / Path(path).name).read_bytes() for path in paths)
