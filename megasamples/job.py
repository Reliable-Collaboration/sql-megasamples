"""The commands that read megasamples.yaml and drive the engines.

  python3 -m megasamples build [--engine E] [--fresh] [--no-fetch] [dataset ...]
  python3 -m megasamples image [--engine E] [--keep] [--from-dumps] [dataset ...]
  python3 -m megasamples test-image [--engine E] [dataset ...]
  python3 -m megasamples run [--up]              fetch, build, image for every configured engine
  python3 -m megasamples up | down               the stack, from compose.yaml (regenerated first)
  python3 -m megasamples check                   the local gate

Datasets default to what megasamples.yaml names for the engine; naming some on the command line
narrows the job to those. MySQL is the hub, so building a dataset for any engine first builds it
there (ARCHITECTURE.md section 3).
"""
import argparse, os, subprocess, sys

from megasamples import data_volumes, workspace, compose, config as stack, console_page, fetch as fetcher, engines as engine_registry
from megasamples.paths import COMPOSE, ROOT


def _engines(cfg, chosen):
    names = [chosen] if chosen else list(cfg.engines)
    for n in names:
        if n not in cfg.engines and chosen:
            print(f"  ! {n} is not in {cfg.source}; building it anyway")
    return [engine_registry.get(n) for n in names]


def _datasets(cfg, engine, named):
    return list(named) if named else cfg.datasets(engine.name)


def _fetch_all(cfg, engines, named):
    """Fetch every configured dataset's artifacts once. Returns {dataset: [reasons]} for the datasets
    whose downloads are not in place; the build goes on without them and says so at the end."""
    wanted = []
    for engine in engines:
        for d in _datasets(cfg, engine, named):
            if d not in wanted:
                wanted.append(d)
    if not wanted:
        return {}
    print(f"== fetch: {' '.join(wanted)}")
    return fetcher.fetch_for(wanted)


def _report_blocked(blocked):
    if blocked:
        print(f"  x {len(blocked)} dataset(s) left out, their downloads not in place: {', '.join(sorted(blocked))}"
              " -- see the fetch lines above for what to obtain, or leave them out of megasamples.yaml")


def build(argv=None):
    ap = argparse.ArgumentParser(description="fetch, stage, load and verify datasets on an engine")
    ap.add_argument("datasets", nargs="*")
    ap.add_argument("--engine")
    ap.add_argument("--fresh", action="store_true", help="recreate the build server first")
    ap.add_argument("--no-fetch", action="store_true", help="assume the downloads are present")
    a = ap.parse_args(argv)
    cfg = stack.load()
    engines = _engines(cfg, a.engine)
    blocked = {} if a.no_fetch else _fetch_all(cfg, engines, a.datasets)
    failures = 0
    for engine in engines:
        datasets = [d for d in _datasets(cfg, engine, a.datasets) if d not in blocked]
        if not datasets:
            print(f"  . {engine.name}: no datasets to build")
            continue
        for i, d in enumerate(datasets):
            print(f"== {engine.name} {d} ({i + 1}/{len(datasets)})")
            failures += engine.build(d, fresh=a.fresh and i == 0) or 0
    _report_blocked(blocked)
    print(f"build: {failures} failure(s)" + (f", {len(blocked)} dataset(s) not fetched" if blocked else ""))
    return 1 if failures or blocked else 0


def image(argv=None):
    ap = argparse.ArgumentParser(description="bake the configured datasets into an engine's image")
    ap.add_argument("datasets", nargs="*")
    ap.add_argument("--engine")
    ap.add_argument("--keep", action="store_true", help="keep the build server afterwards")
    ap.add_argument("--from-dumps", action="store_true",
                    help="bake from the dumps already in build/<engine>/ instead of dumping the build server")
    a = ap.parse_args(argv)
    cfg = stack.load()
    keep = a.keep or bool(cfg.build.get("keep_build_server"))
    for engine in _engines(cfg, a.engine):
        datasets = _datasets(cfg, engine, a.datasets)
        print(f"== image: {engine.image} <- {' '.join(datasets)}")
        rc = engine.image_build(datasets, keep=keep, threads=int(cfg.build.get("threads", 4)),
                                from_dumps=a.from_dumps)
        if rc:
            return rc
    return 0


def test_image(argv=None):
    ap = argparse.ArgumentParser(description="run the image-level tests against a built image")
    ap.add_argument("datasets", nargs="*")
    ap.add_argument("--engine")
    a = ap.parse_args(argv)
    cfg = stack.load()
    failures = 0
    for engine in _engines(cfg, a.engine):
        print(f"== test-image: {engine.image}")
        failures += engine.image_test(_datasets(cfg, engine, a.datasets)) or 0
    return 1 if failures else 0


def main(argv=None):
    """`run`: the whole job from the configuration."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--up", action="store_true", help="start the stack when the images are built")
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    cfg = stack.load()
    problems = cfg.validate()
    for p in problems:
        print(f"  x {p}")
    if problems:
        return 2
    print(f"run: {cfg.source}")
    for name, datasets in cfg.engines.items():
        print(f"  {name}: {len(datasets)} dataset(s)")
    print(f"  consoles: {', '.join(cfg.consoles)}\n")
    # everything is fetched once, up front; a dataset whose download is not in place is left out of
    # every engine's build and image, and named at the end, rather than stopping the whole job
    engines = _engines(cfg, None)
    blocked = {} if a.no_fetch else _fetch_all(cfg, engines, [])
    rc = 0
    for engine in engines:
        datasets = [d for d in cfg.datasets(engine.name) if d not in blocked]
        if not datasets:
            print(f"  . {engine.name}: no datasets to build")
            continue
        if build(["--no-fetch", "--engine", engine.name, *datasets]):
            rc = 1
            continue                    # an engine that did not build is not baked
        # the build servers stay up across engines: the ports read the hub, and every engine's
        # image is baked from what one MySQL build loaded
        if image(["--engine", engine.name, "--keep", *datasets]):
            rc = 1
    if not cfg.build.get("keep_build_server"):
        print("  . removing the build servers; set build.keep_build_server to keep them next time")
        workspace.clean()
    _report_blocked(blocked)
    if a.up and not rc:
        return up([])
    return 1 if rc or blocked else rc


def up(argv=None):
    ap = argparse.ArgumentParser(description="regenerate compose.yaml and the landing page, start the stack")
    ap.parse_args(argv)
    cfg = stack.load()
    from megasamples import console_config
    console_config.main([])
    if compose.main([]):
        return 2
    from megasamples import console_images
    if console_images.build(cfg):
        return 1
    # Compose does not recreate a service whose image was rebuilt under the same tag, and when it
    # does recreate one it keeps the anonymous volume the official images declare for their data
    # directory -- so the old data would shadow the new image. An engine whose running container is
    # not on the current image is recreated first, with its anonymous volumes renewed.
    stale = []
    # The image Compose will run, with .env's overrides, not Python's default tag.
    resolved = data_volumes.compose_images()
    for name in cfg.engines:
        e = engine_registry.get(name)
        if name not in resolved:
            # Without Compose's answer the only comparison left is with Python's default tag, which can call
            # a current container stale and discard its working data: renew nothing.
            print(f"  ! not recreating {name}: Compose could not resolve its image, so whether it is stale is "
                  f"unknown; check `docker compose -f {COMPOSE} config`", file=sys.stderr)
            continue
        running = subprocess.run(["docker", "inspect", "-f", "{{.Image}}", e.container], capture_output=True, text=True)
        current = subprocess.run(["docker", "image", "inspect", "-f", "{{.Id}}", resolved[name]],
                                 capture_output=True, text=True)
        if running.returncode == 0 and current.returncode == 0 and running.stdout.strip() != current.stdout.strip():
            stale.append(name)
    if stale:
        print(f"  . recreating {', '.join(stale)}: the image was rebuilt since the container started")
        # The volumes it replaces are removed by name, as reset's are.
        if data_volumes.recreate(stale, [engine_registry.get(name).container for name in stale]):
            return 1
    if "landing" in cfg.consoles:
        # the bind mount's source; Docker would otherwise create it owned by root
        os.makedirs(os.path.join(ROOT, "consoles", "landing"), exist_ok=True)
    print("  . docker compose up -d --wait")
    if subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "-d", "--wait"], cwd=ROOT).returncode != 0:
        return 1
    if "postgres" in cfg.engines:
        from megasamples import postgres_orphans
        for warning in postgres_orphans.scan(engine_registry.get("postgres").container):
            print("  ! " + postgres_orphans.describe(warning), file=sys.stderr)
    if "landing" in cfg.consoles:
        rc = console_page.main([])
        if rc:
            return rc
    print("  . the stack is up:")
    for name in cfg.engines:
        e = engine_registry.get(name)
        where = f"127.0.0.1:{cfg.ports.get(name, e.port)}" if e.port else "files in the container"
        print(f"      {e.title:<14} {where:<22} {e.connection_hint(cfg)}")
    for name in cfg.consoles:
        if name in cfg.ports:
            print(f"      {name:<14} http://127.0.0.1:{cfg.ports[name]}/")
    return 0


def down(argv=None):
    ap = argparse.ArgumentParser(description="remove the stack and each engine's working data; the named SQLite volume stays")
    ap.parse_args(argv)
    if not os.path.exists(COMPOSE):
        compose.main([])
    print("down: discarding each engine's working data, including every copy; "
          "the next `make up` starts from the shipped samples", flush=True)
    return data_volumes.down().returncode


def check(argv=None):
    """The local gate: everything that needs no build."""
    ap = argparse.ArgumentParser(description="the local gate: bundle validation and generated files")
    ap.parse_args(argv)
    from megasamples import catalogue, okf_check, okf_fix_quotes, provenance
    steps = [("knowledge bundle", lambda: okf_check.main(["--bundle", "knowledge"])),
             ("frontmatter quoting", lambda: okf_fix_quotes.main(["--bundle", "knowledge", "--check"])),
             ("licence and provenance files", lambda: provenance.main(["--check"])),
             ("catalogue and README table", lambda: catalogue.main(["--check"])),
             ("port records reproducible", lambda: __import__("megasamples.ports_check", fromlist=["main"]).main([])),
             ("unit tests", lambda: subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=ROOT).returncode)]
    failed = []
    for label, fn in steps:
        print(f"== {label}")
        try:
            rc = fn()
        except SystemExit as exc:
            rc = exc.code
        if rc:
            failed.append(label)
    print(f"check: {len(failed)} failure(s)" + (f" -- {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
