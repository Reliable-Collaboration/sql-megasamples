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
    # The space or control character is one ASCII byte (round 9, Opus 1): a non-ASCII space after `--`
    # does not open a comment, and the character starts an identifier (U+0080 and above).
    ("SELECT 1--\u3000x FROM source.t", f"SELECT 1--\u3000x FROM {T}.t"),
    ("SELECT 1--\xa0x FROM source.t", f"SELECT 1--\xa0x FROM {T}.t"),
    ("SELECT 1--\u2028x FROM source.t", f"SELECT 1--\u2028x FROM {T}.t"),
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
    # Whitespace or a comment before or after the qualifier's dot (round 9, Opus 1 and Sol 1).
    ("SELECT * FROM source . items", f"SELECT * FROM {T} . items"),
    ("SELECT * FROM source/**/.items", f"SELECT * FROM {T}/**/.items"),
    ("SELECT * FROM source /* c */ .items", f"SELECT * FROM {T} /* c */ .items"),
    ("SELECT * FROM source -- c\n.items", f"SELECT * FROM {T} -- c\n.items"),
    ("SELECT * FROM source # c\n.items", f"SELECT * FROM {T} # c\n.items"),
    ("SELECT * FROM source./* c */items", f"SELECT * FROM {T}./* c */items"),
    ("SELECT * FROM `source` /* c */ . `items`", f"SELECT * FROM {T} /* c */ . `items`"),
    # An executable comment is code, not a gap: the dot inside it still follows the name.
    ("SELECT * FROM source/*!.items*/", f"SELECT * FROM {T}/*!.items*/"),
    # Schema names are case-sensitive on this image (lower_case_table_names=0, Sol round 9, 1):
    # `SOURCE` is another schema, and is left alone.
    ("SELECT * FROM SOURCE.items", "SELECT * FROM SOURCE.items"),
    ("SELECT * FROM `Source`.items", "SELECT * FROM `Source`.items"),
]


@pytest.mark.parametrize("sql, expected", CASES)
def test_replay_rewrites_the_source_schema_in_code_only(sql, expected):
    assert definition(sql, "source", "target", False) == expected
