"""Prepare the pinned Oracle server plus matching LTS Shell before any use."""
import os
import subprocess

from megasamples import container_engine
from megasamples.paths import engine_dir

IMAGE = 'sql-megasamples-mysql-base:9.7.4-shell-9.7.1'


def build():
    context = engine_dir('mysql')
    args = ['docker', 'build', '-f', os.path.join(context, 'base.Dockerfile'), '-t', IMAGE, context]
    if subprocess.run(args, env=container_engine.build_env()).returncode:
        raise SystemExit('Could not prepare Oracle MySQL LTS base image')
    return 0


def main(argv=None):
    return build()
