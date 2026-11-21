"""The PostgreSQL image records its own copy service row at build, so copies work as shipped.

The copy client refuses (exit 5, unidentified-volume) without the row. It is written once, in the
image's copy-roles SQL, so every start of the image, a fresh or recreated volume included, has it.
"""
import re
from types import SimpleNamespace

from megasamples.copy_config import Namespace
from megasamples.copy_server import SERVICE_TAG
from megasamples.postgres_templates import stage_roles


def test_copy_roles_sql_records_the_service_row(tmp_path):
    settings = SimpleNamespace(namespaces=[Namespace("copy", "copier", 32)], readers={}, writers={})
    stage_roles(tmp_path, settings)
    sql = (tmp_path / "copy-roles.sql").read_text()
    rows = re.findall(r"INSERT INTO copy_service VALUES \(true, '([^']+)', (.+?)\);", sql)
    assert len(rows) == 1, sql
    tag, volume = rows[0]
    assert tag == SERVICE_TAG
    assert volume == "gen_random_uuid()::text"
    assert sql.index("CREATE TABLE copy_service") < sql.index("INSERT INTO copy_service")
