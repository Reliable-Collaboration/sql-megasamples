"""Run the real `megasamples reset` against a named, task-owned engine container.

    dl077_reset_target.py CONTAINER RESET-ARGS...

The stack's container name is fixed (`megasamples-postgres`); this points the PostgreSQL engine at
CONTAINER instead, and changes nothing else. Run from a checkout without a `.env`, so the factory
test passwords apply, and only against the isolated store.
"""

import sys

from megasamples.engines import registry


def run():
    container, *args = sys.argv[1:]
    registry.get("postgres").__class__.container = container
    from megasamples.reset import main
    return main(args)


if __name__ == "__main__":
    sys.exit(run())
