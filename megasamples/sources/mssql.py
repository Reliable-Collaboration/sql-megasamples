#!/usr/bin/env python3
"""The throwaway SQL Server container used to open the two WideWorldImporters backups.

WideWorldImporters is the only dataset in this project with no script or CSV form: the transactional
rows are produced by randomised T-SQL, so the released `.bak` is the sole source of the released
data, and opening a `.bak` requires SQL Server. That means accepting Microsoft's Developer-edition
EULA, which is a decision for the person running the build, not for the build -- so this module
refuses to start the container until that acceptance is explicit.

Nothing licensed under that EULA is redistributed. The container is removed when the export finishes;
no SQL Server binary, tool or layer reaches the MySQL image; only the exported sample data, which is
MIT, is kept. See knowledge/licenses/microsoft-sql-server-developer-eula.md.
"""
import json, os, shlex, subprocess, sys, time

from megasamples.paths import ROOT
# pinned by digest: the tag floats, and an export has to be attributable to one build of one image.
# Refresh with `python3 -m megasamples pull-image mcr.microsoft.com/mssql/server:2025-CU11-ubuntu-24.04`.
IMAGE = os.environ.get("MSSQL_IMAGE", "mcr.microsoft.com/mssql/server:2025-CU11-ubuntu-24.04@sha256:"
                       "05644dad1266ca3d445d1e8f6d2ebb9a6a03df9a39376e0f7b48917356dca9d9")
NAME = os.environ.get("MSSQL_CONTAINER", "megasamples-build-mssql")
SA_PASSWORD = os.environ.get("MSSQL_SA_PASSWORD", "Megasamples!X02build")
TOOLS = "/opt/mssql-tools18/bin"
ENV_FLAG = "MEGASAMPLES_ACCEPT_MSSQL_EULA"

NOTICE = f"""\
This step runs Microsoft SQL Server 2025 Developer Edition in a container, which requires you to
accept Microsoft's End-User Licence Agreement:

    {IMAGE}
    https://go.microsoft.com/fwlink/?linkid=857698   (License_Dev_Linux.rtf)

    "BY USING THE SOFTWARE, YOU ACCEPT THESE TERMS. IF YOU DO NOT ACCEPT THEM, DO NOT USE THE
     SOFTWARE. ... to design, develop, test and demonstrate your programs. You may not use the
     software on a device or server in a production environment."

Running this target sets ACCEPT_EULA=Y on that container on your behalf, which is how acceptance is
expressed. It is a build-time step only: the container is deleted when the export finishes, and no
SQL Server code is copied into the published MySQL image.

You do not need this to use the published image, and you do not need it to build any other dataset.
It is needed only to re-derive WideWorldImporters from Microsoft's .bak files.

To accept and continue:

    {ENV_FLAG}=1 make wwi-export
"""


def require_acceptance(argv_accept=False):
    """Refuse to run until the operator has accepted the EULA, and record how they did it."""
    via = None
    if argv_accept:
        via = "--accept-eula"
    elif os.environ.get(ENV_FLAG) == "1":
        via = f"{ENV_FLAG}=1"
    if not via:
        print(NOTICE, file=sys.stderr)
        sys.exit(f"refusing to start SQL Server: the EULA has not been accepted "
                 f"(set {ENV_FLAG}=1 or pass --accept-eula)")
    print(f"  ! Microsoft SQL Server Developer EULA accepted via {via}; ACCEPT_EULA=Y will be set "
          f"on {NAME}")
    print(f"  ! terms: https://go.microsoft.com/fwlink/?linkid=857698 -- build-time use only, "
          f"nothing under this licence is redistributed")
    return via


def run(cmd, **kw):
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    return subprocess.run(cmd if isinstance(cmd, list) else shlex.split(cmd), **kw)


def state():
    p = run(["docker", "inspect", "-f", "{{.State.Status}}", NAME])
    return p.stdout.strip() if p.returncode == 0 else None


def start(mounts, memory="6g"):
    """Start the container. `mounts` is [(host path, container path, "ro"|"rw")]."""
    if state():
        run(["docker", "rm", "-f", NAME])
    cmd = ["docker", "run", "-d", "--name", NAME,
           "--label", "megasamples.transient=true", "--label", "megasamples.role=mssql",
           "-e", "ACCEPT_EULA=Y",                    # see require_acceptance()
           "-e", f"MSSQL_SA_PASSWORD={SA_PASSWORD}",
           "-e", "MSSQL_PID=Developer",
           "-e", "LC_ALL=C.UTF-8",                   # makes the ODBC driver emit UTF-8 for bcp -c
           "--memory", memory]
    for host, inside, mode in mounts:
        cmd += ["-v", f"{host}:{inside}:{mode}"]
    p = run(cmd + [IMAGE])
    if p.returncode != 0:
        sys.exit(f"could not start {NAME}: {p.stderr.strip()}")
    last = None
    for _ in range(180):
        probe = sqlcmd("SELECT 1", check=False)
        if probe.returncode == 0:
            return
        last = (probe.stdout + probe.stderr).strip()
        # A usage error ("Sqlcmd: The -h and the -y 0 options are mutually exclusive.") can never
        # be fixed by waiting, and burning the whole timeout on one makes a flag mistake look like
        # a slow server. A *connection* failure is different: sqlcmd reports it the same way, but
        # it is exactly what the first few seconds of startup look like, so only the usage form
        # ends the poll.
        if (last.startswith("Sqlcmd:") and "Sqlcmd: Error:" not in last) or state() != "running":
            break
        time.sleep(1)
    # the poll used to swallow this: a bad sqlcmd flag looks exactly like "not started yet"
    sys.exit(f"{NAME} never became ready. Last probe said:\n  {last}\n"
             + run(["docker", "logs", "--tail", "20", NAME]).stdout)


def stop():
    if state():
        run(["docker", "rm", "-f", NAME])


def sqlcmd(query, database=None, check=True, timeout=7200):
    cmd = ["docker", "exec", "-e", "LC_ALL=C.UTF-8", NAME, f"{TOOLS}/sqlcmd",
           "-S", "localhost", "-U", "sa", "-P", SA_PASSWORD, "-No", "-h", "-1", "-W", "-b",
           "-Q", query]
    if database:
        cmd[cmd.index("-Q"):cmd.index("-Q")] = ["-d", database]
    p = run(cmd, timeout=timeout)
    if check and p.returncode != 0:
        sys.exit(f"sqlcmd failed:\n{query[:400]}\n{p.stdout}{p.stderr}")
    return p


def bcp(query, database, out, field=b"\x1f", row=b"\x1e\n", timeout=7200):
    """Export one query. Terminators are given as hex so bcp reads them literally."""
    hexed = lambda b: "0x" + b.hex()
    p = run(["docker", "exec", "-e", "LC_ALL=C.UTF-8", NAME, f"{TOOLS}/bcp", query, "queryout", out,
             "-c", "-t", hexed(field), "-r", hexed(row),
             "-S", "localhost", "-U", "sa", "-P", SA_PASSWORD, "-d", database, "-u"],
            timeout=timeout)
    if p.returncode != 0 or "rows copied" not in p.stdout:
        sys.exit(f"bcp failed for {out}:\n{query[:400]}\n{p.stdout}{p.stderr}")
    return int(p.stdout.split("rows copied")[0].strip().rsplit("\n", 1)[-1].strip().replace(",", ""))


def server_facts(accepted_via):
    """What the export is attributable to: image, engine build, and how the EULA was accepted."""
    version = sqlcmd("SET NOCOUNT ON; SELECT @@VERSION").stdout.strip()
    digest = run(["docker", "image", "inspect", IMAGE, "-f", "{{.Id}}"]).stdout.strip()
    bcp_version = run(["docker", "exec", NAME, f"{TOOLS}/bcp", "-v"]).stdout.strip().splitlines()
    return {"image": IMAGE, "image_id": digest, "version": version,
            "bcp": next((l.split(":", 1)[1].strip() for l in bcp_version if l.startswith("Version")),
                        "?"),
            "eula": {"accepted": True, "via": accepted_via,
                     "terms": "https://go.microsoft.com/fwlink/?linkid=857698",
                     "note": "build-time use only; nothing licensed under it is redistributed"},
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
