"""The console registry: the web UIs the stack can start beside the databases.

Each console says which engines it can browse, the image it runs (pinned by digest), the memory it
is allowed, and how it is pointed at the databases. compose.py turns these into services,
console_page.py into landing-page links, console_test.py into endpoints to probe.
"""
from dataclasses import dataclass, field


@dataclass
class Console:
    name: str
    title: str
    engines: tuple                 # engines it can browse; () means it needs none (the landing page)
    image: str
    container_port: int
    mem_limit: str
    note: str                      # how a visitor gets in, shown on the landing page
    deep_link: str = ""            # URL template opening one database, {port} and {db}; "" if none
    letter: str = ""               # the one-letter badge the landing page uses for the deep link
    volumes: list = field(default_factory=list)
    environment: dict = field(default_factory=dict)   # settings the console needs whatever the engines
    build_image: str = ""          # local image built from the pinned vendor image and driver lock
    dockerfile: str = ""

    @property
    def runtime_image(self):
        return self.build_image or self.image

    @property
    def container(self):
        return f"megasamples-{self.name}"


CONSOLES = [
    Console("landing", "Console index", (),
            "nginx:1.31.8@sha256:165ddde8751e75a1c907d24ef10d9f6deb08b57e0fe56caf67512486aff76d82", 80, "32m",
            "Start here: every database with its size, licence and provenance, and how to connect your own tool.",
            volumes=["./consoles/landing:/usr/share/nginx/html:ro"]),
    Console("cloudbeaver", "CloudBeaver", ("mysql", "postgres", "sqlite"),
            "dbeaver/cloudbeaver:26.2.5@sha256:5de1c6aa18da9e369966f88a1b25fe017b70ce3fdac7d879616aa931e44b013f", 8978, "640m",
            "Opens as a guest with every connection in the sidebar: both accounts on each server engine, one connection per SQLite file.",
            volumes=["./consoles/cloudbeaver/.cloudbeaver.auto.conf:/opt/cloudbeaver/conf/.cloudbeaver.auto.conf:ro",
                     "./consoles/cloudbeaver/generated/cloudbeaver.conf:/opt/cloudbeaver/conf/cloudbeaver.conf:ro",
                     "./consoles/cloudbeaver/generated/initial-data-sources.conf:/opt/cloudbeaver/conf/initial-data-sources.conf:ro"],
            # guests see the preconfigured connections, cannot edit them, and the ${DEMO_PASSWORD}
            # placeholders in the generated data sources resolve -- whichever engines are in the stack
            environment={"CLOUDBEAVER_APP_GRANT_CONNECTIONS_ACCESS_TO_ANONYMOUS_TEAM": "true",
                         "CLOUDBEAVER_APP_READ_ONLY_CONNECTION_INFO": "true",
                         "CLOUDBEAVER_SYSTEM_VARIABLES_RESOLVING_ENABLED": "true",
                         "DEMO_PASSWORD": "${DEMO_PASSWORD:-demo}", "ADMIN_PASSWORD": "${ADMIN_PASSWORD:-admin}"},
            build_image="sql-megasamples-cloudbeaver:26.2.5-mysql-9.7.0-sqlite-3.54.1.0",
            dockerfile="consoles/cloudbeaver/Dockerfile"),
    # the Debian-based image, not the Alpine one: the SQLite driver's native module (better-sqlite3)
    # is built against glibc and fails to load on musl ("fcntl64: symbol not found"), measured on
    # 6.6.1-alpine on 2026-09-10; on this image it opens a file and answers a query
    Console("dbgate", "DbGate", ("mysql", "postgres", "sqlite"),
            "dbgate/dbgate:7.3.6@sha256:adb32bb7e0de948d1ffccbc9639014741e1f6d750f7fddd800af651777922953", 3000, "320m",
            "Every connection preconfigured in the sidebar: both accounts on each server engine, one per SQLite file.",
            build_image="sql-megasamples-dbgate:7.3.6-node-24.22.3-sqlite-13.2.0",
            dockerfile="consoles/dbgate/Dockerfile"),
    Console("adminer", "Adminer", ("mysql", "postgres"),
            "adminer:6.3.0@sha256:7605e298e5a2ac74d806283362fa253a4e0a42cfd881e8fa2c155f0631899f6c", 8080, "160m",
            "Its login form remains: the page behind this card says what to type for each engine, and opens it filled in.",
            "http://127.0.0.1:{port}/?server=mysql&username=demo&db={db}", "A",
            build_image="sql-megasamples-adminer:6.3.0-libpq-18.7-r0",
            dockerfile="consoles/adminer/Dockerfile"),
    Console("phpmyadmin", "phpMyAdmin", ("mysql",),
            "phpmyadmin:5.2.3@sha256:e4b3eb5305cd42d21512bb55def2bab52625d56df927ad4ee1864a9354c84d40", 80, "256m",
            "MySQL only. Signed in already; the server menu switches account.",
            "http://127.0.0.1:{port}/index.php?route=/database/structure&db={db}&server=1", "P",
            volumes=["./consoles/phpmyadmin/config.user.inc.php:/etc/phpmyadmin/config.user.inc.php:ro"]),
]
_BY_NAME = {c.name: c for c in CONSOLES}


def names():
    return list(_BY_NAME)


def get(name):
    if name not in _BY_NAME:
        raise KeyError(f"unknown console {name!r}; known: {', '.join(_BY_NAME)}")
    return _BY_NAME[name]


def usable(engines):
    """The consoles that can browse at least one of the given engines, plus the landing page."""
    return [c for c in CONSOLES if not c.engines or any(e in engines for e in c.engines)]
