"""The copy suite's fixture must not provide what the image is supposed to provide.

The TCP copy suite once passed only because its fixture wrote PostgreSQL's copy service row, which
the shipped image never wrote. The fixture may set passwords and add its own sample data, but the
copy service metadata (the service row and the namespaces) comes from the image under test.
"""
import re
from pathlib import Path

FIXTURE = Path(__file__).parent / "gates" / "dl077_copy_fixture.py"


def test_fixture_never_writes_the_copy_service_or_namespaces():
    source = FIXTURE.read_text()
    writes = re.findall(r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO|TRUNCATE)\s+"
                        r"(?:megasamples\.)?(copy_service|copy_namespaces)\b", source, re.I)
    assert writes == [], writes
