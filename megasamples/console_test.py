#!/usr/bin/env python3
"""S10: the browsing console starts and shows what is actually loaded, for every engine in the stack.

  python3 -m megasamples test-console

Deliberately shallow: it catches a withdrawn image tag, a console that no longer starts, a landing
page that has drifted from the registries or lost its connection help, an account whose privileges
are not what the page says, and a DbGate whose SQLite driver does not load. It does not try to
drive four web applications.
"""
import http.cookiejar, json, os, subprocess, sys, urllib.error, urllib.request

from megasamples import config as stack, consoles as console_registry, engines as engine_registry
from megasamples.paths import ROOT


def passwords():
    found = {}
    env_file = os.path.join(ROOT, ".env")
    if os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            found[k.strip()] = v.strip().strip('"\'')
    return (found.get("DEMO_PASSWORD") or os.environ.get("DEMO_PASSWORD") or "demo",
            found.get("ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD") or "admin")


def get(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def phpmyadmin_ready(port, wanted, timeout=20):
    """A session-start error also returns HTTP 200; require both database lists."""
    problems = []
    for server in (1, 2):
        status, body = get(f"http://127.0.0.1:{port}/index.php?route=/server/databases&server={server}",
                           timeout=timeout)
        missing = [name for name in wanted if name not in body]
        if status != 200 or missing:
            problems.append(f"phpMyAdmin: server {server} did not list its databases "
                            f"(HTTP {status}; missing: {', '.join(missing[:6])})")
    return problems


def cloudbeaver_ready(port, wanted, timeout=20):
    """CloudBeaver answers even while it shows its setup wizard, so HTTP 200 proves nothing. Ask
    whether it is still in configuration mode and whether an anonymous visitor can open each
    connection -- the two things that silently regress."""
    gql = f"http://127.0.0.1:{port}/api/gql"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(query):
        req = urllib.request.Request(gql, data=json.dumps({"query": query}).encode(),
                                     headers={"Content-Type": "application/json"})
        with opener.open(req, timeout=timeout) as r:
            return json.load(r).get("data") or {}

    def connect(conn_id):
        q = 'mutation{initConnection(projectId:"g_GlobalConfiguration",id:"%s"){connected}}' % conn_id
        return (call(q).get("initConnection") or {}).get("connected")

    call("mutation{openSession{valid}}")
    d = call("{serverConfig{configurationMode} userConnections{id}}")
    problems = []
    if d.get("serverConfig", {}).get("configurationMode"):
        problems.append("CloudBeaver is in configuration mode: it is showing its setup wizard")
    ids = {c["id"] for c in d.get("userConnections") or []}
    for w in wanted:
        if w not in ids:
            problems.append(f"CloudBeaver does not offer the {w} connection anonymously")
        elif not connect(w):
            problems.append(f"CloudBeaver lists {w} but cannot connect with it")
    return problems


def engine_checks(engine, cfg, demo_pw, admin_pw, failures):
    """demo reads and cannot write; admin writes -- on the engine's own client, through its container."""
    c = engine.container
    if engine.name == "mysql":
        def run(user, pw, sql):
            return subprocess.run(["docker", "exec", c, "mysql", f"-u{user}", f"-p{pw}", "-N", "--batch", "-e", sql],
                                  capture_output=True, text=True).returncode
        db = "sakila" if "sakila" in cfg.datasets("mysql") else cfg.datasets("mysql")[0]
        ok_read = run("demo", demo_pw, f"SELECT 1 FROM information_schema.tables WHERE table_schema='{db}' LIMIT 1") == 0
        can_write = run("demo", demo_pw, f"CREATE TABLE {db}.t_console_probe (i INT)") == 0
        if can_write:
            run("admin", admin_pw, f"DROP TABLE IF EXISTS {db}.t_console_probe")
        admin_ok = run("admin", admin_pw, f"CREATE TABLE {db}.t_console_probe (i INT); DROP TABLE {db}.t_console_probe") == 0
    elif engine.name == "postgres":
        def run(user, pw, sql, db="megasamples"):
            return subprocess.run(["docker", "exec", "-e", f"PGPASSWORD={pw}", c, "psql", "-h", "127.0.0.1", "-U", user,
                                   "-d", db, "-v", "ON_ERROR_STOP=1", "-tAc", sql], capture_output=True, text=True).returncode
        ok_read = run("demo", demo_pw, "SELECT count(*) FROM datasets") == 0
        can_write = run("demo", demo_pw, "CREATE TABLE t_console_probe (i int)") == 0
        if can_write:
            run("admin", admin_pw, "DROP TABLE IF EXISTS t_console_probe")
        admin_ok = run("admin", admin_pw, "CREATE TABLE t_console_probe (i int); DROP TABLE t_console_probe") == 0
    else:
        ok_read = subprocess.run(["docker", "exec", c, "sqlite3", "/data/megasamples.sqlite", "SELECT count(*) FROM datasets"],
                                 capture_output=True).returncode == 0
        can_write, admin_ok = False, True
    if not ok_read:
        failures.append(f"{engine.title}: the demo account cannot read with the configured password")
    if can_write:
        failures.append(f"{engine.title}: the demo account can write; it is meant to be read-only")
    if not admin_ok:
        failures.append(f"{engine.title}: the admin account cannot write")
    if ok_read and not can_write and admin_ok:
        print(f"  . {engine.title}: demo reads and cannot write; admin writes" if engine.port else f"  . {engine.title}: files readable")


def main(argv=None):
    cfg = stack.load()
    demo_pw, admin_pw = passwords()
    failures, page = [], ""
    for name in cfg.consoles:
        console = console_registry.get(name)
        if console.engines and not any(e in cfg.engines for e in console.engines):
            continue
        url = f"http://127.0.0.1:{cfg.ports[name]}/"
        try:
            status, body = get(url)
            if status != 200:
                failures.append(f"{console.title}: HTTP {status}")
            else:
                print(f"  . {console.title:<14} HTTP 200 ({len(body):,} bytes)")
            if name == "landing":
                page = body
        except (urllib.error.URLError, OSError) as exc:
            failures.append(f"{console.title}: {exc}")
            print(f"  x {console.title:<14} {exc}")

    for name in cfg.engines:
        engine = engine_registry.get(name)
        try:
            names = [r[0] for r in engine.registry_rows(engine.container)]
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{engine.title}: could not read the registry: {str(exc)[:150]}")
            continue
        if "landing" in cfg.consoles:
            missing = [n for n in names if f">{n}<" not in page]
            if missing:
                failures.append(f"the landing page omits {len(missing)} {engine.title} database(s): " + ", ".join(missing[:6]))
            else:
                print(f"  . the landing page names all {len(names)} {engine.title} databases in the registry")
        engine_checks(engine, cfg, demo_pw, admin_pw, failures)
        if name == "mysql" and "phpmyadmin" in cfg.consoles:
            try:
                problems = phpmyadmin_ready(cfg.ports["phpmyadmin"], names)
                failures += problems
                if not problems:
                    print("  . phpMyAdmin lists every MySQL database for both configured accounts")
            except (urllib.error.URLError, OSError) as exc:
                failures.append(f"phpMyAdmin: could not check its database lists: {exc}")

    if "cloudbeaver" in cfg.consoles:
        wanted = [f"{e}-{a}" for e in cfg.engines if e in ("mysql", "postgres") for a in ("demo", "admin")]
        wanted += [f"sqlite-{d}" for d in ([] if "sqlite" not in cfg.engines else
                                          [__import__("megasamples.datasets", fromlist=["load"]).load(x)["database"] for x in cfg.datasets("sqlite")[:2]])]
        try:
            problems = cloudbeaver_ready(cfg.ports["cloudbeaver"], wanted)
            failures += problems
            if not problems:
                print(f"  . CloudBeaver is configured and opens {len(wanted)} connection(s) anonymously")
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            failures.append(f"CloudBeaver: could not check its state: {exc}")

    for account in ("demo", "admin") if "landing" in cfg.consoles else ():
        if account not in page:
            failures.append(f"the landing page does not state the {account} account, and Adminer's login form needs it")
    if "landing" in cfg.consoles:
        # the page tells a visitor how to reach each engine from a tool of their own
        if "Connect with your own tool" not in page:
            failures.append("the landing page has no 'Connect with your own tool' section")
        for name in cfg.engines:
            engine = engine_registry.get(name)
            marker = f"127.0.0.1 port {cfg.ports.get(name, engine.port)}" if engine.port else "docker cp megasamples-sqlite:/data/"
            if marker not in page:
                failures.append(f"the landing page does not say how to connect to {engine.title} ({marker!r} missing)")
        if "adminer" in cfg.consoles:
            try:
                status, body = get(f"http://127.0.0.1:{cfg.ports['landing']}/adminer.html")
                if status != 200 or "Open as demo" not in body:
                    failures.append("adminer.html, the page behind the Adminer card, is missing or has no filled-in link")
                else:
                    print("  . adminer.html states the login details and opens Adminer filled in")
            except (urllib.error.URLError, OSError) as exc:
                failures.append(f"adminer.html: {exc}")

    if "dbgate" in cfg.consoles and "sqlite" in cfg.engines:
        # DbGate's SQLite driver is a native module; on the Alpine image it did not load at all
        # ("fcntl64: symbol not found"), so the check opens a mounted file through that module inside
        # the running console container and reads the registry
        probe = ("const D=require('/home/dbgate-docker/node_modules/better-sqlite3');"
                 "const db=new D('/data/megasamples.sqlite',{readonly:true});"
                 "console.log(db.prepare('select count(*) n from datasets').get().n)")
        p = subprocess.run(["docker", "exec", console_registry.get("dbgate").container, "node", "-e", probe],
                           capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip().isdigit():
            print(f"  . DbGate's SQLite driver opens a mounted file and reads the registry ({p.stdout.strip()} datasets)")
        else:
            failures.append(f"DbGate cannot open a SQLite file: {(p.stderr or p.stdout).strip()[:160]}")

    for f in failures:
        print(f"  x {f}")
    print(f"console: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
