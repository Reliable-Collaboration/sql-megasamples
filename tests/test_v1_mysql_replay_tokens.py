"""The MySQL replay rewrites the source schema in code only, by MySQL's own lexical rules (Sol round 8, P3-8).

Each class: MySQL's `--` comment needs whitespace or a control character after it (or the end of the
statement); `#` and `/* */` comments run as documented; `/*! */` is an executable comment whose content is
code; strings and quoted identifiers follow their quoting rules; an unquoted identifier may hold `$` and
characters from U+0080, so `x$source` is one identifier, not `x$` followed by `source`.
https://dev.mysql.com/doc/refman/9.7/en/comments.html and /identifiers.html, /string-literals.html.
"""

import pytest

from megasamples.mysql_templates import definition

T = "`target`"
CASES = [
    # `--` is a comment only before whitespace, a control character or the end.
    ("SELECT 1--1 FROM source.items", f"SELECT 1--1 FROM {T}.items"),
    ("SELECT 1 --1 FROM source.items", f"SELECT 1 --1 FROM {T}.items"),
    ("SELECT --source.items.id FROM t", f"SELECT --{T}.items.id FROM t"),
    ("SELECT 1 -- source.items\nFROM source.t", f"SELECT 1 -- source.items\nFROM {T}.t"),
    ("SELECT 1 --\tsource.items\nFROM source.t", f"SELECT 1 --\tsource.items\nFROM {T}.t"),
    ("SELECT 1 --\x01source.items\nFROM source.t", f"SELECT 1 --\x01source.items\nFROM {T}.t"),
    ("SELECT 1 FROM source.t --", f"SELECT 1 FROM {T}.t --"),
    ("SELECT 1 --\r\nFROM source.t", f"SELECT 1 --\r\nFROM {T}.t"),
    # `#` to the end of the line; `/* */` to its close, across lines.
    ("SELECT 1 # source.items\nFROM source.t", f"SELECT 1 # source.items\nFROM {T}.t"),
    ("SELECT /* source.items\n source.x */ 1 FROM source.t", f"SELECT /* source.items\n source.x */ 1 FROM {T}.t"),
    # An executable comment is code.
    ("SELECT 1 FROM /*!50001 source.items */ x", f"SELECT 1 FROM /*!50001 {T}.items */ x"),
    ("SELECT 1 FROM /*! source.items */ x", f"SELECT 1 FROM /*! {T}.items */ x"),
    # Strings, with doubled quotes and backslash escapes, are not code.
    ("SELECT 'source.items', source.t.id", f"SELECT 'source.items', {T}.t.id"),
    ("SELECT 'it''s source.x', source.t.id", f"SELECT 'it''s source.x', {T}.t.id"),
    ("SELECT 'a\\' source.x', source.t.id", f"SELECT 'a\\' source.x', {T}.t.id"),
    ('SELECT "source.items", source.t.id', f'SELECT "source.items", {T}.t.id'),
    ("SELECT _utf8mb4'source.x', source.t.id", f"SELECT _utf8mb4'source.x', {T}.t.id"),
    # Quoted identifiers.
    ("SELECT * FROM `source`.`items`", f"SELECT * FROM {T}.`items`"),
    ("SELECT * FROM `sou``rce`.`items`", "SELECT * FROM `sou``rce`.`items`"),
    ("SELECT * FROM `source.items`", "SELECT * FROM `source.items`"),
    # Unquoted identifiers include `$` and U+0080 and above.
    ("SELECT x$source.id FROM t", "SELECT x$source.id FROM t"),
    ("SELECT source$x.id FROM t", "SELECT source$x.id FROM t"),
    ("SELECT ésource.id FROM t", "SELECT ésource.id FROM t"),
    ("SELECT sourceé.id FROM t", "SELECT sourceé.id FROM t"),
    # Whitespace before the qualifier's dot, and the name in any case.
    ("SELECT * FROM source . items", f"SELECT * FROM {T} . items"),
    ("SELECT * FROM SOURCE.items", f"SELECT * FROM {T}.items"),
]


@pytest.mark.parametrize("sql, expected", CASES)
def test_replay_rewrites_the_source_schema_in_code_only(sql, expected):
    assert definition(sql, "source", "target", False) == expected
