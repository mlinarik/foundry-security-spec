"""Build-time scanner verification; extracted names and destinations are fixed."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen

for scanner in json.loads(Path('/build/scanners.json').read_text())["scanners"]:
    with urlopen(scanner["url"], timeout=120) as response:
        archive = response.read()
    if hashlib.sha256(archive).hexdigest() != scanner["sha256"]:
        raise ValueError("Scanner archive digest mismatch: " + scanner["name"])
    if scanner["name"] == "gitleaks":
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            member = bundle.getmember("gitleaks")
            if not member.isfile():
                raise ValueError("Expected regular executable")
            binary = bundle.extractfile(member).read()
    else:
        binary = archive
    destination = Path('/usr/local/bin') / scanner['name']
    destination.write_bytes(binary)
    destination.chmod(0o755)
