"""The dataset inventory: every datasets/<name>/dataset.yaml, with tiers, dependencies and build order.

A dataset directory holds the contract (`dataset.yaml`), the converter that turns the upstream
artifact into MySQL SQL (`convert.py`), the engine-neutral expectations every engine is verified
against (`tests/`), and the generated `LICENSE` and `PROVENANCE.md`. The contract's keys:

    name        the dataset (directory) name
    database    the database it loads into; normally the same, but an `append: true` dataset adds
                tables to a database another dataset created
    tier        core | core-medium | extended | generated | user-fetched | not-shipped
    quick       true for the subset that builds in minutes with no large download
    record      the knowledge record behind it
    licenses    licence record ids
    artifacts   manifest ids it downloads
    stage       how the converter is run (see stage.py)
    load        the staged SQL files, in load order
    depends     datasets that must be loaded first (cross-database foreign keys)
    build_license  a licence accepted at build time only (never in the image)
    blurb       a one-line description for the catalogue, when the record's is not written for readers
    live        true for a dataset built from a feed that changes: its artifacts are taken as served
                and its tests describe a snapshot (floors and structure), see megasamples/verify.py
"""
import functools, os

import yaml

from megasamples.paths import DATASETS, MANIFEST

TIERS = ("core", "core-medium", "extended", "generated", "user-fetched", "not-shipped")
SELECTORS = ("core", "quick", "all", "extended", "generated")


def load(name):
    path = os.path.join(DATASETS, name, "dataset.yaml")
    if not os.path.exists(path):
        raise KeyError(f"no such dataset: {name} ({path} does not exist)")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    cfg.setdefault("name", name)
    return cfg


@functools.lru_cache(maxsize=None)
def inventory():
    """{name: contract} for every dataset, in name order."""
    out = {}
    for name in sorted(os.listdir(DATASETS)):
        if os.path.exists(os.path.join(DATASETS, name, "dataset.yaml")):
            out[name] = load(name)
    return out


def names():
    return list(inventory())


def by_tier(*tiers):
    return [n for n, c in inventory().items() if c.get("tier") in tiers]


def core():
    return build_order(by_tier("core", "core-medium"))


def quick():
    return build_order([n for n, c in inventory().items() if c.get("quick")])


@functools.lru_cache(maxsize=None)
def manifest_sizes():
    """Bytes per artifact id, from manifest.yaml."""
    with open(MANIFEST, encoding="utf-8") as fh:
        arts = (yaml.safe_load(fh) or {}).get("artifacts") or []
    return {a["id"]: int(a.get("size_bytes") or 0) for a in arts}


def download_bytes(name):
    sizes = manifest_sizes()
    return sum(sizes.get(i, 0) for i in inventory()[name].get("artifacts") or [])


def base_dataset(name):
    """For an `append: true` dataset, the dataset that creates the database it appends to."""
    cfg = inventory()[name]
    if not cfg.get("append"):
        return None
    for other, c in inventory().items():
        if c.get("database") == cfg.get("database") and not c.get("append"):
            return other
    return None


def prerequisites(name):
    """Datasets that must be loaded before this one."""
    cfg = inventory()[name]
    pre = list(cfg.get("depends") or [])
    base = base_dataset(name)
    if base:
        pre.append(base)
    return pre


def build_order(selected):
    """Smallest download first, with every prerequisite before what needs it.

    Fail-fast ordering: a converter bug in a 1 MB dataset shows up before the 500 MB one starts.
    The order is deterministic for a given manifest, so two machines build in the same sequence.
    """
    wanted = list(dict.fromkeys(selected))
    ranked = sorted(wanted, key=lambda n: (download_bytes(n), n))
    out, seen = [], set()

    def place(n):
        if n in seen:
            return
        seen.add(n)
        for p in prerequisites(n):
            if p not in inventory():
                raise KeyError(f"{n} depends on {p}, which is not in the inventory")
            place(p)
        out.append(n)

    for n in ranked:
        place(n)
    return out


def select(spec):
    """Expand a selector into an ordered list of dataset names.

    `spec` is "core", "quick", "all", a tier name, a single name, or a list mixing any of these.
    """
    if spec is None:
        return []
    items = spec if isinstance(spec, list) else [spec]
    chosen = []
    for item in items:
        if item == "core":
            chosen += by_tier("core", "core-medium")
        elif item == "quick":
            chosen += [n for n, c in inventory().items() if c.get("quick")]
        elif item == "all":
            chosen += names()
        elif item in TIERS:
            chosen += by_tier(item)
        elif item in inventory():
            chosen.append(item)
        else:
            raise KeyError(f"unknown dataset or selector: {item!r}")
    return build_order(chosen)
