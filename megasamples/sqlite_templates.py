"""Materialize the read-only SQLite files and their build manifest."""

from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile


def stage_templates(context, settings):
    directory = Path(context)
    output = directory / "templates"
    output.mkdir()
    entries = []
    with closing(sqlite3.connect(directory / "data" / "megasamples.sqlite")) as db:
        for physical in settings.templates:
            name = physical + ".sqlite"
            source = directory / "data" / name
            with tempfile.NamedTemporaryFile(dir=directory.parent, delete=False) as template:
                temporary = Path(template.name)
                try:
                    with source.open("rb") as input_file:
                        shutil.copyfileobj(input_file, template)
                    template.flush()
                    with temporary.open("rb") as copied:
                        digest = hashlib.file_digest(copied, "sha256").hexdigest()
                    size = temporary.stat().st_size
                    temporary.chmod(0o444)
                    os.replace(temporary, directory.parent / name)
                    os.link(directory.parent / name, output / name)
                finally:
                    temporary.unlink(missing_ok=True)
            row = db.execute("SELECT * FROM datasets WHERE name = ?", (physical,)).fetchone()
            build = db.execute("SELECT build_id FROM datasets WHERE name = ?", (physical,)).fetchone()[0]
            entries.append({"name": name, "size": size, "sha256": digest, "build": build,
                            "registry_digest": hashlib.sha256(json.dumps(row).encode()).hexdigest()})
            print(f"  . sqlite template {physical}: {size:,} bytes")
    manifest = {"tag": "megasamples-manifest/1", "templates": entries,
                "namespaces": {item.prefix: item.max_copies for item in settings.namespaces}}
    with tempfile.NamedTemporaryFile(dir=directory.parent, mode="w", encoding="utf-8", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(manifest, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.replace(temporary, directory.parent / "templates.json")
        finally:
            temporary.unlink(missing_ok=True)
    os.link(directory.parent / "templates.json", output / "templates.json")
