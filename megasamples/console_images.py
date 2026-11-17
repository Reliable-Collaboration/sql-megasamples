"""Build console extensions from pinned vendor images and exact driver inputs."""
import os
import subprocess

from megasamples import consoles, container_engine, pull_image
from megasamples.paths import ROOT


def build(cfg):
    for name in cfg.consoles:
        console = consoles.get(name)
        if not console.dockerfile or not any(e in cfg.engines for e in console.engines):
            continue
        present = subprocess.run(['docker', 'image', 'inspect', console.image], capture_output=True)
        if present.returncode and pull_image.main([console.image]):
            return 1
        print(f'  . building {console.runtime_image} with pinned database drivers', flush=True)
        result = subprocess.run(['docker', 'build', '-f', console.dockerfile,
                                 '-t', console.runtime_image, os.path.dirname(console.dockerfile)],
                                cwd=ROOT, env=container_engine.build_env())
        if result.returncode:
            return result.returncode
    return 0
