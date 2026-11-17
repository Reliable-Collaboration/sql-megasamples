"""An HTTP-200 phpMyAdmin session error must fail the console gate."""
from types import SimpleNamespace
import pytest
from megasamples import console_test


@pytest.mark.parametrize('body,expected', [
    ('<h1>phpMyAdmin - Error</h1><p>Error during session start; Permission denied</p>', 1),
    ('<table><tr><td>pubs</td></tr></table>', 0),
])
def test_console_requires_phpmyadmin_database_list(monkeypatch, body, expected):
    cfg = SimpleNamespace(consoles=['phpmyadmin'], ports={'phpmyadmin': 18081},
                          engines={'mysql': ['pubs']}, datasets=lambda _: ['pubs'])
    engine = SimpleNamespace(name='mysql', title='MySQL', container='fixture', port=3306,
                             registry_rows=lambda _: [['pubs']])
    monkeypatch.setattr(console_test.stack, 'load', lambda: cfg)
    monkeypatch.setattr(console_test, 'passwords', lambda: ('fixture-reader', 'fixture-writer'))
    monkeypatch.setattr(console_test, 'get', lambda *args, **kwargs: (200, body))
    monkeypatch.setattr(console_test.engine_registry, 'get', lambda _: engine)
    monkeypatch.setattr(console_test, 'engine_checks', lambda *args: None)
    assert console_test.main([]) == expected
