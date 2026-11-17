"""Decode the SQLite CLI registry output used by the isolated validation."""
import csv
import io


def sqlite_registry_rows(text):
    return list(csv.reader(io.StringIO(text), delimiter='\t'))
