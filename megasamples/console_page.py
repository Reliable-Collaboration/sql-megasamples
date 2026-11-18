#!/usr/bin/env python3
"""Generate the browsing console's landing page from the running stack.

  python3 -m megasamples console-page [--out consoles/landing/index.html]

The page is generated rather than written because a hand-written one is wrong the first time a
dataset is added, an engine is switched on or a row count moves. For every engine megasamples.yaml
names it reads the provenance registry inside that engine's running container -- the same table
the image tests assert against -- so it lists the databases that are actually there, with the
counts they actually have and, for a port, what was not carried over.

It also states the credentials: Adminer's login form remains even with a default server set
(measured, not assumed), so a visitor needs them to get in. Both accounts are shown, the read-only
one first, and the passwords are read from .env if there is one, so the page says what is actually
configured rather than what the defaults were. The page opens with how to connect a tool of the
visitor's own to each engine (address, accounts, client command, URL and JDBC forms; for SQLite the
files and how to copy one out), then the consoles ordered by how many engines they browse, and
beside it writes adminer.html, the page behind the Adminer card, with what its login form wants
for each engine and links that fill it in.
"""
import argparse, html, json, os, subprocess, sys, urllib.parse

import yaml

from megasamples import config as stack, consoles as console_registry, engines as engine_registry
from megasamples.catalogue import shorten
from megasamples.paths import CONSOLES as CONSOLES_DIR, ROOT


def passwords():
    values = stack.passwords()
    return values["DEMO_PASSWORD"], values["ADMIN_PASSWORD"]


def describe(record, blurb=""):
    """The dataset's one-line description, from its knowledge record (one trimming rule, shared
    with the catalogue, so the page and the catalogue cannot describe a dataset differently)."""
    if blurb:
        return blurb
    path = os.path.join(ROOT, record or "")
    if not record or not os.path.exists(path):
        return ""
    try:
        meta = yaml.safe_load(open(path, encoding="utf-8").read().split("---", 2)[1]) or {}
    except Exception:
        return ""
    return shorten((meta.get("description") or "").strip())


# Which consoles can be pointed at one database through a URL, per engine. DbGate and CloudBeaver
# read no database parameter, so they get no per-row link rather than one that opens their front page.
DEEP_LINKS = {
    "mysql": [("phpmyadmin", "P", "http://127.0.0.1:{port}/index.php?route=/database/structure&db={db}&server=1"),
              ("adminer", "A", "http://127.0.0.1:{port}/?server=mysql&username=demo&db={db}")],
    "postgres": [("adminer", "A", "http://127.0.0.1:{port}/?pgsql=postgres&username=demo&db={db}")],
    "sqlite": [],
}


def running(container):
    p = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", container], capture_output=True, text=True)
    return p.returncode == 0 and p.stdout.strip() == "true"


def collect(cfg):
    """{engine: {database: {tier, licenses, counts, record, tables, mb, not_ported}}} for every running engine."""
    out = {}
    for name in cfg.engines:
        engine = engine_registry.get(name)
        if not running(engine.container):
            print(f"  ! {engine.container} is not running; {engine.title} is left off the page")
            continue
        rows = engine.registry_rows(engine.container)
        sizes = engine.sizes(engine.container)
        per = {}
        for r in rows:
            db, tier, licenses, counts, record = r[:5]
            try:
                per_table = json.loads(counts) if counts and counts != "NULL" else {}
            except ValueError:
                per_table = {}
            try:
                lic = ", ".join(json.loads(licenses)) if licenses else ""
            except ValueError:
                lic = licenses or ""
            tables, mb = sizes.get(db, (len(per_table), 0.0))
            per[db] = {"tier": tier, "licenses": lic, "rows": sum(v for v in per_table.values() if isinstance(v, int)),
                       "record": record, "tables": tables, "mb": mb, "not_ported": not_ported(engine, db)}
        out[name] = per
    return out


def not_ported(engine, db):
    if engine.name == "mysql":
        return []
    try:
        rows = engine.query(engine.container, f"SELECT not_ported FROM datasets WHERE name = '{db}'")
        return json.loads(rows[0][0]) if rows and rows[0][0] not in ("", "NULL") else []
    except Exception:
        return []


def first_database(data, engine_name):
    dbs = sorted(data.get(engine_name, {}))
    return "sakila" if "sakila" in dbs else (dbs[0] if dbs else "sakila")


def connect_cards(cfg, data, demo_pw, admin_pw):
    """How to reach each running engine from a tool of the visitor's own: address, accounts, and the
    forms a client, a URL and a JDBC driver take -- read from the configuration and the stack, so a
    changed port or password is what the page says."""
    cards = []
    for name in data:
        e = engine_registry.get(name)
        first = first_database(data, name)
        port = cfg.ports.get(name, e.port)
        rows = []
        if name == "mysql":
            rows = [("address", f"127.0.0.1 port {port}"),
                    ("accounts", f"demo / {demo_pw} (read only) · admin / {admin_pw} (all privileges) · root (superuser; private .env)"),
                    ("client", f"mysql -h 127.0.0.1 -P {port} -u demo -p {first}"),
                    ("URL", f"mysql://demo:{urllib.parse.quote(demo_pw, safe='')}@127.0.0.1:{port}/{first}"),
                    ("JDBC", f"jdbc:mysql://127.0.0.1:{port}/{first}"),
                    ("note", "MySQL 9 authenticates with caching_sha2_password: use a client or driver from the MySQL 8 era or newer.")]
        elif name == "postgres":
            rows = [("address", f"127.0.0.1 port {port}"),
                    ("accounts", f"demo / {demo_pw} (read only) · admin / {admin_pw} (owns every sample table) · postgres (superuser; private .env)"),
                    ("client", f"psql -h 127.0.0.1 -p {port} -U demo -W {first}"),
                    ("URL", f"postgresql://demo:{urllib.parse.quote(demo_pw, safe='')}@127.0.0.1:{port}/{first}"),
                    ("JDBC", f"jdbc:postgresql://127.0.0.1:{port}/{first}"),
                    ("note", "one database per dataset; connect to the one you want, or to `megasamples` for the registry.")]
        elif name == "sqlite":
            rows = [("files", f"/data/{{database}}.sqlite inside the megasamples-sqlite container, plus /data/megasamples.sqlite (the registry); no accounts"),
                    ("copy one out", f"docker cp megasamples-sqlite:/data/{first}.sqlite ."),
                    ("on the build machine", f"build/sqlite/{first}/{first}.sqlite (the same file)"),
                    ("open", f"sqlite3 {first}.sqlite · DB Browser for SQLite, DBeaver, DataGrip: open the file · Python: sqlite3.connect('{first}.sqlite')"),
                    ("note", "run PRAGMA foreign_keys=ON to enforce the foreign keys the file declares; a full-text index is an FTS5 table named <table>_<index>_fts.")]
        body = "".join(f'<tr><th>{html.escape(k)}</th><td>{"<code>" + html.escape(v) + "</code>" if k in ("client", "URL", "JDBC", "copy one out") else html.escape(v)}</td></tr>'
                       for k, v in rows)
        cards.append(f'<div class="engine"><h3>{html.escape(e.title)} {html.escape(e.version)}</h3><table class="kv">{body}</table></div>')
    return "\n".join(cards)


def console_cards(cfg, data):
    """The consoles, the ones that browse every engine first; a console that browses one engine of
    several says so and takes less room."""
    present = [console_registry.get(n) for n in cfg.consoles if n != "landing" and n in cfg.ports]
    order = {c.name: i for i, c in enumerate(console_registry.CONSOLES)}
    covers = {c.name: [e for e in c.engines if e in data] for c in present}
    present.sort(key=lambda c: (-len(covers[c.name]), order[c.name]))
    cards = []
    for c in present:
        browsed = ", ".join(engine_registry.get(e).title for e in covers[c.name]) or "—"
        minor = len(covers[c.name]) == 1 and len(data) > 1
        badge = f'<span class="only">{html.escape(engine_registry.get(covers[c.name][0]).title)} only</span>' if minor else ""
        href = "adminer.html" if c.name == "adminer" else f"http://127.0.0.1:{cfg.ports[c.name]}/"
        cards.append(f'      <a class="console{" minor" if minor else ""}" href="{href}"><b>{html.escape(c.title)}</b>{badge}'
                     f'<span>{html.escape(c.note)}</span><em>browses {html.escape(browsed)}</em></a>')
    return "\n".join(cards)


STYLE = """
 :root { color-scheme: light dark; --line:#8883; }
 body { font:15px/1.5 system-ui,sans-serif; margin:0 auto; padding:2rem 1.25rem; max-width:72rem; }
 h1 { font-size:1.5rem; margin:0 0 .25rem; }
 h2 { font-size:1.15rem; margin:1.75rem 0 .5rem; }
 h3 { font-size:1rem; margin:0 0 .35rem; }
 p.sub { margin:0 0 1.5rem; opacity:.7; }
 .consoles { display:grid; gap:.75rem; grid-template-columns:repeat(auto-fit,minmax(15rem,1fr)); margin-bottom:1.5rem; }
 a.console { display:block; padding:.85rem 1rem; border:1px solid var(--line); border-radius:.5rem; text-decoration:none; color:inherit; }
 a.console:hover { border-color:#69f; }
 a.console span, a.console em { display:block; font-size:.85em; opacity:.7; margin-top:.2rem; font-style:normal; }
 a.console.minor { opacity:.75; font-size:.92em; padding:.6rem .85rem; }
 .only { display:inline-block; margin-left:.5rem; padding:0 .4rem; border:1px solid var(--line); border-radius:.3rem; font-size:.72em; opacity:.8; vertical-align:middle; }
 .engines { display:grid; gap:.75rem; grid-template-columns:repeat(auto-fit,minmax(20rem,1fr)); }
 .engine { border:1px solid var(--line); border-radius:.5rem; padding:.75rem 1rem; }
 table.kv { font-size:.88em; width:100%; }
 table.kv th { width:8.5rem; opacity:.7; font-weight:500; white-space:nowrap; }
 table.kv th, table.kv td { border:none; padding:.15rem .4rem .15rem 0; vertical-align:top; }
 table.kv code { word-break:break-all; }
 table { border-collapse:collapse; width:100%; font-size:.9em; }
 th,td { text-align:left; padding:.35rem .6rem; border-bottom:1px solid var(--line); vertical-align:top; }
 th.eng { text-align:center; border-left:1px solid var(--line); }
 td.n, th.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
 code { font-size:.95em; }
 .what { font-size:.88em; opacity:.72; margin-top:.15rem; max-width:34rem; }
 a.go { display:inline-block; width:1.25rem; height:1.25rem; line-height:1.25rem; text-align:center; border:1px solid var(--line);
         border-radius:.25rem; font-size:.72em; font-weight:600; text-decoration:none; color:inherit; opacity:.65; margin-left:.25rem; }
 a.go:hover { opacity:1; border-color:#69f; }
 .np { font-size:.75em; opacity:.6; cursor:help; }
 .creds { border:1px solid var(--line); border-radius:.5rem; padding:.75rem 1rem; margin:1.5rem 0; font-size:.9em; }
 footer { margin-top:2rem; font-size:.85em; opacity:.7; }
"""


def render(cfg, data):
    raw_demo, raw_admin = passwords()
    demo_pw, admin_pw = (html.escape(p) for p in (raw_demo, raw_admin))
    engines = [engine_registry.get(n) for n in data]
    blurbs = {}
    for d in os.listdir(os.path.join(ROOT, "datasets")):
        p = os.path.join(ROOT, "datasets", d, "dataset.yaml")
        if os.path.exists(p):
            spec = yaml.safe_load(open(p, encoding="utf-8")) or {}
            if spec.get("blurb"):
                blurbs[spec.get("database", d)] = spec["blurb"]

    databases = sorted({db for per in data.values() for db in per})
    head_cells = "".join(f'<th colspan="3" class="eng">{html.escape(e.title)} {html.escape(e.version)}</th>' for e in engines)
    sub_cells = "".join('<th class="n">tables</th><th class="n">rows</th><th class="n">MB</th>' for _ in engines)
    rows_html = []
    for db in databases:
        first = next((per[db] for per in data.values() if db in per), {})
        what = describe(first.get("record", ""), blurbs.get(db, ""))
        cells = []
        for e in engines:
            info = data[e.name].get(db)
            if not info:
                cells.append('<td class="n" colspan="3">—</td>')
                continue
            links = "".join(
                f'<a class="go" title="Open {html.escape(db)} in {html.escape(console_registry.get(cn).title)}" '
                f'href="{html.escape(url.format(port=cfg.ports.get(cn, 0), db=db), quote=True)}">{letter}</a>'
                for cn, letter, url in DEEP_LINKS.get(e.name, []) if cn in cfg.consoles)
            np = info["not_ported"]
            note = (f' <span class="np" title="{html.escape(chr(10).join(np))}">{len(np)} not ported</span>' if np else "")
            cells.append(f'<td class="n">{info["tables"]:,}{links}</td><td class="n">{info["rows"]:,}</td>'
                         f'<td class="n">{info["mb"]:,.1f}{note}</td>')
        rows_html.append(f'      <tr><td><code>{html.escape(db)}</code><div class="what">{html.escape(what)}</div></td>'
                         f'<td>{html.escape(first.get("tier", ""))}</td>{"".join(cells)}<td>{html.escape(first.get("licenses", ""))}</td></tr>')

    totals = " · ".join(f"{html.escape(e.title)}: {len(data[e.name])} databases, "
                        f"{sum(i['rows'] for i in data[e.name].values()):,} rows" for e in engines)
    consoles_present = [n for n in cfg.consoles if n != "landing" and n in cfg.ports]
    page = f"""<!doctype html>
<meta charset="utf-8"><title>sql-megasamples</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{STYLE}</style>
<h1>sql-megasamples</h1>
<p class="sub">{totals}</p>

<h2>Connect with your own tool</h2>
<p>Every server engine listens on <code>127.0.0.1</code> of this machine, on the port below, with the same two accounts;
DBeaver, DataGrip, TablePlus, VS Code, a language driver or the engine's own client all take these details as they are.</p>
<div class="engines">
{connect_cards(cfg, data, raw_demo, raw_admin)}
</div>

<h2>Or browse in the browser</h2>
<div class="consoles">
{console_cards(cfg, data)}
</div>

<div class="creds">
  <b>Two accounts</b>, offered by every console and usable from any client:
  <code>demo</code> / <code>{demo_pw}</code> — <b>read only</b>, no write privilege anywhere; each console opens on this one.
  <code>admin</code> / <code>{admin_pw}</code> — <b>full privileges</b>, so anything you change here stays changed.
  SQLite files have no accounts. Both passwords are boilerplate for a disposable test database; change them by copying
  <code>.env.example</code> to <code>.env</code>, and the same value reaches every engine and every console.
</div>

<table>
  <thead><tr><th rowspan="2">database — <b>P</b> opens it in phpMyAdmin (MySQL), <b>A</b> in Adminer</th><th rowspan="2">tier</th>{head_cells}<th rowspan="2">licence</th></tr>
  <tr>{sub_cells}</tr></thead>
  <tbody>
{chr(10).join(rows_html)}
  </tbody>
</table>

<footer>
  Generated from the provenance registry inside each running engine, so it cannot drift from what is actually loaded.
  PostgreSQL and SQLite are ports of the verified MySQL corpus: the same rows, checked by the same content digests;
  "not ported" counts the views, routines, triggers, indexes and columns that engine cannot carry, lists them with the
  reason when you hover, and <code>knowledge/decisions/programmable-object-parity.md</code> in the repository explains
  each kind. Each dataset keeps its own upstream licence — see <code>datasets/&lt;name&gt;/PROVENANCE.md</code>
  in the repository — and each description comes from its research record rather than being written here.
</footer>
"""
    return page, len(databases)


def render_adminer(cfg, data):
    """The page behind the Adminer card: what its login form wants for each engine, and links that
    open it filled in. Adminer runs inside the stack, so the server it connects to is the engine's
    service name, not 127.0.0.1."""
    demo_pw, admin_pw = (html.escape(p) for p in passwords())
    port = cfg.ports.get("adminer", 8082)
    sections = []
    if "mysql" in data:
        first = first_database(data, "mysql")
        sections.append(f"""
<div class="engine"><h3>MySQL</h3>
<table class="kv">
<tr><th>System</th><td>MySQL</td></tr>
<tr><th>Server</th><td><code>mysql</code> (the engine's name inside the stack; not 127.0.0.1)</td></tr>
<tr><th>Username</th><td><code>demo</code> (read only) or <code>admin</code> (all privileges)</td></tr>
<tr><th>Password</th><td><code>{demo_pw}</code> for demo, <code>{admin_pw}</code> for admin — Adminer never fills this in</td></tr>
<tr><th>Database</th><td>optional; one of {html.escape(", ".join(sorted(data["mysql"])))}</td></tr>
</table>
<p><a class="open" href="http://127.0.0.1:{port}/?server=mysql&amp;username=demo&amp;db={first}">Open as demo</a>
   <a class="open" href="http://127.0.0.1:{port}/?server=mysql&amp;username=admin&amp;db={first}">Open as admin</a></p>
</div>""")
    if "postgres" in data:
        first = first_database(data, "postgres")
        sections.append(f"""
<div class="engine"><h3>PostgreSQL</h3>
<table class="kv">
<tr><th>System</th><td>PostgreSQL</td></tr>
<tr><th>Server</th><td><code>postgres</code> (the engine's name inside the stack; not 127.0.0.1)</td></tr>
<tr><th>Username</th><td><code>demo</code> (read only) or <code>admin</code> (owns every sample table); <code>postgres</code> / <code>root</code> is the superuser</td></tr>
<tr><th>Password</th><td><code>{demo_pw}</code> for demo, <code>{admin_pw}</code> for admin — Adminer never fills this in</td></tr>
<tr><th>Database</th><td>one of {html.escape(", ".join(sorted(data["postgres"])))}; PostgreSQL needs one to connect to</td></tr>
</table>
<p><a class="open" href="http://127.0.0.1:{port}/?pgsql=postgres&amp;username=demo&amp;db={first}">Open as demo</a>
   <a class="open" href="http://127.0.0.1:{port}/?pgsql=postgres&amp;username=admin&amp;db={first}">Open as admin</a></p>
</div>""")
    sqlite_note = ("<p>SQLite files are not opened by Adminer here: its SQLite driver requires a password plugin and a path inside its own "
                   "container. Use CloudBeaver or DbGate for them, or your own tool on the file (see the index page).</p>"
                   if "sqlite" in data else "")
    return f"""<!doctype html>
<meta charset="utf-8"><title>Adminer — connection details</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{STYLE}
 a.open {{ display:inline-block; margin:.25rem .5rem 0 0; padding:.35rem .8rem; border:1px solid var(--line); border-radius:.4rem; text-decoration:none; color:inherit; }}
 a.open:hover {{ border-color:#69f; }}
</style>
<h1>Adminer</h1>
<p class="sub"><a href="index.html">← console index</a> · Adminer keeps its login form; here is what to type for each engine, and links that fill it in for you.</p>
<div class="engines">
{"".join(sections)}
</div>
{sqlite_note}
<footer>Adminer 5 at <a href="http://127.0.0.1:{port}/">http://127.0.0.1:{port}/</a>. The passwords come from <code>.env</code> when there is one, so this page states what is actually configured.</footer>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.path.join(CONSOLES_DIR, "landing", "index.html"))
    a = ap.parse_args(argv)
    cfg = stack.load()
    data = collect(cfg)
    if not data:
        print("  x no engine of the stack is running; nothing to write")
        return 1
    page, n = render(cfg, data)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(page)
    print(f"  . wrote {os.path.relpath(a.out, ROOT)}: {n} databases across {', '.join(data)}")
    if "adminer" in cfg.consoles:
        adminer_page = os.path.join(os.path.dirname(a.out), "adminer.html")
        open(adminer_page, "w", encoding="utf-8").write(render_adminer(cfg, data))
        print(f"  . wrote {os.path.relpath(adminer_page, ROOT)}: Adminer's connection details")
    return 0


if __name__ == "__main__":
    sys.exit(main())
