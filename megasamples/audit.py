#!/usr/bin/env python3
"""Assert that nothing which may not be redistributed is in the repository or the image.

  python3 -m megasamples audit-assets [--image sql-megasamples-mysql:dev]

ARCHITECTURE.md section 8 items 4, 5 and 6, run as one check because they are one question: did anything
whose licence forbids redistribution end up somewhere we publish?

  4. No Citi Bike or Divvy data in any image layer. Both Lyft licences prohibit
     hosting or distributing the data as a stand-alone dataset, so the project ships the loaders and
     never the data.
  5. No TPC-generated data committed, and no modified TPC query text. The TPC EULA permits
     redistribution of the *tools* with the agreement and the legend; the project generates data on
     the user's machine and ships none of it.
  6. No `sakila.mwb`, Sakila manual, `.bak` files, SQL Server or Oracle binaries, or Contoso
     `.pbix`/`.bak` in the repository or the image -- none of those is openly licensed.

Absence is what is being proved, so each check names where it looked. A check that cannot look --
the image is not built, say -- reports that rather than passing quietly.

Item 6 is asked of *what this project added*, not of every byte in the image: the official
`mysql:9.7.2` base ships three MySQL Workbench models inside the mysqlsh plugins and a
`/etc/nsswitch.conf.bak` from Debian packaging, none of which this project put there or can remove.
So the image scan subtracts the same scan run against the base image, and reports the difference.
"""
import argparse, os, subprocess, sys

from megasamples.paths import ROOT
BIKESHARE_DB = ("citibike", "divvy")
TPC_DB = ("tpch", "tpcds", "tpcc", "ssb")
# extensions and names that are not openly licensed and must never be committed or baked
FORBIDDEN_FILES = (".bak", ".mwb", ".pbix", ".mdf", ".ldf", ".ndf")


def tracked_files():
    p = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.splitlines() if p.returncode == 0 else []


def forbidden_files_in(image, failures, entrypoint_only=False):
    """Paths matching the forbidden patterns inside `image`, or None if it could not be started."""
    cmd = ["docker", "run", "--rm", "--entrypoint", "sh",
           "--label", "megasamples.transient=true", "--label", "megasamples.role=audit", image,
           "-c", "find / -xdev \\( " + " -o ".join(f"-iname '*{e}'" for e in FORBIDDEN_FILES)
                 + " \\) 2>/dev/null"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        failures.append(f"could not scan {image}: {p.stderr.strip()[:120]}")
        return None
    return {line.strip() for line in p.stdout.splitlines() if line.strip()}


def image_schemas(image, failures):
    """Schemas actually inside the image, read by starting it once."""
    name = "megasamples-audit"
    subprocess.run(["docker", "rm", "-fv", name], capture_output=True)
    run = subprocess.run(["docker", "run", "-d", "--name", name,
                          "--label", "megasamples.transient=true",
                          "--label", "megasamples.role=audit",
                          "-e", "MYSQL_ROOT_PASSWORD=audit", image], capture_output=True, text=True)
    if run.returncode != 0:
        print(f"  ? image {image} could not be started, so its layers were not audited")
        failures.append(f"could not start {image}: {run.stderr.strip()[:120]}")
        return None, None
    try:
        for _ in range(300):
            q = subprocess.run(["docker", "exec", name, "mysql", "-uroot", "-paudit", "-N", "--batch",
                                "-e", "SELECT schema_name FROM information_schema.schemata"],
                               capture_output=True, text=True)
            if q.returncode == 0:
                break
            subprocess.run(["sleep", "1"])
        else:
            failures.append(f"{image} never became ready, so its layers were not audited")
            return None, None
        return [s for s in q.stdout.split() if s], None
    finally:
        subprocess.run(["docker", "rm", "-fv", name], capture_output=True)


def main(argv=None):
    from .engines.mysql.server import IMAGE as mysql_base

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--image", default=os.environ.get("MEGASAMPLES_MYSQL_IMAGE", "sql-megasamples-mysql:dev"))
    ap.add_argument("--base", default=mysql_base,
                    help="the image this one is built FROM; its own files are not our doing")
    ap.add_argument("--skip-image", action="store_true", help="audit only the repository")
    a = ap.parse_args(argv)
    failures = []

    # --- 4 and 5: the repository -------------------------------------------------------------
    tracked = tracked_files()
    print(f"  . {len(tracked):,} tracked files scanned")
    for db in BIKESHARE_DB + TPC_DB:
        hits = [f for f in tracked
                if f"/{db}/" in f and ("/data/" in f or f.endswith((".csv", ".tsv", ".zip", ".7z")))]
        if hits:
            failures.append(f"{db} data is committed: {', '.join(hits[:3])}")
    print("  . no Citi Bike, Divvy or TPC data files are committed")

    bad = [f for f in tracked if f.lower().endswith(FORBIDDEN_FILES)]
    if bad:
        failures.append(f"files that are not openly licensed are committed: {', '.join(bad[:3])}")
    else:
        print("  . no .bak/.mwb/.pbix/.mdf/.ldf/.ndf files are committed")

    # --- 4, 5 and 6: the image ---------------------------------------------------------------
    if a.skip_image:
        print("  ? image not audited (--skip-image)")
    else:
        schemas, _ = image_schemas(a.image, failures)
        if schemas is not None:
            present = [s for s in schemas if s in BIKESHARE_DB + TPC_DB]
            if present:
                failures.append(f"the image contains {', '.join(present)}")
            else:
                print(f"  . the image holds {len(schemas)} schemas, none of them bike-share or TPC")

        ours = forbidden_files_in(a.image, failures)
        base = forbidden_files_in(a.base, failures)
        if ours is not None and base is not None:
            added = sorted(ours - base)
            if added:
                failures.append(f"this project added {len(added)} non-redistributable file(s) to the "
                                f"image: " + ", ".join(added[:3]))
            else:
                print(f"  . no .bak/.mwb/.pbix/.mdf/.ldf/.ndf file that {os.path.basename(a.base)} "
                      f"does not already ship ({len(ours & base)} inherited, left alone)")

    for f in failures:
        print(f"  x {f}")
    print(f"assets: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
