"""The published PostgreSQL routine inventory matches design 4.2: every routine demo may execute, with its
reason, including P-3's named built-ins and P-8's direct grant (Sol round 7, 5; Opus round 7, P3-2)."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
NAMED = ("pg_export_snapshot()", "pg_current_snapshot()", "pg_database_size(oid)", "megasamples_policy_loaded()")


def test_published_inventories_carry_every_named_exception_with_a_reason():
    public = json.loads((ROOT / "docs/validation/dl-077-v1-public-routines.json").read_text())
    published = json.loads((ROOT / "docs/validation/strict-read-executable-routines.json").read_text())
    markdown = (ROOT / "docs/validation/strict-read-executable-routines.md").read_text()
    for inventory in (public, published):
        signatures = {item["signature"]: item for item in inventory["routines"]}
        assert inventory["count"] == len(signatures)
        for signature in NAMED:
            assert signature in signatures, signature
            assert signatures[signature]["reason"] and "NOT in explicit" not in signatures[signature]["reason"]
        assert not [item for item in inventory["routines"] if "NOT in explicit" in item["reason"]]
        assert "direct grant to demo" in signatures["megasamples_policy_loaded()"]["reason"]
    assert {item["signature"] for item in public["routines"]} == {item["signature"] for item in published["routines"]}
    assert f"{published['count']} signatures" in markdown and "`megasamples_policy_loaded()`" in markdown
