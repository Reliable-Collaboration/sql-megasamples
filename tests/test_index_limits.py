"""Named native FULLTEXT limits remain explicit without suppressing other index checks."""
import pytest
from megasamples import verify
from megasamples.port import ddl, model

REASON = 'PostgreSQL tsvector exceeds its native 1 MiB limit; message bytes are preserved'


def database():
    table = model.Table('sample', 'message', indexes=[
        model.Index('ft', False, 'FULLTEXT', [('body', None)]),
        model.Index('ix', False, 'BTREE', [('body', None)]),
    ])
    return model.Database('sample', [table], [], [], [])


def test_declared_limit_is_named_and_does_not_remove_other_indexes():
    result = ddl.render(database(), 'postgres', index_omissions={'message': {'ft': REASON}})
    assert result['indexes'] == ['CREATE INDEX "message_ix" ON "message" ("body");']
    assert result['indexes_not_ported'] == {'message': {'ft': REASON}}
    assert any('message.ft: '+REASON in line for line in result['dropped'])


@pytest.mark.parametrize('omissions,dialect', [
    ({'typo': {'ft': REASON}}, 'postgres'),
    ({'message': {'typo': REASON}}, 'postgres'),
    ({'message': {'ix': REASON}}, 'postgres'),
    ({'message': {'ft': ''}}, 'postgres'),
    ({'message': {'ft': REASON}}, 'sqlite'),
])
def test_invalid_or_unexplained_limits_fail_closed(omissions, dialect):
    with pytest.raises(ValueError):
        ddl.render(database(), dialect, index_omissions=omissions)


@pytest.mark.parametrize('missing_btree', [False, True])
def test_verifier_reports_only_the_named_unsupported_index(monkeypatch, missing_btree):
    ordinary = {'type': 'BTREE', 'unique': False, 'columns': ['body']}
    expected = {'message': {'ft': {'type': 'FULLTEXT', 'unique': False, 'columns': ['body']}, 'ix': ordinary}}
    class Adapter:
        name = 'postgres'
        def tables(self, schema): return ['message']
        def indexes(self, schema): return {'message': {} if missing_btree else {'ix': ordinary}}
        def carries_index(self, spec): return True
        def indexes_not_ported(self, schema): return {'message': {'ft': REASON}}
    monkeypatch.setattr(verify, 'load_yaml', lambda path: expected)
    result = verify.Result()
    verify.stage_indexes(Adapter(), {}, 'sample', 'unused', False, result)
    assert bool(result.failures) == missing_btree
    assert any('Unsupported: message.ft' in note for note in result.notes)
    if missing_btree:
        assert result.failures == ['message: index ix missing']
