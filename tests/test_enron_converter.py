"""Keep the shipped Enron timestamp values independent of the converter host timezone."""
import importlib.util
import io
import os
import sys
import tarfile
import time
from pathlib import Path

import pytest


@pytest.mark.parametrize("host_timezone", ["UTC", "America/Chicago"])
@pytest.mark.parametrize("date, expected", [
    ("Tue, 1 Jan 1980 00:00:00 +0000", "1979-12-31 18:00:00"),
    ("Thu, 1 Jun 2000 00:00:00 +0000", "2000-05-31 19:00:00"),
    ("Tue, 1 Jan 1980 00:00:00", "1980-01-01 00:00:00"),
])
def test_dates_preserve_the_pinned_corpus_timezone(tmp_path, monkeypatch, host_timezone, date, expected):
    path = Path(__file__).resolve().parents[1] / "datasets/enron/convert.py"
    spec = importlib.util.spec_from_file_location("enron_converter", path)
    converter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(converter)
    source = tmp_path / "input"
    source.mkdir()
    body = f"Date: {date}\nSubject: fixture\n\nbody\n".encode()
    with tarfile.open(source / converter.ARCHIVE, "w:gz") as archive:
        member = tarfile.TarInfo("maildir/sample/inbox/1.")
        member.size = len(body)
        archive.addfile(member, io.BytesIO(body))
    target = tmp_path / "enron"
    target.mkdir()
    monkeypatch.setattr(sys, "argv", [str(path), str(source), str(target / "enron.sql")])
    original_timezone = os.environ.get("TZ")
    try:
        os.environ["TZ"] = host_timezone
        time.tzset()
        converter.main()
    finally:
        if original_timezone is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_timezone
        time.tzset()
    assert (target / "message.tsv").read_text().split("\t")[5] == expected
