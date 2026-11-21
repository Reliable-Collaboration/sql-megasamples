#!/usr/bin/env python3
"""What this project has running, and how to get rid of it.

  python3 -m megasamples status status     what is up: the compose stack, and any throwaway container
  python3 -m megasamples status clean      remove the throwaway containers, leave the stack alone
  python3 -m megasamples status clean --all   also `docker compose down`

Two kinds of container exist and they are not the same kind of thing:

* The **stack** -- the engines and the consoles megasamples.yaml names -- is one Compose project,
  `sql-megasamples`.
  It comes up and goes down together (`docker compose up -d` / `docker compose down`) and is the only
  thing meant to keep running.
* Everything else is **transient**: the build server that datasets are loaded into, the SQL Server
  used to export WideWorldImporters, the loader image, the throwaway servers the tests start. Each
  carries `megasamples.transient=true`, which is what this script finds them by, so a container added
  later is covered without editing a list here.

The build server is deliberately reused across a build session -- starting a fresh MySQL for every
dataset would be slow, and `load.py` then `dump.py` both want the same one -- so nothing removes it
automatically. Remove it when the session is over; everything in it is reproducible from
`build/mysql/dumps` and the loaders.
"""
import argparse, json, subprocess, sys

LABEL = "megasamples.transient=true"
PROJECT = "sql-megasamples"
# Containers started before the label existed, and any started with the environment overrides in
# db.py / mssql.py left at their defaults. Matching both ways means an older workspace still cleans.
KNOWN = ("megasamples-build-mysql", "megasamples-build-mssql", "megasamples-build-oracle",
         "megasamples-test-mysql", "megasamples-test-mysql2", "megasamples-audit",
         "mms-build", "mms-mssql", "mms-oracle", "mms-image-test", "mms-image-test2", "mms-audit")


def docker(*args, check=False):
    p = subprocess.run(["docker", *args], capture_output=True, text=True)
    if check and p.returncode != 0:
        sys.exit(f"docker {' '.join(args)} failed: {p.stderr.strip()[:300]}")
    return p


def listing(*filters):
    fmt = "{{json .}}"
    p = docker("ps", "-a", "--format", fmt, *[a for f in filters for a in ("--filter", f)])
    out = []
    for line in p.stdout.splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def role(name):
    p = docker("inspect", "-f", "{{index .Config.Labels \"megasamples.role\"}}", name)
    return p.stdout.strip() or "?"


def transient_containers():
    """Everything labelled transient, plus any known name that predates the label."""
    found = {c["Names"]: c for c in listing(f"label={LABEL}")}
    for name in KNOWN:
        if name in found:
            continue
        for c in listing(f"name=^{name}$"):
            found[c["Names"]] = {**c, "matched": "name"}
    return list(found.values())


def status():
    stack = listing(f"label=com.docker.compose.project={PROJECT}")
    transient = transient_containers()

    print(f"stack ({PROJECT}) -- up and down together:")
    for c in sorted(stack, key=lambda c: c["Names"]):
        print(f"  {c['Names']:<26} {c['State']:<9} {c['Status']}")
    if not stack:
        print("  (nothing running; `docker compose up -d` starts it)")

    print("\ntransient -- safe to remove whenever the work using them is done:")
    for c in sorted(transient, key=lambda c: c["Names"]):
        print(f"  {c['Names']:<26} {c['State']:<9} role={role(c['Names']):<7} {c['Status']}")
    if not transient:
        print("  (none)")
    return 0


def remove_unlabelled(names):
    """Containers found only by a name from before the transient label. On a shared daemon such a name may be
    another project's container, so its volumes stay (Opus round 10, N2); a labelled one goes with them."""
    if names:
        docker("rm", "-f", *names, check=True)


def clean(also_stack=False):
    transient = transient_containers()
    if not transient:
        print("no transient containers to remove")
    else:
        names = [c["Names"] for c in transient]
        labelled = [c["Names"] for c in transient if c.get("matched") != "name"]
        if labelled:
            docker("rm", "-fv", *labelled, check=True)
        remove_unlabelled([c["Names"] for c in transient if c.get("matched") == "name"])
        for n in names:
            print(f"  removed {n}")

    if also_stack:
        from megasamples import data_volumes
        p = data_volumes.down(capture=True)
        print("  stack down" if p.returncode == 0
              else f"  could not bring the stack down: {p.stderr.strip()[:200]}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=["status", "clean"], nargs="?", default="status")
    ap.add_argument("--all", action="store_true",
                    help="with `clean`: also bring the compose stack down")
    a = ap.parse_args(argv)
    return status() if a.action == "status" else clean(a.all)


def main_status(argv=None):
    return main(["status"] + list(argv or []))


def main_clean(argv=None):
    return main(["clean"] + list(argv or []))


if __name__ == "__main__":
    sys.exit(main())
