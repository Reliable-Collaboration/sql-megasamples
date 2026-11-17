"""Optional Oracle verification must select the current independently pinned clients."""
from pathlib import Path
from types import SimpleNamespace

from megasamples.sources import verify_oracle

ROOT = Path(__file__).resolve().parents[1]


def test_oracle_client_binary_selection(monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(verify_oracle.subprocess, 'run', run)
    verify_oracle.sqlplus('test_user', '', 'SELECT 1 FROM dual;')
    assert any('/usr/local/bin/megasamples-sqlplus' in args for args in calls)


def test_oracle_client_archive_versions_and_hashes():
    text = (ROOT / 'engines/oracle-client/Dockerfile').read_text()
    assert 'instantclient-basic-linux.x64-23.26.4.0.0.zip' in text
    assert 'instantclient-sqlplus-linux.x64-23.26.4.0.0.zip' in text
    assert 'instantclient-tools-linux.x64-23.26.4.0.0.zip' in text
    assert 'cab59aa3b411b3b50898e456fa9aabfe48d67e25cbc1bb23303800390ce7de26' in text
    assert '3cd43219cbaad59bb75cee18e7af074ada707446f13397b6f93ec7e4ca870490' in text
    assert '95e60dedcaf64a4ebc4dded73f5614c494a8c17fa272cd3c0485e0d13e825000' in text


def test_oracle_license_gate_precedes_any_container_action(monkeypatch):
    monkeypatch.delenv('MEGASAMPLES_ACCEPT_ORACLE_LICENSE', raising=False)
    def unexpected(*args, **kwargs):
        raise AssertionError('License refusal must not build or start any container')
    monkeypatch.setattr(verify_oracle.subprocess, 'run', unexpected)
    assert verify_oracle.main([]) == 2


def test_client_build_preserves_oracle_base_override(monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(verify_oracle.subprocess, 'run', run)
    monkeypatch.setattr(verify_oracle.container_engine, 'build_env', lambda: {})
    monkeypatch.setattr(verify_oracle, 'IMAGE', 'vendor/oracle-free:custom')
    assert verify_oracle.build_client_image() == 0
    assert any('ORACLE_IMAGE=vendor/oracle-free:custom' in args for args in calls)
