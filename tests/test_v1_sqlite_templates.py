"""The SQLite build's published templates and manifest are readable by any consumer (Astra round 2, 9)."""

import json
import sqlite3
import stat
from types import SimpleNamespace

from megasamples.sqlite_templates import stage_templates


def test_published_templates_and_manifest_are_world_readable_and_read_only(tmp_path):
    context = tmp_path / "image"
    data = context / "data"
    data.mkdir(parents=True)
    with sqlite3.connect(data / "megasamples.sqlite") as db:
        db.execute("CREATE TABLE datasets (name text, build_id text)")
        db.execute("INSERT INTO datasets VALUES ('sample', 'fixture-build')")
    with sqlite3.connect(data / "sample.sqlite") as db:
        db.execute("CREATE TABLE t (i int)")
    stage_templates(context, SimpleNamespace(templates=["sample"], namespaces=[]))
    # The build publishes beside the context and links the same files into its templates directory.
    for directory in (tmp_path, context / "templates"):
        manifest = directory / "templates.json"
        template = directory / "sample.sqlite"
        assert stat.S_IMODE(manifest.stat().st_mode) == 0o444, oct(manifest.stat().st_mode)
        assert stat.S_IMODE(template.stat().st_mode) == 0o444, oct(template.stat().st_mode)
        assert json.loads(manifest.read_text())["templates"][0]["name"] == "sample.sqlite"
