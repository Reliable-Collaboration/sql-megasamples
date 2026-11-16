#!/usr/bin/env python3
"""Pull an OCI image with native Podman, or an IPv4 archive import for Docker.

  python3 -m megasamples pull-image mcr.microsoft.com/mssql/server:2022-latest

Why this exists: on this machine `docker pull mcr.microsoft.com/...` fails with a bare `EOF` from the
manifest request while `curl -4` to the same URL answers in 0.15 s, which is the IPv6 signature the
runbook puts first (knowledge/runbooks/ipv6-and-privileges.md section 1d). The daemon-level fix needs
a Docker Desktop change, so section 2's no-privilege workaround applies instead: do the transfer with
`curl -4` and load the result.

Podman uses its native importer to preserve image-index digest references and platform selection.
Docker uses the IPv4 archive path below.

This is not a looser fetch than `docker pull`. Every blob is verified against the digest the registry
named, the manifest digest is printed so the caller can pin `image@sha256:...`, and nothing is
believed that was not checked. Anonymous registries only (MCR); a registry that answers 401 with a
`WWW-Authenticate` challenge gets a token fetched from the realm it names.
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tarfile, tempfile

from megasamples.paths import ROOT
ACCEPT = ", ".join((
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json"))
INDEX_TYPES = {"application/vnd.oci.image.index.v1+json",
               "application/vnd.docker.distribution.manifest.list.v2+json"}


def curl(url, out=None, headers=(), fail=True):
    """One IPv4 request. Returns (body_or_None, headers_text)."""
    cmd = ["curl", "-4", "-sS", "--location", "--retry", "3", "--retry-all-errors",
           "--connect-timeout", "20", "-D", "-"]
    for h in headers:
        cmd += ["-H", h]
    cmd += ["-o", out or "-", url]
    p = subprocess.run(cmd, capture_output=True, timeout=3600)
    if p.returncode != 0 and fail:
        sys.exit(f"curl failed for {url}: {p.stderr.decode('utf-8', 'replace').strip()}")
    if out:
        return None, p.stdout.decode("utf-8", "replace")
    # with -o - the body and the headers both land on stdout; the headers come first
    blob = p.stdout
    sep = blob.find(b"\r\n\r\n")
    while True:                      # a redirect chain emits one header block per hop
        nxt = blob.find(b"\r\n\r\n", sep + 4)
        if nxt < 0 or not blob[sep + 4:sep + 9].upper().startswith(b"HTTP"):
            break
        sep = nxt
    return blob[sep + 4:], blob[:sep].decode("utf-8", "replace")


def split_ref(ref):
    """`host/repo:tag`, and also Docker Hub's shorthands: `debian:12-slim`, `library/debian`.

    A first segment with no dot and no colon is not a hostname, so it belongs to the repository and
    the registry is Docker Hub -- where a single-segment name additionally lives under `library/`.
    """
    head = ref.split("/", 1)[0]
    if "/" not in ref or not ("." in head or ":" in head or head == "localhost"):
        ref = "registry-1.docker.io/" + ("library/" + ref if "/" not in ref else ref)
    host, rest = ref.split("/", 1)
    if "@" in rest:
        repo, tag = rest.split("@", 1)
        if ":" in repo.rsplit("/", 1)[-1]:
            repo = repo.rsplit(":", 1)[0]
    elif ":" in rest.rsplit("/", 1)[-1]:
        repo, tag = rest.rsplit(":", 1)
    else:
        repo, tag = rest, "latest"
    return host, repo, tag


def auth_headers(host, repo, header_text):
    """Answer a 401 challenge by fetching an anonymous token from the realm it names."""
    m = re.search(r'(?im)^www-authenticate:\s*Bearer\s+(.*)$', header_text)
    if not m:
        return []
    fields = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    realm = fields.pop("realm", None)
    if not realm:
        return []
    query = "&".join(f"{k}={v}" for k, v in fields.items()) or f"scope=repository:{repo}:pull"
    body, _ = curl(f"{realm}?{query}")
    token = json.loads(body).get("token") or json.loads(body).get("access_token")
    return [f"Authorization: Bearer {token}"] if token else []


def get_manifest(host, repo, reference, headers):
    url = f"https://{host}/v2/{repo}/manifests/{reference}"
    body, head = curl(url, headers=[f"Accept: {ACCEPT}"] + headers)
    if re.match(r"HTTP/[\d.]+ 401", head):
        headers = auth_headers(host, repo, head)
        body, head = curl(url, headers=[f"Accept: {ACCEPT}"] + headers)
    if not re.search(r"HTTP/[\d.]+ 200", head):
        sys.exit(f"{url}: {head.splitlines()[0] if head else 'no response'}")
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    named = re.search(r"(?im)^docker-content-digest:\s*(\S+)", head)
    if named and named.group(1) != digest:
        sys.exit(f"manifest digest mismatch: registry says {named.group(1)}, body hashes {digest}")
    return json.loads(body), body, digest, headers


def blob(host, repo, digest, dest, headers, size=None):
    path = os.path.join(dest, "blobs", "sha256", digest.split(":", 1)[1])
    if os.path.exists(path) and (size is None or os.path.getsize(path) == size) \
            and sha256_of(path) == digest:
        print(f"  = {digest[7:19]} {os.path.getsize(path):>12,} bytes (cached)")
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    curl(f"https://{host}/v2/{repo}/blobs/{digest}", out=path, headers=headers)
    got = sha256_of(path)
    if got != digest:
        sys.exit(f"blob {digest} hashed {got}")
    print(f"  + {digest[7:19]} {os.path.getsize(path):>12,} bytes")
    return path


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ref", help="host/repo:tag, e.g. mcr.microsoft.com/mssql/server:2022-latest")
    ap.add_argument("--dest", default=os.path.join(ROOT, "downloads", "_images"))
    ap.add_argument("--platform", default="linux/amd64")
    a = ap.parse_args(argv)
    from megasamples import container_engine
    if container_engine.podman():
        # Podman's importer preserves index/digest references. Its OCI-archive loader rejects an
        # index-pinned name on the single-platform archive used for Docker's IPv4 workaround.
        return subprocess.run(["docker", "pull", "--platform", a.platform, a.ref]).returncode
    host, repo, tag = split_ref(a.ref)
    dest = os.path.join(a.dest, repo.replace("/", "_") + "_" + tag.replace(":", "_"))
    os.makedirs(dest, exist_ok=True)

    manifest, raw, digest, headers = get_manifest(host, repo, tag, [])
    if manifest.get("mediaType") in INDEX_TYPES:
        want_os, want_arch = a.platform.split("/")
        for entry in manifest["manifests"]:
            p = entry.get("platform", {})
            if p.get("os") == want_os and p.get("architecture") == want_arch:
                manifest, raw, digest, headers = get_manifest(host, repo, entry["digest"], headers)
                break
        else:
            sys.exit(f"{a.ref} has no {a.platform} manifest")
    print(f"{a.ref}\n  manifest {digest}")

    os.makedirs(os.path.join(dest, "blobs", "sha256"), exist_ok=True)
    with open(os.path.join(dest, "blobs", "sha256", digest.split(":", 1)[1]), "wb") as fh:
        fh.write(raw)
    blob(host, repo, manifest["config"]["digest"], dest, headers, manifest["config"].get("size"))
    for layer in manifest["layers"]:
        blob(host, repo, layer["digest"], dest, headers, layer.get("size"))

    with open(os.path.join(dest, "oci-layout"), "w") as fh:
        json.dump({"imageLayoutVersion": "1.0.0"}, fh)
    index = {"schemaVersion": 2, "manifests": [{
        "mediaType": manifest.get("mediaType",
                                  "application/vnd.oci.image.manifest.v1+json"),
        "digest": digest, "size": len(raw),
        "annotations": {"io.containerd.image.name": a.ref,
                        "org.opencontainers.image.ref.name": tag}}]}
    with open(os.path.join(dest, "index.json"), "w") as fh:
        json.dump(index, fh)

    archive = os.path.join(dest, "image.tar")
    with tarfile.open(archive, "w") as tar:
        for name in ("oci-layout", "index.json", "blobs"):
            tar.add(os.path.join(dest, name), arcname=name)
    print(f"  loading {os.path.getsize(archive):,} bytes into Docker")
    p = subprocess.run(["docker", "load", "-i", archive], text=True)
    os.remove(archive)
    if p.returncode != 0:
        sys.exit("docker load failed")
    print(f"\nPIN for the build: {host}/{repo}@{digest}")


if __name__ == "__main__":
    sys.exit(main())
