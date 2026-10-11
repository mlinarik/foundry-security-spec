"""Capture official base manifest digest and verify upstream scanner assets."""
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


def fetch(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=45) as response:
        return response.read(), response.headers


def main():
    token_data, _ = fetch("https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull")
    token = json.loads(token_data)["token"]
    manifest, headers = fetch("https://registry-1.docker.io/v2/library/python/manifests/3.12-slim-bookworm", {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json"})
    digest = headers["Docker-Content-Digest"]
    assert hashlib.sha256(manifest).hexdigest() == digest.removeprefix("sha256:")
    scanners = []
    for name, version, repo, checksum_name, asset in [
        ("osv-scanner", "2.6.0", "google/osv-scanner", "osv-scanner_SHA256SUMS", "osv-scanner_linux_amd64"),
        ("gitleaks", "8.30.1", "gitleaks/gitleaks", "gitleaks_8.30.1_checksums.txt", "gitleaks_8.30.1_linux_x64.tar.gz")]:
        base = f"https://github.com/{repo}/releases/download/v{version}/"
        checksums, _ = fetch(base + checksum_name)
        expected = next(line.split()[0] for line in checksums.decode().splitlines() if line.split()[-1].lstrip('*') == asset)
        archive, _ = fetch(base + asset)
        assert hashlib.sha256(archive).hexdigest() == expected, name
        scanners.append({"name": name, "version": version, "url": base+asset, "sha256": expected, "asset": asset})
    target = Path(__file__).parent
    (target/"scanners.json").write_text(json.dumps({"architecture":"linux/amd64", "scanners":scanners},indent=2)+"\n")
    (target/"base-image.json").write_text(json.dumps({"source":"python:3.12-slim-bookworm", "reference":"python@"+digest},indent=2)+"\n")
    print("Verified official base digest and both scanner checksums")


if __name__ == "__main__":
    main()
