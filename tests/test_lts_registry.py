"""SQLite's TSV quoting must preserve the complete registry JSON value."""
import json
import pytest
from docs.validation.lts_registry import sqlite_registry_rows


@pytest.mark.parametrize('text', [
    'pubs\t"{""jobs"":14,""employee"":43}"\n',
    'pubs\t{"jobs":14,"employee":43}\n',
])
def test_sqlite_registry_json_roundtrip(text):
    rows = sqlite_registry_rows(text)
    assert {name: json.loads(counts) for name, counts in rows} == {
        'pubs': {'jobs': 14, 'employee': 43}}
