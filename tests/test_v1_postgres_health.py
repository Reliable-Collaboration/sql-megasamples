"""Opus round 3, 1, in depth: the PostgreSQL service is healthy only while read_policy is loaded."""

import yaml

from megasamples import compose, config


def test_postgres_healthcheck_requires_the_policy_library():
    cfg = config.Config({"engines": {"postgres": {"datasets": ["pubs"]}}, "consoles": []})
    probe = yaml.safe_load(compose.render(cfg))["services"]["postgres"]["healthcheck"]["test"]
    assert probe[0] == "CMD-SHELL"
    assert "current_setting('read_policy.loaded')" in probe[1]
    assert probe[1].rstrip().endswith("| grep -qx on")
