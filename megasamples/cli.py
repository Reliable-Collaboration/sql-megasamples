"""The command line: `python3 -m megasamples <command> [args]`.

Every command is a module with a `main(argv)`; this file only names them. `make` targets are
one-line shims over the same commands, so `make -n <target>` shows exactly what will run.
"""
import importlib, sys

# name -> (module, function, one-line help). Grouped as `--help` prints them.
COMMANDS = {
    # the stack
    "configure":    ("megasamples.configure", "main", "choose engines x datasets and consoles; writes megasamples.yaml"),
    "list":         ("megasamples.matrix", "main", "what exists: engines, datasets with tiers and sizes, consoles"),
    "run":          ("megasamples.job", "main", "the whole job from megasamples.yaml: fetch, build, image, up"),
    "compose":      ("megasamples.compose", "main", "write compose.yaml from megasamples.yaml"),
    "up":           ("megasamples.job", "up", "regenerate the landing page and start the stack"),
    "down":         ("megasamples.job", "down", "stop the stack"),
    "reset":        ("megasamples.reset", "main", "put databases back as the images ship them: all, engines, or engine:dataset pairs"),
    "status":       ("megasamples.workspace", "main_status", "what is running: the stack, and any transient container"),
    "clean":        ("megasamples.workspace", "main_clean", "remove the transient containers (--all: the stack too)"),
    # the pipeline
    "fetch":        ("megasamples.fetch", "main", "download and verify upstream artifacts (once; a monitor shows progress)"),
    "stage":        ("megasamples.stage", "main", "convert a dataset's artifacts into MySQL SQL under build/stage/"),
    "build":        ("megasamples.job", "build", "fetch, stage, load and verify datasets on an engine"),
    "load":         ("megasamples.engines.mysql.load", "main", "load a staged dataset into the MySQL build server"),
    "verify":       ("megasamples.verify", "main", "run the verification stages against a loaded dataset"),
    "dump":         ("megasamples.engines.mysql.dump", "main", "dump a loaded dataset from the MySQL build server"),
    "restore":      ("megasamples.engines.mysql.restore", "main", "reload datasets into the MySQL build server from their dumps"),
    "image":        ("megasamples.job", "image", "bake the configured datasets into an engine's image"),
    "test-image":   ("megasamples.job", "test_image", "run the image-level tests against a built image"),
    "test-console": ("megasamples.console_test", "main", "assert the consoles are up and the accounts behave"),
    "build-server": ("megasamples.engines.mysql.server", "main", "start | stop | fresh | status of the MySQL build server"),
    "pg-server":    ("megasamples.engines.postgres.server", "main", "start | stop | fresh | status of the PostgreSQL build server"),
    "pg-port":      ("megasamples.engines.postgres.port", "main", "port a dataset from the MySQL corpus to PostgreSQL and load it"),
    "sqlite-port":  ("megasamples.engines.sqlite.port", "main", "port a dataset from the MySQL corpus to a SQLite file"),
    "registry":     ("megasamples.registry", "main", "write the provenance registry SQL for the named datasets"),
    "console-page": ("megasamples.console_page", "main", "generate the landing page from the running stack"),
    "console-config": ("megasamples.console_config", "main", "write the console configuration files the stack needs (CloudBeaver connections)"),
    # documents and checks
    "catalogue":    ("megasamples.catalogue", "main", "regenerate CATALOGUE.md and the README table (--check)"),
    "provenance":   ("megasamples.provenance", "main", "regenerate LICENSE, PROVENANCE.md, LICENSES.md, NOTICE.md (--check)"),
    "check":        ("megasamples.job", "check", "the local gate: bundle, generated files, compose"),
    "ports-check":  ("megasamples.ports_check", "main", "re-render every port's DDL and compare it with the committed files"),
    "okf-check":    ("megasamples.okf_check", "main", "validate the knowledge bundle"),
    "okf-fix-quotes": ("megasamples.okf_fix_quotes", "main", "normalise frontmatter quoting in the bundle"),
    "audit-assets": ("megasamples.audit", "main", "prove nothing unredistributable is in the repo or an image"),
    "prepub-check": ("megasamples.prepub", "main", "the pre-publication checklist"),
    # source-side tools
    "pull-image":   ("megasamples.pull_image", "main", "pull an image over IPv4 and load it into Docker"),
    "wwi-export":   ("megasamples.sources.wwi_export", "main", "export WideWorldImporters from SQL Server (EULA gate)"),
    "verify-oracle": ("megasamples.sources.verify_oracle", "main", "cross-check the Oracle datasets against Oracle (licence gate)"),
    "bikeshare":    ("megasamples.sources.bikeshare", "main", "load one month of Citi Bike or Divvy (licence gate)"),
    "tpcc-load":    ("megasamples.sources.tpcc_load", "main", "load TPC-C through sysbench in the loader image"),
    "tpc-check":    ("megasamples.sources.tpc_check", "main", "check a generated TPC-H/DS load against the specification"),
    "bench":        ("megasamples.engines.mysql.bench", "main", "time a load with indexes before and after"),
}


def usage():
    width = max(len(n) for n in COMMANDS)
    print(__doc__.strip().splitlines()[0])
    print()
    for name, (_, _, text) in COMMANDS.items():
        print(f"  {name:<{width}}  {text}")
    print("\n  <command> --help   for the command's own options")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help", "help"):
        usage()
        return 0
    name, rest = argv[0], argv[1:]
    if name not in COMMANDS:
        print(f"unknown command {name!r}\n")
        usage()
        return 2
    module_name, func_name, _ = COMMANDS[name]
    module = importlib.import_module(module_name)
    sys.argv = [f"megasamples {name}"] + rest
    result = getattr(module, func_name)(rest)
    return int(result or 0)
