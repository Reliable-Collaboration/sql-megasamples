#!/usr/bin/env python3
"""A small T-SQL to MySQL translator for the Microsoft sample scripts (Northwind, pubs).

These scripts are SQL Server 2000 era: `GO` batch separators, `"Quoted Identifiers"`, types written
as `"int"`, `IDENTITY (1,1)`, `PRIMARY KEY CLUSTERED`, `dbo.` prefixes and `INSERT "T" VALUES(...)`
without INTO. Everything here works on a token scanner that tracks single-quoted string literals, so
no transformation can reach into data: the scripts contain apostrophes, commas, capital letters and
words like `int` inside customer names.

What it does NOT attempt: rewriting T-SQL procedural bodies. Objects whose body uses constructs with
no mechanical MySQL equivalent are reported by name so the caller can decide to port or drop them.
"""
import hashlib

from megasamples.sources import ddlutil
import re

from megasamples.sources.ddlutil import inline_identity_pk

TYPE_MAP = {
    "int": "INT", "smallint": "SMALLINT", "bigint": "BIGINT",
    # SQL Server tinyint is UNSIGNED 0..255; MySQL's plain TINYINT is signed -128..127, so an
    # unqualified mapping silently rejects any value above 127 (pubs.jobs.min_lvl hits this).
    "tinyint": "TINYINT UNSIGNED",
    "bit": "TINYINT(1)", "money": "DECIMAL(19,4)", "smallmoney": "DECIMAL(10,4)",
    "datetime": "DATETIME", "smalldatetime": "DATETIME", "float": "DOUBLE", "real": "FLOAT",
    "ntext": "TEXT", "text": "TEXT", "image": "MEDIUMBLOB", "uniqueidentifier": "CHAR(36)",
    "sysname": "VARCHAR(128)", "xml": "LONGTEXT", "date": "DATE", "time": "TIME",
    # MySQL has neither: hierarchyid keeps its raw bytes (the converter adds a decoded path column
    # beside it) and geography becomes a point in the same spatial reference system
    "hierarchyid": "VARBINARY(892)", "geography": "POINT SRID 4326",
    "datetime2": "DATETIME(6)", "datetimeoffset": "DATETIME(6)",
}
assert len(TYPE_MAP) == len(set(TYPE_MAP)), "duplicate key: the later one wins silently"
SIZED = {"nvarchar": "VARCHAR", "varchar": "VARCHAR", "nchar": "CHAR", "char": "CHAR",
         "decimal": "DECIMAL", "numeric": "DECIMAL", "binary": "BINARY", "varbinary": "VARBINARY"}

SKIP_BATCH = re.compile(
    r"^\s*(if\s+exists|set\s+(nocount|dateformat|quoted_identifier|ansi_nulls|rowcount)\b"
    r"|set\s+identity_insert|use\s+|go\s*$|--"
    # server maintenance and messaging with no MySQL equivalent; the pipeline runs its own
    # ANALYZE TABLE after loading, so UPDATE STATISTICS is redundant rather than lost
    r"|update\s+statistics\b|dbcc\b|raiserror\b|print\b|checkpoint\b"
    r"|exec(ute)?\s+sp_|create\s+type\b)", re.I)


ASCII_WORD_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
MAX_IDENT = 64          # MySQL's limit; SQL Server allows 128


def ident(name):
    """Upstream identifier -> MySQL identifier: lower case, spaces to underscores.

    A name over MySQL's 64-character limit is truncated and given a hash of the full original, so
    the result is deterministic across builds and two long names that share a prefix stay distinct.
    AdventureWorks LT has a six-column index whose name runs to 82 characters.
    """
    out = name.strip().lower().replace(" ", "_")
    if len(out) > MAX_IDENT:
        digest = hashlib.sha256(out.encode()).hexdigest()[:8]
        out = out[:MAX_IDENT - 9] + "_" + digest
    return out


def split_batches(sql):
    """Split on a line that is only GO (the batch separator), never inside a string literal.

    The literal tracking has to skip comments as well as quotes: AdventureWorks' script is full of
    lines like `-- don't` and `PRINT 'Creating ...'`, and counting an apostrophe inside a comment
    leaves the scanner believing it is inside a string, after which every GO to the next stray
    apostrophe is missed. That turned 434 batches into 12.
    """
    out, cur, in_str, in_block = [], [], False, False
    for line in sql.splitlines():
        if not in_str and not in_block and re.fullmatch(r"(?i)go", line.strip()):
            out.append("\n".join(cur)); cur = []
            continue
        cur.append(line)
        i, n = 0, len(line)
        while i < n:
            if in_block:
                if line.startswith("*/", i):
                    in_block = False; i += 2; continue
                i += 1; continue
            if in_str:
                if line[i] == "'":
                    if line.startswith("''", i):
                        i += 2; continue
                    in_str = False
                i += 1; continue
            if line.startswith("--", i):
                break                      # rest of the line is a comment
            if line.startswith("/*", i):
                in_block = True; i += 2; continue
            if line[i] == "'":
                in_str = True
            i += 1
    if cur:
        out.append("\n".join(cur))
    return [b for b in out if b.strip()]


STMT_START = re.compile(
    r"(?i)^\s*(create|insert|alter|update|delete|drop|exec(ute)?|grant|use|set|if|begin)\b")
ROUTINE_START = re.compile(r"(?i)^\s*create\s+(view|proc(edure)?|function|trigger)\b")


def split_statements(batch):
    """Split one batch into statements. T-SQL separates them by nothing but a newline, so a new
    statement begins at a line that starts with a statement keyword outside any string literal.
    A view or routine body is never split: its lines are part of one definition."""
    lines, in_str = batch.split("\n"), False
    lead = re.sub(r"(?s)^\s*(?:/\*.*?\*/|--[^\n]*\n)\s*", "", batch)
    if ROUTINE_START.match(lead):
        return [batch]
    out, cur, in_routine = [], [], False
    for n, line in enumerate(lines):
        if not in_str and not in_routine and ROUTINE_START.match(line):
            if cur and any(c.strip() for c in cur):
                out.append("\n".join(cur)); cur = []
            in_routine = True                    # its body is one definition, semicolons and all
        elif not in_str and not in_routine and STMT_START.match(line) and cur \
                and any(c.strip() for c in cur):
            out.append("\n".join(cur)); cur = []
        cur.append(line)
        quotes = 0
        j = 0
        while j < len(line):
            if line[j] == "'":
                if j + 1 < len(line) and line[j + 1] == "'":
                    j += 2; continue
                quotes += 1
            j += 1
        if quotes % 2:
            in_str = not in_str
    if cur:
        out.append("\n".join(cur))
    return [st for st in out if st.strip()]


def scan_replace(sql, on_dquote=None, on_word=None):
    """Walk sql outside string literals and comments, rewriting quoted names and bare words.

    `on_dquote` is called with (name, in_type_position). A quoted token sits in type position when
    the previous emitted token was itself an identifier, which is how a column definition reads:
    `[Col] [Type]`. Deciding by name alone is not enough -- AdventureWorks has a column named
    NameStyle whose type is also NameStyle, and treating the first one as a type eats the name.
    """
    out, i, n = [], 0, len(sql)
    prev_ident = False
    while i < n:
        ch = sql[i]
        if ch == "'":                                  # string literal: copy verbatim
            out.append(ch); i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        out.append("''"); i += 2; continue
                    out.append("'"); i += 1; break
                out.append(sql[i]); i += 1
            continue
        if ch == "`":                                  # already-emitted MySQL identifier: copy
            end = sql.find("`", i + 1)
            if end > 0:
                out.append(sql[i:end + 1]); i = end + 1; continue
        if sql.startswith("--", i):                    # line comment
            end = sql.find("\n", i); end = n if end < 0 else end
            out.append(sql[i:end]); i = end; continue
        if sql.startswith("/*", i):
            end = sql.find("*/", i + 2); end = n if end < 0 else end + 2
            out.append(sql[i:end]); i = end; continue
        if ch in '"[' and on_dquote:                   # "quoted" or [bracketed] identifier
            end = sql.find('"' if ch == '"' else "]", i + 1)
            if end > 0:
                emitted = on_dquote(sql[i + 1:end], prev_ident)
                out.append(emitted)
                prev_ident = emitted.endswith("`")
                i = end + 1
                continue
        # ASCII only: `ch.isalpha()` is true for accented letters in the data (AdventureWorks has
        # French and Spanish text), which the identifier pattern would then fail to match
        if on_word and (ch in ASCII_WORD_START):       # bare word
            word = re.match(r"[A-Za-z_][A-Za-z0-9_]*", sql[i:]).group(0)
            out.append(on_word(word)); i += len(word); prev_ident = False; continue
        if not ch.isspace():
            prev_ident = False
        out.append(ch); i += 1
    return "".join(out)


CAST_TYPES = {"money": "DECIMAL(19,4)", "smallmoney": "DECIMAL(10,4)", "int": "SIGNED",
              "integer": "SIGNED", "numeric": "DECIMAL", "decimal": "DECIMAL",
              "bigint": "SIGNED", "smallint": "SIGNED", "tinyint": "SIGNED", "bit": "SIGNED",
              "float": "DOUBLE", "real": "DOUBLE", "datetime": "DATETIME", "date": "DATE",
              "varchar": "CHAR", "nvarchar": "CHAR", "char": "CHAR", "nchar": "CHAR"}


def _cast_type(tsql_type):
    """Map a T-SQL type used as a CONVERT/CAST target to a MySQL CAST target type.

    MySQL's CAST accepts a much shorter list of types than a column declaration does: VARCHAR is not
    among them, so a character target of any width becomes CHAR(n)."""
    t = tsql_type.strip()
    m = re.match(r"(?i)^(n?(?:var)?char)\s*\(\s*(\d+)\s*\)$", t)
    if m:
        return f"CHAR({m.group(2)})"
    m = re.match(r"(?i)^(decimal|numeric)\s*\((\s*\d+\s*(?:,\s*\d+\s*)?)\)$", t)
    if m:
        return f"DECIMAL({m.group(2).replace(' ', '')})"
    return CAST_TYPES.get(t.lower(), t.upper())


# SQL Server's CONVERT date styles, as MySQL format strings. Only the six the sources actually use
# are listed; anything else is left as a CONVERT so it fails at CREATE time rather than silently.
CONVERT_STYLES = {"107": "%b %e, %Y", "111": "%Y/%m/%d", "112": "%Y%m%d",
                  "113": "%d %b %Y %H:%i:%s:%f", "121": "%Y-%m-%d %H:%i:%s.%f",
                  "126": "%Y-%m-%dT%H:%i:%s.%f"}


def convert_tsql_convert(sql):
    """`CONVERT(type, expr)` -> `CAST(expr AS type)`.

    The argument list is parsed with balanced-paren scanning rather than split on the first comma,
    because the type itself may contain one (`CONVERT(decimal(14,2), x)`)."""
    out, i, n = [], 0, len(sql)
    while i < n:
        m = re.compile(r"(?i)(?<![A-Za-z0-9_])CONVERT\s*\(").match(sql, i)
        if not m:
            out.append(sql[i]); i += 1; continue
        j, depth = m.end(), 1
        while j < n and depth:                       # find the matching close paren
            if sql[j] == "(": depth += 1
            elif sql[j] == ")": depth -= 1
            j += 1
        args = sql[m.end():j - 1]
        # first argument is a type: a word plus an optional balanced (...) group
        tm = re.match(r"(?i)\s*([A-Za-z_][A-Za-z0-9_]*\s*(?:\([^()]*\))?)\s*,", args)
        if not tm:
            out.append(sql[i:j]); i = j; continue
        rest = split_top(args[tm.end():], ",")
        if len(rest) > 2 or (len(rest) == 2 and not rest[1].strip().isdigit()):
            out.append(sql[i:j]); i = j; continue      # left alone, so it fails loudly
        if len(rest) == 2:
            # CONVERT(type, expr, style): the third argument is a date format code, and ignoring
            # it turned `CONVERT(datetime, '20040701', 112)` into `CAST( '20040701', 112 AS
            # DATETIME)` -- an expression with a stray comma and an unbalanced paren
            fmt = CONVERT_STYLES.get(rest[1].strip())
            if fmt is None:
                out.append(sql[i:j]); i = j; continue
            expr = convert_tsql_convert(rest[0])
            target = tm.group(1).strip().lower()
            out.append(f"DATE_FORMAT({expr}, '{fmt}')" if target.startswith(("char", "varchar",
                                                                             "nchar", "nvarchar"))
                       else f"STR_TO_DATE({expr}, '{fmt}')")
            i = j
            continue
        out.append(f"CAST({convert_tsql_convert(rest[0])} AS {_cast_type(tm.group(1))})")
        i = j
    return "".join(out)


LIKE_CLASS = re.compile(r"(?i)\bLIKE\s+'((?:[^']|'')*)'")


def like_pattern_to_regexp(pattern):
    """Translate a T-SQL LIKE pattern that uses [character classes] into a MySQL REGEXP.

    MySQL's LIKE has no character classes, so `LIKE '[0-9][0-9][0-9]-...'` silently matches nothing
    and a CHECK built on it would wrongly reject every row."""
    out, i, n = ["^"], 0, len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "[":
            end = pattern.find("]", i)
            if end > 0:
                out.append(pattern[i:end + 1]); i = end + 1
                # collapse an immediately repeated identical class into a {n} quantifier
                continue
        if ch == "%":
            out.append(".*")
        elif ch == "_":
            out.append(".")
        elif ch in ".^$*+?()|{}\\":
            out.append("\\" + ch)
        else:
            out.append(ch)
        i += 1
    out.append("$")
    return "".join(out)


def convert_like_classes(sql):
    """Rewrite only those LIKE patterns that actually use a character class."""
    def repl(m):
        pattern = m.group(1)
        if "[" not in pattern:
            return m.group(0)
        return "REGEXP '" + like_pattern_to_regexp(pattern) + "'"
    return LIKE_CLASS.sub(repl, sql)


NULLABILITY = re.compile(r"(?i)\s*\b(NOT\s+NULL|NULL)\s*$")


def split_alias(definition):
    """`nvarchar(50) NULL` -> ('VARCHAR(50)', 'NULL'), with the base type already mapped to MySQL."""
    definition = convert_types(definition.strip().rstrip(";").strip())
    m = NULLABILITY.search(definition)
    if not m:
        return definition, ""
    return definition[:m.start()].strip(), " ".join(m.group(1).split()).upper()


DECLARED_PK = re.compile(r"(?is)ALTER\s+TABLE\s+(?:\[?\w+\]?\s*\.\s*)*\[?(\w+)\]?\s+"
                         r"(?:WITH\s+\w+\s+)?ADD\s+(?:CONSTRAINT\s+\[?\w+\]?\s+)?"
                         r"PRIMARY\s+KEY[^(]*\(([^)]*)\)")


def collect_declared_pks(sql):
    """Primary keys the script adds with ALTER TABLE, as {table: [column, ...]}.

    An identity column has to be keyed the moment it is declared, and what key it should get depends
    on the primary key that arrives later, so that has to be known before the tables are emitted.
    """
    pks = {}
    for m in DECLARED_PK.finditer(sql):
        columns = [c.lower() for c in re.findall(r"\[?(\w+)\]?", m.group(2))
                   if c.upper() not in ("ASC", "DESC")]
        pks[ident(m.group(1))] = columns
    return pks


def collect_tsql_types(sql):
    """`CREATE TYPE [dbo].[Name] FROM nvarchar(50) NULL` -> {name: ('VARCHAR(50)', 'NULL')}."""
    types = {}
    for m in re.finditer(r"(?im)^\s*CREATE\s+TYPE\s+(?:\[?\w+\]?\s*\.\s*)?\[?(\w+)\]?\s+FROM\s+([^;\n]+)", sql):
        types[m.group(1).lower()] = split_alias(m.group(2))
    return types


def column_tail(sql, pos):
    """The rest of the column definition starting at pos: up to the comma that ends it."""
    depth = 0
    for i in range(pos, len(sql)):
        ch = sql[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return sql[pos:i]
            depth -= 1
        elif ch == "," and depth == 0:
            return sql[pos:i]
    return sql[pos:]


def split_top(text, sep):
    """Split at `sep` where it is outside both parentheses and string literals."""
    parts, depth, start, i, n = [], 0, 0, 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            i += 1
            while i < n:
                if text[i] == "'":
                    if i + 1 < n and text[i + 1] == "'":
                        i += 2; continue
                    break
                i += 1
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append(text[start:i]); start = i + 1
        i += 1
    parts.append(text[start:])
    return parts


def has_top_literal(text):
    """True when a string literal appears at the top nesting level, so a `+` here concatenates."""
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "'" and depth == 0:
            return True
    return False


def top_groups(text):
    """(open, close) index pairs of the outermost parenthesised groups, ignoring literals."""
    groups, depth, start, i, n = [], 0, None, 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "'":
            i += 1
            while i < n and text[i] != "'":
                i += 1
        elif ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                groups.append((start, i))
        i += 1
    return groups


def convert_concat(expr, stringy=()):
    """T-SQL overloads `+` for string concatenation; MySQL's `+` is always arithmetic.

    An operand tells the two apart: `N'SO' + CONVERT(...)` has a string literal at the top level of
    the expression and concatenates, while `[SubTotal] + [TaxAmt]` does not and stays as it is.
    Left alone, `'SO' + 71774` would silently evaluate to 71774 in MySQL rather than 'SO71774'.

    Inside a routine body there is a second tell, and it is needed: `REPLICATE('0', n) + @Value`
    has no top-level literal, but `@Value` was DECLAREd `varchar`. `stringy` carries the names of
    the character-typed locals and parameters, and an operand that is exactly one of them counts.
    The test is deliberately narrow -- a bare name, not a name appearing anywhere in a subexpression
    -- so that `8 - LENGTH(@Value)` stays arithmetic.
    """
    parts = split_top(expr, "+")
    if len(parts) > 1 and any(has_top_literal(p) or p.strip().strip("()").strip().lower() in stringy
                              for p in parts):
        return "CONCAT(" + ", ".join(convert_concat(p.strip(), stringy) for p in parts) + ")"
    out, i = [], 0
    for start, end in top_groups(expr):
        out.append(expr[i:start + 1])
        out.append(", ".join(_concat_operand(a.strip(), stringy)
                             for a in split_top(expr[start + 1:end], ",")))
        out.append(")")
        i = end + 1
    out.append(expr[i:])
    return "".join(out)


def convert_view_concat(sql):
    """Rewrite string additions as expressions, preserving the surrounding view statement.

    The expression-only helper cannot distinguish a SELECT item from the rest of a statement:
    a literal in CASE can otherwise turn CREATE VIEW and unrelated numeric additions into CONCAT
    arguments. Parse the already translated MySQL syntax and inspect each addition separately.
    """
    import sqlglot
    from sqlglot import exp

    if xml_blockers(sql):
        return sql  # the caller reports these existing, explicit conversion exceptions

    def string_value(node):
        if isinstance(node, exp.Literal):
            return node.is_string
        if isinstance(node, exp.Paren):
            return string_value(node.this)
        if isinstance(node, exp.Cast):
            return node.to.this.value.upper() in {"CHAR", "NCHAR", "VARCHAR", "NVARCHAR", "TEXT"}
        if isinstance(node, exp.Case):
            # WHEN conditions say nothing about the result's type.
            values = [item.args.get("true") for item in node.args.get("ifs", [])]
            values.append(node.args.get("default"))
            return any(value is not None and string_value(value) for value in values)
        return node.key in {"concat", "concatws", "left", "right", "substring", "repeat", "lower", "upper", "trim"}

    tree = sqlglot.parse_one(normalize_comments(sql), read="mysql")
    for node in reversed(list(tree.walk())):
        if isinstance(node, exp.Add) and (string_value(node.this) or string_value(node.expression)):
            operands = []
            for child in (node.this, node.expression):
                operands.extend(child.expressions if isinstance(child, exp.Concat) else [child])
            node.replace(exp.Concat(expressions=[child.copy() for child in operands]))
    return tree.sql(dialect="mysql")


AS_TYPE = re.compile(r"(?is)^(.*?)(\s+AS\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:\([^()]*\))?\s*)$")


def _concat_operand(part, stringy):
    """One argument of a call, with `CAST(x AS type)`'s type kept out of the concatenation.

    `CAST('0' + CAST(n AS CHAR) AS CHAR(2))` splits on `+` into `'0'` and
    `CAST(n AS CHAR) AS CHAR(2)`, and joining those with CONCAT swallows the outer cast's target
    type. The trailing `AS <type>` is separated first and put back afterwards.
    """
    m = AS_TYPE.match(part)
    if m and split_top(m.group(1), "+")[1:]:
        return convert_concat(m.group(1).strip(), stringy) + m.group(2)
    return convert_concat(part, stringy)


COMPUTED = re.compile(r"(?i)(?:^|,)\s*`(\w+)`\s+AS\s+")


def convert_computed(body, computed_types, materialize=()):
    """`[LineTotal] AS ISNULL(...)` -> `` `linetotal` DECIMAL(38,6) AS (IFNULL(...)) STORED ``.

    T-SQL infers a computed column's type; MySQL requires one to be declared, so the caller supplies
    it per `table.column` from the dataset record. Returns the body and the generated column names,
    which the caller must leave out of INSERT column lists.

    A column named in `materialize` becomes an ordinary column instead, for expressions MySQL will
    not generate -- it rejects a generated column that reads an AUTO_INCREMENT column. Its value
    then has to come from the data, so it stays in the INSERT column list.
    """
    table = re.search(r"(?is)^\s*CREATE\s+TABLE\s+`([^`]+)`", body)
    if not table:
        return body, []
    generated, out, pos = [], [], 0
    for m in COMPUTED.finditer(body):
        column = m.group(1)
        key = f"{table.group(1)}.{column}".lower()
        if key not in computed_types:
            raise SystemExit(f"computed column {key} has no declared MySQL type")
        expression = column_tail(body, m.end()).strip()
        # SQL Server writes the attributes after the expression: PERSISTED means stored, which these
        # columns already are, and a nullability keyword belongs after STORED in MySQL
        attributes = ""
        while True:
            trimmed = re.sub(r"(?i)\s+(PERSISTED|NOT\s+NULL|NULL)\s*$", "", expression)
            if trimmed == expression:
                break
            keyword = expression[len(trimmed):].strip()
            if keyword.upper() != "PERSISTED":
                attributes = " " + " ".join(keyword.split()).upper() + attributes
            expression = trimmed
        out.append(body[pos:m.start(1) - 1])
        pos = m.end() + len(column_tail(body, m.end()))
        if key in materialize:
            out.append(f"`{column}` {computed_types[key]}")
            continue
        # N'x' is a national-character literal; MySQL's utf8mb4 columns make the prefix redundant
        expression = re.sub(r"(?<![A-Za-z0-9_])N'", "'", expression)
        expression = convert_concat(convert_functions(convert_tsql_convert(expression)))
        out.append(f"`{column}` {computed_types[key]} AS ({expression}) STORED{attributes}")
        generated.append(column)
    out.append(body[pos:])
    return "".join(out), generated


def expand_alias_types(sql, types):
    """Replace a user-defined type used as a column type with its base definition.

    T-SQL lets the column override the alias's nullability, so the alias only supplies NULL/NOT NULL
    when the column declares none. Emitting both produces `VARCHAR(50) NULL NOT NULL`, which MySQL
    rejects -- AdventureWorks LT's [Name] alias hits this on nearly every table.
    """
    for name, (base, nullability) in types.items():
        def repl(m, base=base, nullability=nullability):
            tail = column_tail(sql, m.end())
            if nullability and not re.search(r"(?i)\bNULL\b", tail):
                return f"{m.group(1)}{base} {nullability}"
            return m.group(1) + base
        sql = re.sub(rf"(?i)(`\w+`\s+)(?:`dbo`\s*\.\s*)?{name}(?![A-Za-z0-9_(])", repl, sql)
    return sql


def collect_udts(sql):
    """`execute sp_addtype name, 'basetype', 'NOT NULL'` -> {name: ('BASETYPE', 'NOT NULL')}."""
    udts = {}
    for m in re.finditer(r"(?im)^\s*exec(?:ute)?\s+sp_addtype\s+(\w+)\s*,\s*'([^']+)'\s*(?:,\s*'([^']*)')?", sql):
        name, base, nullability = m.group(1), m.group(2), (m.group(3) or "")
        udts[name.lower()] = split_alias(f"{base.strip()} {nullability.strip()}".strip())
    return udts


# T-SQL date parts and their MySQL interval units
DATE_PARTS = {"yy": "YEAR", "yyyy": "YEAR", "year": "YEAR",
              "qq": "QUARTER", "q": "QUARTER", "quarter": "QUARTER",
              "mm": "MONTH", "m": "MONTH", "month": "MONTH",
              "dy": "DAY", "y": "DAY", "dayofyear": "DAY",
              "dd": "DAY", "d": "DAY", "day": "DAY",
              "wk": "WEEK", "ww": "WEEK", "week": "WEEK",
              "hh": "HOUR", "hour": "HOUR",
              "mi": "MINUTE", "n": "MINUTE", "minute": "MINUTE",
              "ss": "SECOND", "s": "SECOND", "second": "SECOND",
              # MySQL has no MILLISECOND interval unit. Mapping ms straight onto MICROSECOND is a
              # thousandfold error: DATEADD(ms, -2, x) means two milliseconds, not two microseconds.
              "ms": "MILLISECOND", "millisecond": "MILLISECOND"}
MILLISECOND = "MILLISECOND"


CAST_TARGET = re.compile(r"(?i)\bCAST\s*\(")


def convert_cast_targets(sql):
    """Rewrite the target type of a literal `CAST(x AS type)` to one MySQL's CAST accepts.

    MySQL's CAST takes a much shorter list than a column declaration: INTEGER, VARCHAR and the rest
    are rejected outright, so a view written for SQL Server fails on the type name alone.
    """
    out, i = [], 0
    while i < len(sql):
        m = CAST_TARGET.search(sql, i)
        if not m:
            out.append(sql[i:]); break
        depth, j = 1, m.end()
        while j < len(sql) and depth:
            depth += {"(": 1, ")": -1}.get(sql[j], 0)
            j += 1
        inner = sql[m.end():j - 1]
        parts = re.split(r"(?i)\s+AS\s+(?=[A-Za-z_][A-Za-z0-9_]*\s*(?:\([^()]*\))?\s*$)", inner)
        out.append(sql[i:m.start()])
        if len(parts) == 2:
            out.append(f"CAST({parts[0]} AS {_cast_type(parts[1])})")
        else:
            out.append(sql[m.start():j])
        i = j
    return "".join(out)


DATENAME_TEXT = {"MONTH": "MONTHNAME({x})", "WEEKDAY": "DAYNAME({x})"}


def convert_date_functions(sql):
    """`DATEDIFF(yy, a, b)` -> `TIMESTAMPDIFF(YEAR, a, b)`, `DATEADD(dd, n, d)` -> `DATE_ADD(...)`,
    `DATENAME(yy, d)` -> `CAST(YEAR(d) AS CHAR)`.

    MySQL has a `DATEDIFF` of its own but it takes two arguments and returns days, so T-SQL's
    three-argument form does not fail loudly everywhere -- with a two-argument call it would silently
    mean something else. Both are rewritten to the MySQL function that takes a unit. `DATENAME`
    returns the part as text: the month's and the weekday's names, every other part as its number.
    """
    for name in ("DATEDIFF", "DATEADD", "DATENAME"):
        out, i = [], 0
        pattern = re.compile(rf"(?i)(?<![A-Za-z0-9_]){name}\s*\(")
        while i < len(sql):
            m = pattern.search(sql, i)
            if not m:
                out.append(sql[i:]); break
            depth, j = 1, m.end()
            while j < len(sql) and depth:
                depth += {"(": 1, ")": -1}.get(sql[j], 0)
                j += 1
            args = [a.strip() for a in split_top(sql[m.end():j - 1], ",")]
            wanted = 2 if name == "DATENAME" else 3
            part = args[0].strip("[]`\"' ").lower()
            unit = (DATE_PARTS.get(part) or ("WEEKDAY" if part in ("dw", "weekday", "w") else None)) if len(args) == wanted else None
            out.append(sql[i:m.start()])
            if name == "DATENAME" and unit in DATENAME_TEXT:
                out.append(DATENAME_TEXT[unit].format(x=args[1]))
            elif name == "DATENAME" and unit and unit != MILLISECOND:
                out.append(f"CAST(EXTRACT({unit} FROM {args[1]}) AS CHAR)")
            elif name == "DATENAME":
                out.append(sql[m.start():j])
            elif unit == MILLISECOND and name == "DATEDIFF":
                out.append(f"(TIMESTAMPDIFF(MICROSECOND, {args[1]}, {args[2]}) / 1000)")
            elif unit == MILLISECOND:
                out.append(f"DATE_ADD({args[2]}, INTERVAL ({args[1]}) * 1000 MICROSECOND)")
            elif unit and name == "DATEDIFF":
                out.append(f"TIMESTAMPDIFF({unit}, {args[1]}, {args[2]})")
            elif unit:
                out.append(f"DATE_ADD({args[2]}, INTERVAL {args[1]} {unit})")
            else:
                out.append(sql[m.start():j])
            i = j
        sql = "".join(out)
    return sql


def convert_functions(sql):
    """Map SQL Server built-ins to their MySQL equivalents.

    CURRENT_TIMESTAMP is used rather than NOW() because it is also legal in a DEFAULT clause, which
    is where getdate() most often appears."""
    sql = re.sub(r"(?i)\bGETDATE\s*\(\s*\)", "CURRENT_TIMESTAMP", sql)
    sql = re.sub(r"(?i)\bGETUTCDATE\s*\(\s*\)", "UTC_TIMESTAMP", sql)
    sql = re.sub(r"(?i)\bISNULL\s*\(", "IFNULL(", sql)
    sql = re.sub(r"(?i)\bLEN\s*\(", "CHAR_LENGTH(", sql)
    return sql


SELECT_ALIAS = re.compile(r"(?s)^\s*(?:`(\w+)`|\[(\w+)\]|\b(\w+)\b)\s*=\s*(?![=<>])(.+)$")


def convert_select_aliases(sql):
    """T-SQL's `Alias = expression` in a select list -> `expression AS Alias`.

    MySQL has only the AS form, and reads `stateprovincename = sp.name` as a comparison, so the
    column vanishes and the query fails on the missing name. Only the region between SELECT and its
    FROM is rewritten, and only where the left side is a bare identifier.
    """
    out, pos = [], 0
    for m in re.finditer(r"(?is)\bSELECT\b", sql):
        if m.start() < pos:
            continue
        depth, i, end = 0, m.end(), None
        while i < len(sql):
            ch = sql[i]
            if ch == "'":
                i += 1
                while i < len(sql) and sql[i] != "'":
                    i += 1
            elif ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    end = i
                    break
                depth -= 1
            elif depth == 0 and re.match(r"(?i)\bFROM\b", sql[i:i + 4]) and not sql[i - 1].isalnum():
                end = i
                break
            i += 1
        if end is None:
            break
        items = split_top(sql[m.end():end], ",")
        rewritten = []
        for item in items:
            a = SELECT_ALIAS.match(item)
            if a:
                name = a.group(1) or a.group(2) or a.group(3)
                rewritten.append(f" {a.group(4).strip()} AS `{name}`")
            else:
                rewritten.append(item)
        out.append(sql[pos:m.end()])
        out.append(",".join(rewritten))
        pos = end
    out.append(sql[pos:])
    return "".join(out)


# a line comment may sit between the column list and AS, as in AdventureWorks' bill-of-materials
CTE_HEAD = re.compile(r"(?i)\bWITH\s+(`?\w+`?)\s*(?:\([^()]*\))?(?:\s*--[^\n]*\n)*\s*AS\s*\(")


def convert_recursive_cte(sql):
    """MySQL needs WITH RECURSIVE where T-SQL just writes WITH.

    Without it a self-referencing CTE fails with "table doesn't exist" on its own name, which is how
    AdventureWorks LT's vGetAllCategories reads the product category tree.
    """
    m = CTE_HEAD.search(sql)
    if not m:
        return sql
    name, depth, i = m.group(1).strip("`"), 1, m.end()
    while i < len(sql) and depth:
        depth += {"(": 1, ")": -1}.get(sql[i], 0)
        i += 1
    if not re.search(rf"(?i)\b{re.escape(name)}\b", sql[m.end():i - 1]):
        return sql
    return sql[:m.start()] + re.sub(r"(?i)^WITH\b", "WITH RECURSIVE", sql[m.start():], count=1)


# the column may carry a table alias: `s.[Demographics].value(...)`
XML_VALUE = re.compile(r"(?is)((?:`?\w+`?\s*\.\s*)?`?\w+`?)\.value\s*\("
                       r"\s*N?'((?:[^']|'')*)'\s*,\s*'([^']*)'\s*\)")
XML_METHOD = re.compile(r"(?i)`?\w+`?\.(query|exist|nodes|modify)\s*\(")


# T-SQL constructs with no MySQL equivalent at all; a view or routine using one cannot be ported
BLOCKERS = [(re.compile(r"(?i)\bPIVOT\s*\("), "PIVOT"),
            (re.compile(r"(?i)\bUNPIVOT\s*\("), "UNPIVOT"),
            (re.compile(r"(?i)\b(CROSS|OUTER)\s+APPLY\b"), "APPLY"),
            (re.compile(r"(?i)\bFOR\s+XML\b"), "FOR XML"),
            (re.compile(r"(?i)\bOPENXML\s*\("), "OPENXML"),
            (re.compile(r"(?i)\bTABLESAMPLE\b"), "TABLESAMPLE")]


def xml_blockers(sql):
    """Constructs with no MySQL equivalent. XML `.value()` is handled; these are not.

    Reported so the caller can drop the object with a reason rather than emit something that parses
    but does not do what its name says.
    """
    found = {f".{m.group(1)}()" for m in XML_METHOD.finditer(sql)}
    found |= {label for pattern, label in BLOCKERS if pattern.search(sql)}
    return sorted(found)
DECLARE_NS = re.compile(r'(?is)\s*declare\s+(?:default\s+element\s+namespace|namespace\s+[\w-]+)'
                        r'\s*=?\s*"[^"]*"\s*;')


def convert_xml_value(sql):
    """SQL Server's `col.value('xquery', 'type')` -> MySQL's `ExtractValue(col, 'xpath')`.

    MySQL has no XQuery and its XPath subset has no namespace support -- `local-name()` is not in the
    grammar. It does match a prefixed element name literally, though, and AdventureWorks' catalog
    documents use the same prefixes the queries declare (p1, wm, wf, html), so dropping the
    `declare namespace` preamble and keeping the path as written selects the same nodes. The
    `(path)[1]` form becomes `path[1]`, which MySQL's grammar does accept, and a sized result type
    becomes a CAST so the column is truncated the way SQL Server truncates it.
    """
    def one(m):
        column, xquery, result = m.group(1), m.group(2), m.group(3).strip()
        path = DECLARE_NS.sub("", xquery).strip()
        outer = re.match(r"^\((.*)\)(\[\d+\])$", path, re.S)
        if outer:
            path = outer.group(1).strip() + outer.group(2)
        path = " ".join(path.split())
        expression = f"ExtractValue({column}, '{path}')"
        size = re.match(r"(?i)^n?(?:var)?char\s*\(\s*(\d+)\s*\)$", result)
        return f"CAST({expression} AS CHAR({size.group(1)}))" if size else expression

    return XML_VALUE.sub(one, sql)


INLINE_REF = re.compile(r"(?i)\s+REFERENCES\s+(`?\w+`?)\s*\(\s*(`?\w+`?)\s*\)")


NONDETERMINISTIC = re.compile(r"(?i)\b(CURRENT_TIMESTAMP|NOW|UTC_TIMESTAMP|CURDATE|CURTIME|RAND"
                              r"|UUID|SYSDATE)\b")
CHECK_CLAUSE = re.compile(r"(?is),?\s*(?:CONSTRAINT\s+`([^`]+)`\s+)?CHECK\s*\(")


def drop_nondeterministic_checks(sql):
    """Remove CHECK constraints whose expression is not deterministic.

    MySQL rejects them outright ("contains disallowed function"), and AdventureWorks has several of
    the form `BirthDate BETWEEN '1930-01-01' AND DATEADD(YEAR, -18, GETDATE())`. Returns the SQL and
    the names dropped, so the caller can say what went.
    """
    dropped, out, pos = [], [], 0
    for m in CHECK_CLAUSE.finditer(sql):
        if m.start() < pos:
            continue
        depth, i = 1, m.end()
        while i < len(sql) and depth:
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        clause = sql[m.start():i]
        if not NONDETERMINISTIC.search(clause):
            continue
        out.append(sql[pos:m.start()])
        dropped.append(m.group(1) or "unnamed")
        pos = i
    out.append(sql[pos:])
    return "".join(out), dropped


CONSTRAINT_LINE = re.compile(r"(?i)^\s*(CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)\b")


def comma_before_constraints(create_table):
    """Put back a comma the upstream script omits before a table-level constraint.

    Contoso's own DDL writes `[CurrencyCode] [nvarchar](5) NOT NULL` and then, with no comma,
    `CONSTRAINT [PK_Orders] PRIMARY KEY ...`. MySQL will not have it.

    Opt-in, because the same shape is legitimate elsewhere: pubs writes a column-level PRIMARY KEY on
    its own line as a continuation of the column above it, where a comma would break the statement.
    """
    lines, out = create_table.split("\n"), []
    for line in lines:
        if CONSTRAINT_LINE.match(line):
            previous = next((i for i in range(len(out) - 1, -1, -1) if out[i].strip()), None)
            if previous is not None:
                text = out[previous].rstrip()
                if text and text[-1] not in ",(":
                    out[previous] = text + ","
        out.append(line)
    return "\n".join(out)


def hoist_inline_references(create_table):
    """Turn column-level `REFERENCES t(c)` into table-level FOREIGN KEY clauses.

    MySQL "parses but ignores inline REFERENCES specifications" (they are accepted and then do
    nothing), so a script that declares all of its foreign keys inline -- as pubs does, with ten of
    them and no ALTER TABLE at all -- would produce a database with no foreign keys whatsoever.
    """
    lines, hoisted = create_table.split("\n"), []
    for idx, line in enumerate(lines):
        m = INLINE_REF.search(line)
        if not m:
            continue
        col = re.match(r"\s*(`?[\w ]+?`?)\s+\S", line)
        if not col:
            continue
        lines[idx] = INLINE_REF.sub("", line)
        hoisted.append(f"\tFOREIGN KEY ({col.group(1)}) REFERENCES {m.group(1)} ({m.group(2)})")
    if not hoisted:
        return create_table, 0
    body = "\n".join(lines)
    close = body.rfind(")")
    head = body[:close].rstrip().rstrip(",")
    return head + ",\n" + ",\n".join(hoisted) + "\n" + body[close:], len(hoisted)


def strip_money_literals(sql):
    """T-SQL writes money literals as `$20.00`; MySQL reads that as an identifier.

    Applied only outside string literals, so a dollar sign inside data is preserved."""
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            out.append(ch); i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        out.append("''"); i += 2; continue
                    out.append("'"); i += 1; break
                out.append(sql[i]); i += 1
            continue
        if ch == "$" and i + 1 < n and (sql[i + 1].isdigit() or sql[i + 1] in "-."):
            i += 1; continue                      # drop the currency prefix, keep the number
        out.append(ch); i += 1
    return "".join(out)


COL_LINE = re.compile(r"^\s*(`[^`]+`|\w+)\s+(?=[A-Za-z])")
NOT_A_COLUMN = re.compile(r"(?i)^\s*(constraint|primary|foreign|unique|check|key|index)\b")


def parse_columns(create_table):
    """Return (all column names, the AUTO_INCREMENT column or None) for a CREATE TABLE statement."""
    open_paren = create_table.find("(")
    if open_paren < 0:
        return [], None
    cols, identity = [], None
    for line in create_table[open_paren + 1:].split("\n"):
        if NOT_A_COLUMN.match(line):
            continue
        m = COL_LINE.match(line)
        if not m:
            continue
        name = m.group(1)
        cols.append(name)
        if re.search(r"(?i)\bAUTO_INCREMENT\b", line):
            identity = name
    return cols, identity


def add_column_list(insert_sql, columns, identity):
    """T-SQL omits an identity column from `INSERT ... VALUES`; MySQL needs the count to match."""
    listed = [c for c in columns if c != identity]
    return re.sub(r"(?i)^(\s*INSERT\s+INTO\s+(?:`[^`]+`|\w+))(\s+VALUES\b)",
                  lambda m: f"{m.group(1)} ({', '.join(listed)}){m.group(2)}", insert_sql, count=1)


def normalize_comments(sql):
    """MySQL needs whitespace after `--` to treat it as a comment; T-SQL does not.

    An upstream `--ORDER BY City` is a comment in SQL Server and a syntax error in MySQL, and
    AdventureWorks writes trailing ones too (`quotadate --,`), so this scans rather than working line
    by line. String literals are skipped: a `--` inside one is data.
    """
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":                                   # string literal, copied verbatim
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2; continue
                    break
                j += 1
            out.append(sql[i:j + 1]); i = j + 1; continue
        if sql.startswith("/*", i):                     # block comment, copied verbatim
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(sql[i:j]); i = j; continue
        if sql.startswith("--", i):
            rest = sql[i + 2:i + 3]
            out.append("-- " if rest and rest not in " \t-" else "--")
            i += 2
            continue
        out.append(ch); i += 1
    return "".join(out)


def terminate(sql):
    """Append the statement terminator after the last line of code, not after a trailing comment.

    Several batches end with an explanatory `-- comment` line; putting the semicolon there comments
    it out and silently merges the statement with the next one."""
    lines = normalize_comments(sql).rstrip().split("\n")
    last = max((i for i, l in enumerate(lines)
                if l.strip() and not l.strip().startswith("--")), default=len(lines) - 1)
    lines[last] = lines[last].rstrip().rstrip(";") + ";"
    return "\n".join(lines) + "\n"


def strip_schemas(sql, schemas=("dbo",)):
    """Fold a schema qualifier into the object name, in either T-SQL quoting style.

    MySQL has no schema level below the database. `schemas` is either a sequence of schema names to
    drop outright (a single-schema dataset such as AdventureWorks LT, where SalesLT and dbo do not
    collide) or a mapping of schema name to the prefix its objects take -- `{"person": "person_",
    "dbo": ""}` turns `[Person].[Address]` into `person_address` and leaves `dbo` tables unprefixed,
    which is the naming decision for multi-schema databases. Left in place a qualifier becomes a
    database reference and the load fails with "Unknown database".
    """
    mapping = schemas if isinstance(schemas, dict) else {s: "" for s in schemas}
    for schema, prefix in mapping.items():
        # the object may be bare, "quoted" or [bracketed], and a quoted name may contain spaces
        # ("dbo"."Order Details"), so its own quoting is preserved when the qualifier is dropped
        pattern = (rf'(?i)(?:"{re.escape(schema)}"|\[{re.escape(schema)}\]|\b{re.escape(schema)}\b)'
                   r'\s*\.\s*(?:"([^"]+)"|\[([^\]]+)\]|(\w+))')

        def fold(m, prefix=prefix):
            quoted, bracketed, bare = m.groups()
            name = quoted or bracketed or bare
            if not prefix:
                return f'"{name}"' if quoted else (f"[{name}]" if bracketed else name)
            return f"[{prefix}{name}]"

        sql = re.sub(pattern, fold, sql)
    return sql


def convert_types(sql):
    """Map SQL Server column types. Types may appear double-quoted (`"int"`), already unquoted here."""
    # SQL Server's MAX length (2 GB) has no size argument in MySQL; LONGTEXT/LONGBLOB are the
    # closest equivalents. AdventureWorks LT uses varbinary(max) for product photos.
    sql = re.sub(r"(?i)\b(?:n?varchar|n?text)\s*\(\s*max\s*\)", "LONGTEXT", sql)
    sql = re.sub(r"(?i)\b(?:var)?binary\s*\(\s*max\s*\)", "LONGBLOB", sql)
    # MySQL has no XML type. A typed XML column names its schema collection, which goes with it.
    sql = re.sub(r"(?i)\bxml\s*\(\s*`?[\w.`]+`?\s*\)", "LONGTEXT", sql)

    def sized(m):
        return f"{SIZED[m.group(1).lower()]}({m.group(2)})"
    sql = re.sub(r"(?i)\b(" + "|".join(SIZED) + r")\s*\(\s*([0-9]+(?:\s*,\s*[0-9]+)?)\s*\)", sized, sql)
    for src, dst in TYPE_MAP.items():
        sql = re.sub(rf"(?i)(?<![A-Za-z0-9_`]){src}(?![A-Za-z0-9_(])", dst, sql)
    # bare nvarchar/nchar with no length
    sql = re.sub(r"(?i)(?<![A-Za-z0-9_`])nvarchar(?![A-Za-z0-9_(])", "VARCHAR(255)", sql)
    sql = re.sub(r"(?i)(?<![A-Za-z0-9_`])nchar(?![A-Za-z0-9_(])", "CHAR(1)", sql)
    return sql


DATE_MDY = re.compile(r"'(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})'")


def convert_dates_mdy(sql):
    """Rewrite `'MM/DD/YYYY'` literals to ISO, as `SET DATEFORMAT mdy` in the script requires.

    This is the one transformation that deliberately reaches inside string literals, so the pattern
    is anchored to a whole quoted value in exactly that shape: a phone number or address containing
    a slash cannot match, and MySQL cannot parse the mdy form at all."""
    def iso(m):
        month, day, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if len(year) == 2:
            # SQL Server's default two-digit year cutoff is 2049: 00-49 -> 20xx, 50-99 -> 19xx
            year = f"20{year}" if int(year) <= 49 else f"19{year}"
        return f"'{year}-{month:02d}-{day:02d}'"
    return DATE_MDY.sub(iso, sql)


def translate(sql, drop_checks=(), keep_objects=True, dateformat=None, schemas=("dbo",),
              computed_types=None, materialize=(), fix_missing_commas=False):
    """Return (statements, name_map, notes). `drop_checks` names CHECK constraints to omit."""
    name_map, notes, statements = {}, [], []
    identity_pk = {}     # table -> column that already carries PRIMARY KEY with its identity
    udts = collect_udts(sql)
    # the schema qualifier is folded first: the primary keys are declared as `ALTER TABLE
    # [Person].[EmailAddress]` while the table is created as `person_emailaddress`, and a lookup on
    # the unfolded name silently finds nothing
    declared_pk = collect_declared_pks(strip_schemas(sql, schemas))
    tsql_types = collect_tsql_types(sql)

    if tsql_types:
        notes.append(f"expanded CREATE TYPE aliases: {', '.join(sorted(tsql_types))}")
    if udts:
        notes.append(f"expanded user-defined types: {', '.join(sorted(udts))}")
    tables = {}          # lower-cased upstream table name -> MySQL identifier
    table_columns = {}   # lower-cased table name -> (columns, identity column)

    # a double-quoted or bracketed token naming a type is a type, not an identifier -- including
    # the script's own CREATE TYPE aliases, which are collected before the scan for this reason
    TYPE_WORDS = set(TYPE_MAP) | set(SIZED) | set(tsql_types)

    def dq(name, in_type_position=False):
        if in_type_position and name.strip().lower() in TYPE_WORDS:
            return name.strip().lower()      # `[Col] [int]`: the second token is the type
        mapped = ident(name)
        if name != mapped:
            name_map[name] = mapped
        return f"`{mapped}`"

    for batch in split_batches(sql):
      for batch in split_statements(batch):
        head = batch.strip()
        if SKIP_BATCH.match(head) or not re.sub(r"(?s)/\*.*?\*/|--[^\n]*", "", head).strip():
            continue
        # enabling or disabling a constraint, by name or with ALL, has no MySQL analogue: the
        # constraint either exists or it does not
        # the table name may be quoted and contain spaces ("Order Details"), so the span between
        # it and the keyword is matched loosely but bounded
        if re.match(r"(?i)^\s*alter\s+table\s+.{0,80}?\b(no)?check\s+constraint\b", head, re.S):
            continue
        # PRINT is progress messaging. It is skipped as a statement of its own, but AdventureWorks
        # also puts one directly after a statement in the same batch, where it would be emitted.
        batch = re.sub(r"(?im)^[ \t]*PRINT\s+[^;]*;[ \t]*$", "", batch)
        body = strip_schemas(batch, schemas)
        # classify on the first real statement: several batches open with a block comment
        lead = re.sub(r"(?s)^\s*(?:/\*.*?\*/|--[^\n]*\n)+\s*", "", body)
        kind = "other"
        if re.match(r"(?i)^\s*create\s+table", lead): kind = "table"
        elif re.match(r"(?i)^\s*create\s+view", lead): kind = "view"
        elif re.match(r"(?i)^\s*create\s+proc", lead): kind = "procedure"
        elif re.match(r"(?i)^\s*create\s+trigger", lead): kind = "trigger"
        elif re.match(r"(?i)^\s*create\s+function", lead): kind = "function"
        elif re.match(r"(?i)^\s*alter\s+table", lead): kind = "constraint"
        elif re.match(r"(?i)^\s*(insert|update|delete)", lead): kind = "dml"

        body = scan_replace(body, on_dquote=dq)
        if kind in ("table", "view"):
            # views join the map too: AdventureWorks DW's vTimeSeries selects `FROM vDMPrep`
            # unquoted, and MySQL is case-sensitive for view names as well as table names
            m = re.search(rf"(?i)CREATE\s+(?:OR\s+REPLACE\s+)?{kind.upper()}\s+(?:`([^`]+)`|(\w+))",
                          body)
            if m:
                tname = m.group(1) or m.group(2)
                tables[tname.lower()] = tname
        if kind in ("view", "procedure", "constraint", "dml", "trigger", "function", "other"):
            # bare (unquoted) references to a table must be lower-cased too -- CREATE INDEX names
            # its table bare in the Northwind script, and its statements are classified "other"
            body = scan_replace(body, on_word=lambda w: f"`{tables[w.lower()]}`" if w.lower() in tables else w)
        # filegroup placement and index-organisation keywords have no MySQL equivalent, and they
        # appear on CREATE INDEX as well as on tables and constraints
        body = re.sub(r"(?i)\s+(?:TEXTIMAGE_ON|FILESTREAM_ON)\s+`?\w+`?", "", body)
        body = re.sub(r"(?i)\s+ON\s+`primary`", "", body)
        body = re.sub(r"(?i)\b(?:NON)?CLUSTERED\s+(?=INDEX\b)", "", body)
        body = re.sub(r"(?i)\b(PRIMARY\s+KEY|UNIQUE)\s+(?:NON)?CLUSTERED", r"\1", body)
        # a covering index: MySQL has no INCLUDE, and an InnoDB secondary index already carries the
        # primary key, so the clause goes rather than the included columns joining the key
        body = re.sub(r"(?is)\s+INCLUDE\s*\([^)]*\)", "", body)
        # index storage options (PAD_INDEX, ALLOW_PAGE_LOCKS, FILLFACTOR ...): none has a MySQL
        # equivalent, and they appear on both CREATE INDEX and inline PRIMARY KEY/UNIQUE clauses
        body = re.sub(r"(?is)\s*WITH\s*\(\s*(?:PAD_INDEX|STATISTICS_NORECOMPUTE|IGNORE_DUP_KEY"
                      r"|ALLOW_ROW_LOCKS|ALLOW_PAGE_LOCKS|OPTIMIZE_FOR_SEQUENTIAL_KEY|FILLFACTOR"
                      r"|SORT_IN_TEMPDB|ONLINE|DROP_EXISTING|DATA_COMPRESSION)\b[^)]*\)", "", body)
        if kind in ("table", "constraint"):
            body = convert_types(body)
            body = re.sub(r"(?i)\bIDENTITY\s*\(\s*\d+\s*,\s*\d+\s*\)", "AUTO_INCREMENT", body)
            body = re.sub(r"(?i)\bAUTO_INCREMENT\s+(NOT\s+NULL|NULL)", r"\1 AUTO_INCREMENT", body)
            body = re.sub(r"(?i)\bWITH\s+(?:NO)?CHECK\b(?!\s+OPTION)", "", body)
            # T-SQL parenthesises column defaults and lets them be named constraints;
            # MySQL supports neither: CONSTRAINT `df_x` DEFAULT (0) -> DEFAULT 0
            body = re.sub(r"(?i)\bDEFAULT\s*\(\s*([^()]+?)\s*\)", r"DEFAULT \1", body)
            body = re.sub(r"(?i)\bCONSTRAINT\s+`[^`]+`\s+(?=DEFAULT\b)", "", body)
            # MySQL cannot name a column-level PRIMARY KEY/UNIQUE constraint
            body = re.sub(r"(?i)\bCONSTRAINT\s+`?\w+`?\s+(?=(PRIMARY\s+KEY|UNIQUE)\b)", "", body)
            body = expand_alias_types(body, udts)          # sp_addtype (pubs)
            body = expand_alias_types(body, tsql_types)    # CREATE TYPE ... FROM (AdventureWorks)
            body = convert_like_classes(body)
            body = convert_functions(body)
            body, dropped_checks = drop_nondeterministic_checks(body)
            for name in dropped_checks:
                notes.append(f"dropped CHECK {name}: MySQL allows no non-deterministic function")
            if kind == "table":
                if fix_missing_commas:
                    body = comma_before_constraints(body)
                body, generated = convert_computed(body, computed_types or {}, materialize)
                # AdventureWorks LT's scripts end several column lists with a trailing comma
                body = re.sub(r",(\s*\)\s*;?)$", r"\1", body.rstrip())
                # only now does IDENTITY(1,1) exist as AUTO_INCREMENT
                body, identity = inline_identity_pk(body, declared_pk)
                if identity:
                    identity_pk[identity[0]] = identity[1]
                body, n_fk = hoist_inline_references(body)
                if n_fk:
                    notes.append(f"hoisted {n_fk} inline REFERENCES to table-level FOREIGN KEYs")
            body = re.sub(r"(?i)\bNOT\s+FOR\s+REPLICATION\b", "", body)
            body = re.sub(r"(?i)\s+\bROWGUIDCOL\b", "", body)          # a marker attribute only
            # NEWID()/NEWSEQUENTIALID() defaults: the data files supply every rowguid, and MySQL
            # cannot default a CHAR column to a generated UUID anyway
            body = re.sub(r"(?i)\s+DEFAULT\s*\(?\s*NEWSEQUENTIALID\s*\(\s*\)\s*\)?", "", body)
            body = re.sub(r"(?i)\s+DEFAULT\s*\(?\s*NEWID\s*\(\s*\)\s*\)?", "", body)
            for name in drop_checks:                     # CHECKs MySQL cannot express
                body = re.sub(rf"(?is),?\s*CONSTRAINT\s+`{re.escape(ident(name))}`\s+CHECK\s*\((?:[^()]|\([^()]*\))*\)",
                              "", body)
                notes.append(f"dropped CHECK {name}")
        if kind == "dml":
            if dateformat == "mdy":
                body = convert_dates_mdy(body)
            body = strip_money_literals(body)
            body = re.sub(r"(?i)^\s*INSERT\s+(?!INTO)", "INSERT INTO ", body, count=1)
            body = re.sub(r"(?i)\n\s*INSERT\s+(?!INTO)", "\nINSERT INTO ", body)
            tm = re.match(r"(?i)\s*INSERT\s+INTO\s+(?:`([^`]+)`|(\w+))\s+VALUES\b", body)
            if tm:
                key = (tm.group(1) or tm.group(2)).lower()
                cols, identity = table_columns.get(key, ([], None))
                if identity:
                    body = add_column_list(body, cols, identity)
        if kind == "table":
            m = re.search(r"(?i)CREATE\s+TABLE\s+(?:`([^`]+)`|(\w+))", body)
            if m:
                table_columns[(m.group(1) or m.group(2)).lower()] = parse_columns(body)
        if kind == "constraint":
            # T-SQL takes several clauses under one ADD; MySQL wants ADD on each of them. Splitting
            # them also lets a primary key already declared with an identity column be dropped on
            # its own, without losing the other clauses of the same statement.
            head = re.match(r"(?is)^(\s*ALTER\s+TABLE\s+`?(\w+)`?\s+)ADD\s+(.*?);?\s*$", body.strip())
            if head:
                clauses = []
                for clause in split_top(head.group(3), ","):
                    clause = clause.strip()
                    dup = re.match(r"(?is)^(?:CONSTRAINT\s+`?\w+`?\s+)?PRIMARY\s+KEY\s*"
                                   r"\(\s*`?(\w+)`?\s*\)$", clause)
                    if dup and identity_pk.get(head.group(2).lower()) == dup.group(1).lower():
                        notes.append("dropped a PRIMARY KEY already declared with its identity column")
                        continue
                    clauses.append(clause)
                if not clauses:
                    continue
                body = head.group(1) + ", ".join("ADD " + c for c in clauses)
        if kind == "view":
            # view attributes: SCHEMABINDING ties a view to its tables' schema, VIEW_METADATA
            # changes what the client driver reports. Neither has a MySQL equivalent.
            body = re.sub(r"(?i)\s+WITH\s+(SCHEMABINDING|VIEW_METADATA|ENCRYPTION)"
                          r"(\s*,\s*(SCHEMABINDING|VIEW_METADATA|ENCRYPTION))*", "", body)
        if kind in ("view", "procedure", "trigger", "function"):
            body = convert_select_aliases(body) if kind != "function" else body
            body = convert_functions(convert_tsql_convert(convert_xml_value(body)))
            body = convert_cast_targets(convert_date_functions(body))
            body = convert_recursive_cte(body)
            if kind == "view":
                # `FirstName + ' ' + LastName` in a view is T-SQL concatenation; left as `+`, MySQL
                # adds the strings numerically and returns 0 with a warning per row
                body = convert_view_concat(body)
        if kind in ("view", "procedure") and not keep_objects:
            notes.append(f"skipped {kind}")
            continue
        statements.append({"kind": kind, "sql": body.strip(),
                           "generated": generated if kind == "table" else []})
    # SQL Server can index a view; MySQL has no materialised views, so those indexes go away
    views = {m.group(1) for st in statements if st["kind"] == "view"
             for m in [re.search(r"(?is)^\s*CREATE\s+VIEW\s+`([^`]+)`", st["sql"])] if m}
    on_view = re.compile(r"(?is)^\s*CREATE\s+(?:UNIQUE\s+)?INDEX\s+`[^`]+`\s+ON\s+`([^`]+)`")
    kept = []
    for st in statements:
        m = on_view.match(st["sql"])
        if m and m.group(1) in views:
            notes.append(f"dropped an index on view {m.group(1)}: MySQL has no indexed views")
            continue
        kept.append(st)
    return kept, name_map, notes
