"""Probe the actual bundled consoles on the private gate stack."""

import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from clients import Client
from mysql import value as mysql_value
from native import ControlNotShown, Unavailable, checked, require, same
from postgres import value as pg_value

PORTS = {"adminer": "8080", "phpmyadmin": "80", "cloudbeaver": "8978"}
CONSOLES = ("adminer", "phpmyadmin", "dbgate", "cloudbeaver")


def loopback_console(target, name):
    port = target.published_port(name, PORTS[name])
    base = f"http://127.0.0.1:{port}"
    return base, urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )


class LoginToken(HTMLParser):
    value = ""

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "input" and fields.get("name") == "token":
            self.value = fields.get("value", "")


def adminer_login(target, demo_canary):
    print("Adminer: GET /, then POST the demo sign-in form")
    base, session = loopback_console(target, "adminer")
    with session.open(base + "/", timeout=45) as response:
        first = response.read().decode()
    token = LoginToken()
    token.feed(first)
    payload = urllib.parse.urlencode({
        "token": token.value, "auth[driver]": "server", "auth[server]": target.config["containers"]["mysql"],
        "auth[username]": "demo", "auth[password]": demo_canary, "auth[db]": "megasamples",
    }).encode()
    with session.open(base + "/", data=payload, timeout=45) as response:
        body = response.read().decode()
    return "datasets" in body and 'name="auth[password]"' not in body


def phpmyadmin_login(target):
    print("phpMyAdmin: GET the bundled demo database structure page")
    base, session = loopback_console(target, "phpmyadmin")
    route = "/index.php?route=/database/structure&server=1&db=megasamples"
    with session.open(base + route, timeout=45) as response:
        body = response.read().decode()
    return "datasets" in body and 'name="pma_password"' not in body


def dbgate_login(target):
    code = """
        (async () => {
          const e = process.env;
          const connection = await require('mysql2/promise').createConnection({
            host: e.SERVER_mysql_demo, port: +e.PORT_mysql_demo,
            user: e.USER_mysql_demo, password: e.PASSWORD_mysql_demo
          });
          const [rows] = await connection.query('SELECT CURRENT_USER() AS account');
          await connection.end();
          process.stdout.write(rows[0].account);
        })().catch(() => process.exit(1));
    """
    result = target.podman("exec", target.container("dbgate"), "node", "-e", code)
    return result.returncode == 0 and result.stdout.strip() == "demo@%"


def cloudbeaver_login(target, engine):
    print(f"CloudBeaver: openSession, initConnection({engine}-demo), navNodeChildren")
    base, session = loopback_console(target, "cloudbeaver")

    def graphql(query):
        request = urllib.request.Request(base + "/api/gql", data=json.dumps({"query": query}).encode(),
                                         headers={"Content-Type": "application/json"})
        with session.open(request, timeout=45) as response:
            document = json.load(response)
        return document.get("data") or {}

    graphql("mutation{openSession{valid}}")
    connections = graphql("{userConnections{id nodePath}}").get("userConnections") or []
    ident = engine + "-demo"
    path = next((row["nodePath"] for row in connections if row["id"] == ident), None)
    if path is None:
        return False
    opened = graphql("mutation{initConnection(projectId:\"g_GlobalConfiguration\",id:" +
                     json.dumps(ident) + "){connected clientVersion serverVersion}}")
    if not (opened.get("initConnection") or {}).get("connected"):
        return False
    data = graphql("{navNodeChildren(parentPath:" + json.dumps(path) + "){uri name}}")
    return session if "navNodeChildren" in data else False


def console_logins(target, canary):
    routines = {
        "Adminer": lambda: adminer_login(target, canary),
        "phpMyAdmin": lambda: phpmyadmin_login(target),
        "DbGate driver": lambda: dbgate_login(target),
        "CloudBeaver": lambda: cloudbeaver_login(target, "mysql"),
    }
    results = {}
    for name, sign_in in routines.items():
        try:
            results[name] = bool(sign_in())
        except urllib.error.HTTPError as error:
            results[name] = False
            print(f"{name}: HTTP {error.code}")
        print(f"{name}: demo sign-in {'accepted' if results[name] else 'refused'}")
    return results


def address_list(target, consoles):
    return ", ".join(f"'{address}'" for address in sorted(
        set().union(*(target.ipv4(console) for console in consoles))
    ))


def pg_sessions(target, addresses):
    return pg_value(target, f"""
        SELECT pid, usename, application_name, state,
               xact_start IS NULL, coalesce(query, '') <> '', host(client_addr)
        FROM pg_stat_activity WHERE host(client_addr) IN ({addresses}) ORDER BY pid;
    """).splitlines()


def browser_sql(target, sessions):
    browser = target.container("browser")
    target.container("cloudbeaver")
    console = target.config["containers"]["cloudbeaver"]
    result = target.podman(
        "exec", browser, "python3", "/gates/browser_sql.py",
        f"http://{console}:8978/", str(sessions), timeout=150,
    )
    if result.returncode or result.stdout.count("CloudBeaver SQL editor returned 17077") != sessions:
        raise Unavailable("the CloudBeaver SQL editor did not return the expected result")


def disposable_name(target):
    addresses = address_list(target, ("cloudbeaver",))
    initial = pg_sessions(target, addresses)
    browser_sql(target, 2)
    idle = [row.split("|") for row in pg_sessions(target, addresses) if row not in initial]
    people = [row for row in idle if row[1] == "demo" and row[3:6] == ["idle", "t", "t"]]
    require(len(people) >= 2, "the console did not retain two idle demo backends after SQL activity")
    require(len({tuple(row[1:]) for row in people}) < len(people),
            "the two idle console sessions do not have matching classification fields")
    reserved = "megasamples/gate"
    selection = f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{reserved}'"
    with Client(target, target.psql_args()) as product:
        product.send(f"SET application_name='{reserved}';")
        same(product.query("SELECT 1;"), "1")
        same(pg_value(target, selection), "1")
        require(all(row[2] != reserved for row in people), "console backend reused the reserved name")
        product.send("SET application_name='other idle client';")
        same(product.query("SELECT 1;"), "1")
        same(pg_value(target, selection), "0")


def no_console_without_users(target):
    addresses = address_list(target, CONSOLES)
    my_count = f"""
        SELECT count(*) FROM performance_schema.processlist
        WHERE SUBSTRING_INDEX(HOST, ':', 1) IN ({addresses})
    """
    for _ in range(3):
        same(pg_sessions(target, addresses), [])
        same(mysql_value(target, my_count), "0")
        time.sleep(3)
    session = cloudbeaver_login(target, "postgres")
    if not session or not pg_sessions(target, addresses):
        raise ControlNotShown("opening a PostgreSQL console session did not change the session query")


CASES = {"G-32a": disposable_name, "G-32b": no_console_without_users}
