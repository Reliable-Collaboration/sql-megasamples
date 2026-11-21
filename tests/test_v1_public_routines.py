"""The routine inventories: PR #14's evidence stays as published, and v1's own inventory is complete.

Sol round 7, 5 and Opus round 7, P3-2: the v1 inventory lists every routine demo may execute, with
its reason, including P-3's named built-ins and P-8's direct grant. Opus and Sol round 8, the P2: a v1
publication must not overwrite PR #14's evidence, and the IA-01 reconciliation is recorded signature by
signature. Sol round 8, P3-2: the guard regenerates every published row from the shared reasons, so a
generator regression or an incomplete row fails here, not only at the next publication.
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
from docs.validation import routine_reasons  # noqa: E402

VALIDATION = ROOT / "docs/validation"
NAMED = ("pg_export_snapshot()", "pg_current_snapshot()", "pg_database_size(oid)", "megasamples_policy_loaded()")
# DataIntent's IA-01 inventory at 4a8aad61c8ab: its SHA-256, which PR #14's published inventory also has.
IA01_SHA256 = "be570f392de66be45d868cee27a2a5d71570c7bf87b5db93ce47179e2cd08076"
# PR #14's head, whose files the publication canary receipt hashed.
PR14_HEAD = "2879fc472ad1ebc2d0bf808a7d7bd4a5206f52c4"
# The one path the receipt hashed that was never tracked: build/ is ignored.
UNTRACKED = "build/strict-read/pr-body.md"
# Files the receipt hashed that later v1 work changed on purpose: current documentation, engine policy
# code and tests. Their receipt hashes describe PR14_HEAD (recorded in tests/dl077-v1-read-profile.md).
CHANGED_SINCE_PR14 = {
    ".dockerignore", "docs/strict-read-account.md", "engines/postgres/Dockerfile",
    "engines/postgres/init/10-read-profile.sql", "engines/postgres/init/read-routine-names.sql",
    "engines/postgres/read-policy/read_policy--1.sql", "engines/postgres/read-policy/read_policy.c",
    "engines/postgres/read-policy/read_policy.control", "megasamples/engines/mysql/image_test.py",
    "megasamples/engines/postgres/image_test.py", "tests/test_mysql_image_startup.py",
    "tests/test_strict_read_native.py",
}


def sha256(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def v1():
    return (json.loads((VALIDATION / "dl-077-v1-public-routines.json").read_text()),
            (VALIDATION / "dl-077-v1-public-routines.md").read_text())


def test_pr14_evidence_files_still_match_their_receipt():
    receipt = json.loads((VALIDATION / "strict-read-publication-canaries.json").read_text())
    tracked = set(subprocess.check_output(["git", "-C", str(ROOT), "ls-files"], text=True).split())
    # Round 9 (Opus 2, Sol 2): one path the receipt hashed was never tracked, the generated PR body. Every
    # other path is compared, so a deleted or untracked evidence file fails as an overwritten one does.
    assert {entry["path"] for entry in receipt["files"] if entry["path"] not in tracked} == {UNTRACKED}
    changed = {entry["path"] for entry in receipt["files"] if entry["path"] != UNTRACKED and (
        not (ROOT / entry["path"]).is_file() or sha256(entry["path"]) != entry["sha256"])}
    assert changed == CHANGED_SINCE_PR14, sorted(changed ^ CHANGED_SINCE_PR14)
    inventory = json.loads((VALIDATION / "strict-read-executable-routines.json").read_text())
    assert sha256("docs/validation/strict-read-executable-routines.json") == IA01_SHA256
    assert inventory["count"] == len(inventory["routines"]) == 1663 and len(inventory["databases"]) == 31
    evidence = (ROOT / "docs/strict-read-evidence.md").read_text()
    assert "Every one of the 1,663 routines" in evidence
    exported = json.loads((VALIDATION / "strict-read-2026-11-18.json").read_text())
    assert exported["executable_routines"] == inventory


def test_v1_inventory_carries_every_named_exception_with_a_reason():
    inventory, markdown = v1()
    signatures = {item["signature"]: item for item in inventory["routines"]}
    assert inventory["count"] == len(signatures) == len(inventory["routines"])
    for signature in NAMED:
        assert signature in signatures, signature
    assert "direct grant to demo" in signatures["megasamples_policy_loaded()"]["reason"]
    assert f"{inventory['count']} signatures" in markdown


def test_v1_inventory_regenerates_exactly_from_its_rows():
    """Every row, in both publications, is what the shared reasons give for the observed facts."""
    inventory, markdown = v1()
    facts = [{key: item[key] for key in ("signature", "name", "namespace", "kind", "volatility")}
             for item in inventory["routines"]]
    operators = {item["signature"] for item in inventory["routines"] if "operator" in item["implements"]}
    casts = {item["signature"] for item in inventory["routines"] if "cast" in item["implements"]}
    regenerated, text = routine_reasons.publication({database: facts for database in inventory["databases"]},
                                                    operators, casts, inventory["observed_at"])
    assert regenerated == inventory
    assert text == markdown
    rows = re.findall(r"^\| `(.+)` \| (.+) \|$", markdown, re.M)
    assert rows == [(item["signature"], item["reason"]) for item in inventory["routines"]]


def fact(signature, name, namespace="pg_catalog"):
    return {"signature": signature, "name": name, "namespace": namespace, "kind": "f", "volatility": "s"}


@pytest.mark.parametrize("observed, message", [
    ({"a": [fact("not_a_reviewed_name(integer)", "not_a_reviewed_name")]}, "without a reason"),
    ({"a": [fact("f()", "f", "public")]}, "without a reason"),
    ({"a": [fact("abs(integer)", "abs")], "b": []}, "differ"),
    ({"a": [fact("abs(integer)", "abs"), fact("abs(integer)", "abs")]}, "more than once"),
])
def test_v1_generator_refuses_an_incomplete_or_inconsistent_set(observed, message):
    with pytest.raises(ValueError, match=message):
        routine_reasons.publication(observed, set(), set(), "2026-11-21T00:00:00Z")


def test_v1_generator_gives_every_named_exception_its_reason():
    observed = {"a": [fact(signature, signature.split("(")[0]) for signature in NAMED]}
    inventory, _ = routine_reasons.publication(observed, set(), set(), "2026-11-21T00:00:00Z")
    assert [item["reason"] for item in inventory["routines"]] == [routine_reasons.NAMED[s] for s in NAMED]


def test_ia01_reconciliation_record_lists_every_difference():
    """tests/dl077-v1-read-profile.md's table is the v1 inventory's difference from IA-01."""
    inventory, _ = v1()
    ia01 = json.loads((VALIDATION / "strict-read-executable-routines.json").read_text())
    assert sha256("docs/validation/strict-read-executable-routines.json") == IA01_SHA256
    current = {item["signature"] for item in inventory["routines"]}
    before = {item["signature"] for item in ia01["routines"]}
    record = (ROOT / "tests/dl077-v1-read-profile.md").read_text()
    rows = re.findall(r"^\| (Added|Removed) \| `(.+?)` \| .+ \|$", record, re.M)
    assert len(rows) == len(set(rows))
    assert {s for change, s in rows if change == "Added"} == current - before
    assert {s for change, s in rows if change == "Removed"} == before - current
    assert "fresh login" not in record
