"""An opt-in dataset's measured engine dispositions belong in the catalogue."""
from megasamples.catalogue import render


def test_explicit_validation_dispositions_are_visible():
    item = dict(name="sample", database="sample", tier="extended", licences=[],
                ports={}, what="Sample", append=False, tables=4, rows=10,
                validation={"engines": {"mysql": {"status": "Passed"},
                                        "postgres": {"status": "Unsupported"},
                                        "sqlite": {"status": "Not run"}}})
    text = render([item])
    assert "MySQL (Passed) · PostgreSQL (Unsupported) · SQLite (Not run)" in text
