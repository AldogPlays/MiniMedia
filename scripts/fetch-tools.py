#!/usr/bin/env python3
"""Download build inputs from their official publishers. Never installs to Android."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
BASE = "https://dl.google.com/android/repository/"
TIZEN_SHA256 = "72a3527f520db3a1b414916ad96481244e451c41e272ae33344ae5e79abb37dd"


def fetch(url, destination, algorithm=None, expected=None, size=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        data = destination.read_bytes()
        if expected and hashlib.new(algorithm, data).hexdigest() == expected and (size is None or len(data) == size):
            return destination
        if not expected:
            raise RuntimeError(f"Refusing to overwrite unverified existing file: {destination}")
    request = urllib.request.Request(url, headers={"User-Agent": "MiniMedia-build/0.1"})
    print(f"Downloading {destination.name}", flush=True)
    temporary = destination.with_name(destination.name + ".partial")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            if urllib.parse.urlparse(response.url).scheme != "https":
                raise RuntimeError("Refusing a download redirected away from HTTPS")
            shutil.copyfileobj(response, output)
        data = temporary.read_bytes()
        if size is not None and len(data) != size:
            raise RuntimeError(f"Size mismatch for {destination.name}")
        if expected and hashlib.new(algorithm, data).hexdigest() != expected:
            raise RuntimeError(f"Checksum mismatch for {destination.name}")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def extract(archive, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            target = (destination / entry.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Archive contains a path outside its destination")
            if stat.S_ISLNK(entry.external_attr >> 16):
                raise RuntimeError("Archive contains an unexpected symlink")
        source.extractall(destination)
        for entry in source.infolist():
            mode = entry.external_attr >> 16
            if mode & 0o111:
                (destination / entry.filename).chmod(0o755)


def sdk_archive(repository, package):
    for remote in repository.iter("remotePackage"):
        if remote.get("path") != package:
            continue
        for archive in remote.findall("archives/archive"):
            if archive.findtext("host-os") not in (None, "linux"):
                continue
            complete = archive.find("complete")
            if complete is None:
                continue
            checksum = complete.find("checksum")
            if checksum is None or not checksum.text:
                raise RuntimeError("SDK metadata has no checksum")
            algorithm = checksum.get("type", "sha1").replace("-", "").lower()
            if algorithm not in ("sha1", "sha256", "sha512"):
                raise RuntimeError(f"Unsupported checksum: {algorithm}")
            return {"url": BASE + complete.findtext("url"), "algorithm": algorithm,
                    "checksum": checksum.text.strip(), "size": int(complete.findtext("size"))}
    raise RuntimeError(f"Official SDK metadata does not contain {package}")


def main():
    if sys.argv[1:] == ["--file-browser"]:
        fetch("https://github.com/zhanghai/MaterialFiles/releases/download/v1.7.5/app-release-universal.apk",
              ROOT / "private/downloads/material-files-1.7.5.apk", "sha256",
              "f2e7f028fbddf51d7ee90ace27a1ae4b247511e12514d1def6c9e52435feac40")
        print("Material Files downloaded and checksum verified; ready for device installation.")
        return
    TOOLS.mkdir(exist_ok=True)
    # Keep each fetched metadata document so the recorded inputs can be audited.
    with tempfile.TemporaryDirectory(dir=TOOLS) as stage:
        metadata = fetch(BASE + "repository2-1.xml", Path(stage) / "repository.xml")
        repository = ET.parse(metadata).getroot()
        for element in repository.iter():
            element.tag = element.tag.rsplit("}", 1)[-1]
        provenance = {}
        for package, relative, sentinel in [
            ("build-tools;35.0.0", "sdk/build-tools/35.0.0", "lib/d8.jar"),
            ("platforms;android-30", "sdk/platforms/android-30", "android.jar"),
        ]:
            spec = sdk_archive(repository, package)
            archive = fetch(spec["url"], TOOLS / "downloads" / spec["url"].rsplit("/", 1)[-1],
                            spec["algorithm"], spec["checksum"], spec["size"])
            destination = TOOLS / relative
            if not (destination / sentinel).exists():
                unpacked = Path(stage) / package.replace(";", "-")
                extract(archive, unpacked)
                roots = list(unpacked.iterdir())
                if len(roots) != 1 or not roots[0].is_dir() or not (roots[0] / sentinel).is_file():
                    raise RuntimeError(f"Unexpected archive structure for {package}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists():
                    raise RuntimeError(f"Incomplete existing tools directory: {destination}")
                shutil.move(str(roots[0]), destination)
            provenance[package] = spec
        shutil.copyfile(metadata, TOOLS / "repository.xml")
        (TOOLS / "inputs.json").write_text(json.dumps(provenance, indent=2) + "\n")

    # Pinned ARMv7 input for inspection/customization, not an automatic installation.
    fetch("https://github.com/reisxd/TizenTubeCobalt/releases/download/v2.0.3/cobalt-arm.apk",
          ROOT / "private/downloads/cobalt-arm-2.0.3.apk", "sha256", TIZEN_SHA256)
    wireguard = ROOT / "private/downloads/com.wireguard.android-1.0.20260315.apk"
    if not wireguard.exists():
        fetch("https://download.wireguard.com/android-client/com.wireguard.android-1.0.20260315.apk", wireguard)
    font_license = ROOT / "app/assets/Monaspace-LICENSE.txt"
    if not font_license.exists():
        fetch("https://raw.githubusercontent.com/githubnext/monaspace/v1.400/LICENSE", font_license)
    print("Ready. Build inputs downloaded; nothing installed on the projector.")


if __name__ == "__main__":
    main()
