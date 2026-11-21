"""Every container megasamples removes goes with its anonymous volumes (round 9's batch finding).

`docker rm -f` without `-v` leaves the image's declared volumes behind: `megasamples test-image` left one per
MySQL run. Once its container is gone an anonymous volume cannot be reached again (no later `docker run`
reattaches it), so nothing is kept by leaving it; `-v` removes anonymous volumes only, never a named
volume or a bind mount, so a container whose data must persist keeps it in a named volume regardless.
The class: every removal call in megasamples/, by its source text, so a new one is covered too.
"""

import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
# A container removal is docker's rm subcommand and its options, as separate arguments of one call:
# ("docker", "rm", "-f", ...) or the workspace helper's docker("rm", "-f", ...). A file removal run inside
# a container (docker exec ... rm -rf) and docker volume rm are not container removals.
REMOVAL = re.compile(r"""(?:["']docker["']\s*,\s*|\bdocker\(\s*)["']rm["']\s*,\s*["'](-[a-z]+)["']""")
# Removals that must keep a container's anonymous volumes, each with its reason. None today.
KEEPS_VOLUMES = {}


def removals():
    for path in sorted((ROOT / "megasamples").rglob("*.py")):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            for options in REMOVAL.findall(line):
                yield f"{path.relative_to(ROOT)}:{number}", options


def test_the_class_is_found():
    found = list(removals())
    assert len(found) >= 20, found      # 17 found by round 9's batch, plus the three already with -v


def test_every_container_removal_takes_its_anonymous_volumes():
    leaking = [where for where, options in removals() if "f" in options and "v" not in options
               and where.split(":")[0] not in KEEPS_VOLUMES]
    assert leaking == [], leaking
