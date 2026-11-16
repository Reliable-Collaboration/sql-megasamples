"""The fetcher's fall-through: a source whose bytes are not the pinned ones gives way to the next
mirror, and a failed artifact is reported as the dataset it blocks. Sources are file:// URLs, so
nothing leaves the machine."""
import hashlib, os

from megasamples import fetch


def _art(tmp_path, art_id, good, bad):
    return {"id": art_id, "dataset": art_id.split("/")[0], "url": f"file://{bad}", "mirrors": [f"file://{good}"],
            "sha256": hashlib.sha256(open(good, "rb").read()).hexdigest(), "size_bytes": os.path.getsize(good)}


def test_a_changed_upstream_gives_way_to_the_mirror(tmp_path):
    good, bad = tmp_path / "good.csv", tmp_path / "bad.csv"
    good.write_bytes(b"id,name\n1,pinned\n")
    bad.write_bytes(b"id,name\n1,pinned\n2,added since\n")
    art = _art(tmp_path, "sample/rows.csv", str(good), str(bad))
    job = fetch.Job(art)
    dest_root = tmp_path / "downloads"
    state = fetch.fetch_one(job, str(dest_root), str(tmp_path / "manifest.yaml"), False, stall=5)
    assert state == "fetched" and "from mirror" in job.verdict
    assert (dest_root / "sample" / "rows.csv").read_bytes() == good.read_bytes()
    assert (dest_root / "sample" / "rows.csv.ok").read_text().strip() == art["sha256"]
    # the second time it is verified from disk, not fetched
    assert fetch.fetch_one(fetch.Job(art), str(dest_root), str(tmp_path / "manifest.yaml"), False, stall=5) == "cached"


def test_every_source_failing_names_each_reason(tmp_path):
    good, bad = tmp_path / "good.csv", tmp_path / "bad.csv"
    good.write_bytes(b"x"); bad.write_bytes(b"xy")
    art = _art(tmp_path, "sample/rows.csv", str(good), str(bad))
    art["mirrors"] = [f"file://{tmp_path}/missing.csv"]
    try:
        fetch.fetch_one(fetch.Job(art), str(tmp_path / "dl"), str(tmp_path / "m.yaml"), False, stall=5)
        assert False
    except RuntimeError as exc:
        assert "every source failed" in str(exc) and "size 2 != manifest size_bytes 1" in str(exc) and "missing.csv" in str(exc)


def test_a_manual_artifact_tries_its_mirror_before_asking_for_the_file(tmp_path):
    good = tmp_path / "lahman.zip"; good.write_bytes(b"zip")
    art = {"id": "lahman/lahman.zip", "dataset": "lahman", "manual": True, "url": "https://example.invalid/share",
           "mirrors": [f"file://{good}"], "sha256": hashlib.sha256(b"zip").hexdigest(), "size_bytes": 3}
    assert fetch.fetch_one(fetch.Job(art), str(tmp_path / "dl"), str(tmp_path / "m.yaml"), False, stall=5) == "fetched"
    art["mirrors"] = [f"file://{tmp_path}/not-published.zip"]
    try:
        fetch.fetch_one(fetch.Job(art), str(tmp_path / "dl2"), str(tmp_path / "m.yaml"), False, stall=5)
        assert False
    except RuntimeError as exc:
        assert "not fetchable by a script" in str(exc) and "mirror tried" in str(exc)


def test_failures_are_grouped_by_the_dataset_they_block():
    arts = [{"id": "lahman/lahman.zip", "dataset": "lahman"}, {"id": "chicago_crimes/crimes_2024.csv", "dataset": "chicago_crimes"},
            {"id": "chicago_crimes/iucr.csv", "dataset": "chicago_crimes"}]
    blocked = fetch.blocked_datasets(["lahman/lahman.zip: maintainer-supplied and not present.",
                                      "chicago_crimes/crimes_2024.csv: size 1 != manifest size_bytes 2"], arts)
    assert sorted(blocked) == ["chicago_crimes", "lahman"] and len(blocked["chicago_crimes"]) == 1


def test_manifest_repin_replaces_a_pinned_digest_and_size(tmp_path):
    m = tmp_path / "manifest.yaml"
    m.write_text('artifacts:\n  - id: a/one.csv\n    dataset: a\n    url: "x"\n    sha256: "00aa"\n    size_bytes: 10\n  - id: a/two.csv\n    dataset: a\n    url: "y"\n    sha256: ""\n    size_bytes: 0\n')
    assert fetch.write_manifest_sha(str(m), "a/one.csv", "11bb") is False          # pinned already: a first fetch does not overwrite
    assert fetch.write_manifest_sha(str(m), "a/one.csv", "11bb", replace=True) is True
    assert fetch.write_manifest_size(str(m), "a/one.csv", 12, replace=True) is True
    assert fetch.write_manifest_sha(str(m), "a/two.csv", "22cc") is True and fetch.write_manifest_size(str(m), "a/two.csv", 5) is True
    text = m.read_text()
    assert 'sha256: "11bb"' in text and "size_bytes: 12" in text and 'sha256: "22cc"' in text and "size_bytes: 5" in text
    assert text.count("- id:") == 2


def test_drift_is_accepted_only_when_asked(tmp_path, monkeypatch):
    good, moved = tmp_path / "good.csv", tmp_path / "moved.csv"
    good.write_bytes(b"a\n"); moved.write_bytes(b"a\nb\n")
    m = tmp_path / "manifest.yaml"
    m.write_text(f'artifacts:\n  - id: a/rows.csv\n    dataset: a\n    url: "file://{moved}"\n    sha256: "{hashlib.sha256(b"a\\n").hexdigest()}"\n    size_bytes: 2\n')
    art = {"id": "a/rows.csv", "dataset": "a", "url": f"file://{moved}", "mirrors": [],
           "sha256": hashlib.sha256(b"a\n").hexdigest(), "size_bytes": 2}
    monkeypatch.delenv("MEGASAMPLES_ACCEPT_DRIFT", raising=False)
    try:
        fetch.fetch_one(fetch.Job(art), str(tmp_path / "dl"), str(m), False, stall=5)
        assert False
    except RuntimeError as exc:
        assert "MEGASAMPLES_ACCEPT_DRIFT=1" in str(exc)
    monkeypatch.setenv("MEGASAMPLES_ACCEPT_DRIFT", "1")
    job = fetch.Job(art)
    assert fetch.fetch_one(job, str(tmp_path / "dl"), str(m), False, stall=5) == "fetched"
    new_digest = hashlib.sha256(b"a\nb\n").hexdigest()
    assert job.verdict.startswith("DRIFT ACCEPTED") and new_digest[:12] in job.verdict
    assert f'sha256: "{new_digest}"' in m.read_text() and "size_bytes: 4" in m.read_text()


def test_a_live_artifact_takes_what_the_feed_serves_today(tmp_path, monkeypatch):
    pinned, today = tmp_path / "pinned.csv", tmp_path / "today.csv"
    pinned.write_bytes(b"id,name\n1,then\n")
    today.write_bytes(b"id,name\n1,then\n2,amended since\n")
    art = _art(tmp_path, "portal/extract.csv", str(pinned), str(today))   # url serves today's bytes
    art["mirrors"] = []
    art["live"] = True
    dl = tmp_path / "downloads"
    job = fetch.Job(art)
    assert fetch.fetch_one(job, str(dl), str(tmp_path / "m.yaml"), False, stall=5) == "fetched"
    assert "live feed" in job.verdict and (dl / "portal" / "extract.csv").read_bytes() == today.read_bytes()
    assert (dl / "portal" / "extract.csv.ok").read_text().strip() == hashlib.sha256(today.read_bytes()).hexdigest()
    assert not (tmp_path / "m.yaml").exists()                                   # the manifest is not re-pinned
    job = fetch.Job(art)
    assert fetch.fetch_one(job, str(dl), str(tmp_path / "m.yaml"), False, stall=5) == "cached" and "live feed" in job.verdict
    today.write_bytes(b"id,name\n1,then\n2,amended since\n3,and again\n")
    monkeypatch.setenv("MEGASAMPLES_REFRESH_LIVE", "1")
    assert fetch.fetch_one(fetch.Job(art), str(dl), str(tmp_path / "m.yaml"), False, stall=5) == "fetched"
    assert (dl / "portal" / "extract.csv").read_bytes() == today.read_bytes()


def test_the_progress_line_of_a_fetched_job():
    """A fresh clone's first download crashed every worker here: `started` was never set (2026-09-16)."""
    job = fetch.Job({"id": "sample/rows.csv", "dataset": "sample", "url": "file:///x", "size_bytes": 3})
    job.verdict = "verified"
    job.finished = 10.0
    assert "in " not in fetch.final_line(job, "fetched")            # no start time: no duration, no crash
    job.started = 8.5
    assert " in 1.5s" in fetch.final_line(job, "fetched")
