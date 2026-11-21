"""The engines' anonymous data volumes, and the stack routes that replace or remove their containers.

The engine images declare their data directories as volumes, and the stack mounts none in their place, so
each engine's data lives in an anonymous volume. Docker never reattaches one once its container is gone:
Compose's `down` and `up --renew-anon-volumes` leave the old ones behind unless they are removed with the
container or by name. Removal here touches anonymous volumes only (a 64-digit hex name); the named volume
the SQLite consoles share is never one of them.
"""
import json, re, subprocess

from megasamples.paths import COMPOSE, ROOT


def attached(container):
    """The anonymous volumes a container's data lives in."""
    mounts = subprocess.run(["docker", "inspect", "-f", "{{json .Mounts}}", container], capture_output=True, text=True)
    if mounts.returncode != 0:
        return []
    return [m["Name"] for m in json.loads(mounts.stdout or "[]")
            if m.get("Type") == "volume" and re.fullmatch(r"[0-9a-f]{64}", m.get("Name") or "")]


def remove_replaced(replaced, attached=attached, report=print):
    """Remove each recorded volume its container no longer mounts, by name (never a prune)."""
    for container, volumes in replaced.items():
        current = attached(container)
        for volume in volumes:
            if volume in current:
                continue
            removed = subprocess.run(["docker", "volume", "rm", volume], capture_output=True, text=True)
            report(f"  . removed the replaced data volume {volume[:12]}" if removed.returncode == 0
                   else f"  ! could not remove the replaced data volume {volume}: {removed.stderr.strip()[:200]}")


def compose_images():
    """The image Compose resolves for each service, with .env's overrides applied ({} if it cannot say)."""
    resolved = subprocess.run(["docker", "compose", "-f", COMPOSE, "config", "--format", "json"], cwd=ROOT,
                              capture_output=True, text=True)
    if resolved.returncode != 0:
        return {}
    try:
        services = json.loads(resolved.stdout).get("services", {})
    except json.JSONDecodeError:
        return {}
    return {name: service["image"] for name, service in services.items() if service.get("image")}


def recreate(services, containers, attached=attached, report=print):
    """Recreate services from their images with fresh data directories, then remove the volumes replaced."""
    replaced = {container: attached(container) for container in containers}
    try:
        return 1 if subprocess.run(["docker", "compose", "-f", COMPOSE, "up", "-d", "--force-recreate",
                                    "--renew-anon-volumes", "--no-deps", "--wait", *services],
                                   cwd=ROOT).returncode != 0 else 0
    finally:
        # On every exit: Compose may have renewed the volumes before --wait gave up.
        # A volume its container still mounts is skipped, so a recreate that failed earlier keeps its data.
        remove_replaced(replaced, attached, report)


def down(capture=False):
    """Bring the stack down with each container's anonymous volumes. Compose's `rm --volumes` removes
    anonymous volumes only, so the named SQLite volume stays; `down` then removes the network."""
    options = {"cwd": ROOT, "capture_output": capture, "text": True}
    removed = subprocess.run(["docker", "compose", "-f", COMPOSE, "rm", "--stop", "--force", "--volumes"], **options)
    if removed.returncode != 0:
        return removed
    return subprocess.run(["docker", "compose", "-f", COMPOSE, "down"], **options)
