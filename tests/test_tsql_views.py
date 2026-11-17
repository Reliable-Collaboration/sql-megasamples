"""Whole view definitions must not become operands of a string concatenation."""
import sqlglot
from sqlglot import exp

from megasamples.sources import tsql


def test_view_concat_keeps_statement_case_aliases_and_numeric_addition():
    script = """CREATE VIEW dbo.vTimeSeries AS
SELECT CASE Model WHEN 'Mountain-100' THEN 'M200'
       ELSE LEFT(Model, 1) + RIGHT(Model, 3) END + ' ' + Region AS ModelRegion,
       CAST(CalendarYear AS int) * 100 + CAST(Month AS int) AS TimeIndex
FROM dbo.Sales;
GO
"""
    statements, _, _ = tsql.translate(script, keep_objects=True, schemas={"dbo": ""})
    view = next(s["sql"] for s in statements if s["kind"] == "view")
    tree = sqlglot.parse_one(view, read="mysql")
    assert isinstance(tree, exp.Create)
    selection = tree.expression
    first, second = selection.expressions
    assert first.alias.lower() == "modelregion"
    assert isinstance(first.this, exp.Concat)
    assert len(list(first.find_all(exp.Concat))) == 2  # CASE's ELSE and its outer string join
    assert second.alias.lower() == "timeindex"
    assert isinstance(second.this, exp.Add)  # the year/month key stays arithmetic


def test_numeric_view_arithmetic_is_not_stringified_by_a_case_literal():
    statements, _, _ = tsql.translate("CREATE VIEW dbo.v AS SELECT CASE WHEN x = 'a' THEN 1 ELSE 2 END + n AS total FROM dbo.t;\nGO\n", keep_objects=True, schemas={"dbo": ""})
    view = next(s["sql"] for s in statements if s["kind"] == "view")
    tree = sqlglot.parse_one(view, read="mysql")
    assert isinstance(tree.expression.expressions[0].this, exp.Add)


def test_tsql_line_comment_without_space_stays_a_comment():
    statements, _, _ = tsql.translate("CREATE VIEW dbo.v AS SELECT name FROM dbo.t\n--ORDER BY name\nGO\n", keep_objects=True, schemas={"dbo": ""})
    view = next(s["sql"] for s in statements if s["kind"] == "view")
    tree = sqlglot.parse_one(view, read="mysql")
    assert tree.expression.args.get("order") is None


def test_unportable_xml_view_reaches_existing_exception_reporting():
    source = """CREATE VIEW dbo.v AS
SELECT CONVERT(datetime, REPLACE(r.ref.value('x[1]', 'varchar(40)'), 'Z', '')) AS d
FROM dbo.t CROSS APPLY t.doc.nodes('/x') AS r(ref)
GO
"""
    statements, _, _ = tsql.translate(source, keep_objects=True, schemas={"dbo": ""})
    view = next(s["sql"] for s in statements if s["kind"] == "view")
    assert "APPLY" in tsql.xml_blockers(view)
