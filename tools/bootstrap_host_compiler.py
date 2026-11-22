"""Download a portable POSIX MinGW compiler into .cache, no system install."""
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cache = root / ".cache/host-compiler"
cache.mkdir(parents=True, exist_ok=True)
tag = "14.2.0posix-12.0.0-ucrt-r3"
url = f"https://api.github.com/repos/brechtsanders/winlibs_mingw/releases/tags/{tag}"
with urllib.request.urlopen(url, timeout=45) as response:
    release = json.load(response)
asset = next(a for a in release["assets"]
             if a["name"] == "winlibs-x86_64-posix-seh-gcc-14.2.0-mingw-w64ucrt-12.0.0-r3.zip")
archive = cache / asset["name"]
if not archive.exists():
    print(f'Downloading {asset["name"]} ({asset["size"]} bytes)', flush=True)
    with urllib.request.urlopen(asset["browser_download_url"], timeout=120) as response, archive.open("wb") as out:
        while chunk := response.read(1024 * 1024):
            out.write(chunk)
if archive.stat().st_size != asset["size"]:
    raise RuntimeError("Incomplete compiler download")
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
if asset.get("digest"):
    if asset["digest"] != "sha256:" + digest:
        raise RuntimeError("Compiler archive digest mismatch")
with zipfile.ZipFile(archive) as bundle:
    # Standard ZipFile extraction sanitizes absolute paths and '..' entries.
    bundle.extractall(cache)
(root / "docs/validation/host-compiler.json").write_text(
    json.dumps({"source": asset["browser_download_url"], "sha256": digest}, indent=2) + "\n")
print(cache / "mingw64/bin/gcc.exe")
