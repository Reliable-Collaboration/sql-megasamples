"""Every container megasamples removes or replaces goes with its anonymous volumes (round 9's batch finding;
Opus round 10, P2-1 and P3-2; Sol round 10, P3-2).

`docker rm -f` without `-v` left the image's declared volume behind on every `test-image` run, and Compose's
`down` and `up --renew-anon-volumes` leave the engines' data volumes the same way. Once its container is gone,
an anonymous volume is never reattached, so nothing is kept by leaving it; `-v` removes anonymous volumes
only, never a named volume or a bind mount.

The class, read from megasamples/'s syntax tree, so no spelling or line split hides a call:
- `docker`/`podman` `rm` and `container rm`, through any call (`subprocess.run`, the `sh()` and `run()`
  wrappers, workspace's `docker()` helper) or inside a shell string: needs `-v` or `--volumes`;
- Compose `rm`: needs `--volumes`; Compose `down`: needs a Compose `rm --volumes` before it in the same
  function, and never `down -v`, which would remove the named SQLite volume too;
- Compose `up --force-recreate` or `--renew-anon-volumes`: the same function removes what it replaced, by
  calling `remove_replaced`.
An exemption names a file and function, with its reason.
"""

import ast
import re
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
CALLS = {"run", "sh", "docker", "Popen", "call", "check_call", "check_output"}
SHELL = re.compile(r"\b(?:docker|podman)\s+(?:container\s+)?rm\b[^;&|]*")
# Removals that must keep a container's anonymous volumes, by (file, function), each with its reason.
KEEPS_VOLUMES = {
    ("megasamples/workspace.py", "remove_unlabelled"):
        "containers matched by a name from before the transient label: on a shared daemon the name may be "
        "another project's container, so only the container goes and its volumes stay (Opus round 10, N2)",
}


def literal_argv(call):
    """The call's argument vector as strings, None for a value that is not a literal."""
    name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", None)
    if name not in CALLS:
        return None
    args = call.args
    if args and isinstance(args[0], (ast.List, ast.Tuple)):
        args = args[0].elts
    argv = [a.value if isinstance(a, ast.Constant) and isinstance(a.value, str) else None for a in args]
    if name == "docker" and argv[:1] != ["docker"]:
        argv = ["docker", *argv]
    return argv


def takes_volumes(options):
    return any(o in ("-v", "--volumes") or re.fullmatch(r"-[a-z]*v[a-z]*", o or "") for o in options)


def problems(source, where="<source>"):
    """Each removal or replacement in the source that leaves anonymous volumes, as (where:line, function)."""
    found = []
    tree = ast.parse(source)
    scopes = [("<module>", tree)] + [(n.name, n) for n in ast.walk(tree)
                                     if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for function, scope in scopes:
        own = [n for n in ast.walk(scope) if isinstance(n, ast.Call)]
        if function == "<module>":
            inner = {id(n) for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
                     for n in ast.walk(f)}
            own = [n for n in own if id(n) not in inner]
        else:
            nested = {id(n) for f in ast.walk(scope) if f is not scope
                      and isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(f)}
            own = [n for n in own if id(n) not in nested]
        own.sort(key=lambda n: (n.lineno, n.col_offset))
        compose_rm_with_volumes = False
        removes_replaced = any((getattr(n.func, "attr", None) or getattr(n.func, "id", None)) == "remove_replaced"
                               for n in own)
        for call in own:
            vectors = []
            argv = literal_argv(call)
            if argv and argv[0] in ("docker", "podman"):
                vectors.append(argv)
            for node in ast.walk(call):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    vectors += [shlex.split(m) for m in SHELL.findall(node.value)]
            for argv in vectors:
                words = [w for w in argv[1:] if w is not None]
                label = (f"{where}:{call.lineno}", function)
                if words[:1] == ["rm"] or words[:2] == ["container", "rm"]:
                    if not takes_volumes([w for w in words if w.startswith("-")]):
                        found.append(label)
                elif words[:1] == ["compose"]:
                    options = [w for w in words if w.startswith("-")]
                    if "rm" in words:
                        if takes_volumes(options):
                            compose_rm_with_volumes = True
                        else:
                            found.append(label)
                    elif "down" in words:
                        if takes_volumes(options) or not compose_rm_with_volumes:
                            found.append(label)
                    elif "up" in words and ({"--force-recreate", "--renew-anon-volumes"} & set(options)):
                        if not removes_replaced:
                            found.append(label)
    return found


def product():
    for path in sorted((ROOT / "megasamples").rglob("*.py")):
        relative = str(path.relative_to(ROOT))
        for label, function in problems(path.read_text(), relative):
            if (relative, function) not in KEEPS_VOLUMES:
                yield label


def test_every_container_removal_takes_its_anonymous_volumes():
    assert list(product()) == []


def test_each_exemption_still_names_a_removal():
    for (relative, function), reason in KEEPS_VOLUMES.items():
        assert reason
        assert any(f == function for _, f in problems((ROOT / relative).read_text(), relative)), relative


LEAKS = [
    'subprocess.run(["docker", "rm", "-f", name])',
    'subprocess.run(["docker", "rm", "--force", name])',
    'subprocess.run(["docker", "rm", name])',
    'subprocess.run(["docker", "container", "rm", "-f", name])',
    'sh("docker", "rm", "-f", NAME)',
    'docker("rm", "-f", *names)',
    'run(["podman", "rm", "-f", name])',
    'subprocess.run(["docker",\n    "rm",\n    "-f", name])',
    'subprocess.run(["sh", "-c", "docker rm -f x && true"])',
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "down"])',
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "rm", "--stop", "--force"])',
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "rm", "--stop", "--force", "--volumes"])\n'
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "down", "-v"])',
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "-d", "--force-recreate", "--renew-anon-volumes"])',
]
TAKES = [
    'subprocess.run(["docker", "rm", "-fv", name])',
    'subprocess.run(["docker", "rm", "-f", "-v", name])',
    'subprocess.run(["docker", "rm", "--volumes", "--force", name])',
    'subprocess.run(["docker", "container", "rm", "-vf", name])',
    'subprocess.run(["sh", "-c", "docker rm -fv x"])',
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "rm", "--stop", "--force", "--volumes"])\n'
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "down"])',
    'subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "--force-recreate", "--renew-anon-volumes"])\n'
    'remove_replaced(replaced)',
    'subprocess.run(["docker", "volume", "rm", volume])',
    'subprocess.run(["docker", "exec", name, "rm", "-rf", "/tmp/x"])',
]


@pytest.mark.parametrize("line", LEAKS)
def test_a_form_that_leaks_is_found(line):
    assert problems(f"def f():\n    {line.replace(chr(10), chr(10) + '    ')}\n") != []


@pytest.mark.parametrize("line", TAKES)
def test_a_form_that_takes_its_volumes_passes(line):
    assert problems(f"def f():\n    {line.replace(chr(10), chr(10) + '    ')}\n") == []


def test_an_exemption_covers_its_own_function_only():
    source = 'def keep():\n    sh("docker", "rm", "-f", a)\n\ndef other():\n    sh("docker", "rm", "-f", b)\n'
    exempt = {("x.py", "keep")}
    assert [f for _, f in problems(source, "x.py") if ("x.py", f) not in exempt] == ["other"]


def test_clean_takes_volumes_only_of_labelled_containers(monkeypatch):
    """Opus round 10, N2: a container found only by a name from before the label may be another project's on a
    shared daemon, so its volumes stay; a labelled transient container goes with its volumes."""
    import json
    import subprocess
    from megasamples import workspace
    calls = []

    def docker(*args, check=False):
        calls.append(args)
        out = ""
        if args[:2] == ("ps", "-a"):
            wanted = args[args.index("--filter") + 1]
            if wanted == f"label={workspace.LABEL}":
                out = json.dumps({"Names": "megasamples-build-mysql"})
            elif wanted == "name=^mms-build$":
                out = json.dumps({"Names": "mms-build"})
        return subprocess.CompletedProcess(args, 0, out, "")
    monkeypatch.setattr(workspace, "docker", docker)
    assert workspace.clean() == 0
    removals = [c for c in calls if c[0] == "rm"]
    assert ("rm", "-fv", "megasamples-build-mysql") in removals
    assert ("rm", "-f", "mms-build") in removals
    assert all("mms-build" not in c or c[1] == "-f" for c in removals)
