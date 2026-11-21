#!/usr/bin/env python3
"""Build and verify the dependency-free native launcher without Gradle or network."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile
from apk_build import (ROOT, ANDROID, BUILD_TOOLS, jdk, native, run,
                       signing_identity, finish_apk, publish_apk)


def main():
    if not ANDROID.is_file() or not (BUILD_TOOLS / "lib/d8.jar").is_file():
        raise SystemExit("Missing build inputs. Run python3 scripts/fetch-tools.py in your terminal first.")
    for name in ("MonaspaceNeon-Regular.otf", "Monaspace-LICENSE.txt"):
        if not (ROOT / "app/assets" / name).is_file():
            raise SystemExit(f"Missing font asset: {name}. Complete the download/font setup first.")
    java_home = jdk()
    java = java_home / "bin/java"
    signing_identity(create=True)
    destination = ROOT / "dist/minimedia-home.apk"
    build_root = ROOT / "build"
    build_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build_root) as temporary:
        stage = Path(temporary)
        classes = stage / "classes"
        classes.mkdir()
        run([*native("aapt2"), "compile", "--dir", ROOT / "app/res", "-o", stage / "resources.zip"])
        run([*native("aapt2"), "link", "-o", stage / "resources.apk", "-I", ANDROID,
             "--manifest", ROOT / "app/AndroidManifest.xml", stage / "resources.zip"])
        sources = sorted((ROOT / "app/src").rglob("*.java"))
        run([java_home / "bin/javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
             "-bootclasspath", str(ANDROID) + os.pathsep + str(BUILD_TOOLS / "core-lambda-stubs.jar"), "-d", classes, *sources])
        with zipfile.ZipFile(stage / "classes.jar", "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted(classes.rglob("*.class")):
                output.write(path, path.relative_to(classes))
        dex = stage / "dex"
        dex.mkdir()
        run([java, "-cp", BUILD_TOOLS / "lib/d8.jar", "com.android.tools.r8.D8", "--release",
             "--min-api", "26", "--lib", ANDROID, "--output", dex, stage / "classes.jar"])
        unsigned = stage / "unsigned.apk"
        shutil.copyfile(stage / "resources.apk", unsigned)
        with zipfile.ZipFile(unsigned, "a", zipfile.ZIP_DEFLATED) as output:
            output.write(dex / "classes.dex", "classes.dex")
            for asset in sorted((ROOT / "app/assets").rglob("*")):
                if asset.is_file():
                    output.write(asset, "assets/" + asset.relative_to(ROOT / "app/assets").as_posix())
            for asset in sorted((ROOT / "private/wallpapers").glob("*.webp")):
                output.write(asset, "assets/wallpapers/" + asset.name)
        signed = finish_apk(unsigned, stage, min_sdk=26, print_certs=True)
        digest = hashlib.sha256(signed.read_bytes()).hexdigest()
        report = {"package": "local.minimedia.home", "version": "0.1.0", "sha256": digest,
                  "sdk_inputs": json.loads((ROOT / ".tools/inputs.json").read_text()),
                  "wallpaper_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in sorted((ROOT / "private/wallpapers").glob("*.webp"))},
                  "source_hashes": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted((ROOT / "app").rglob("*")) if p.is_file()}}
        publish_apk(signed, destination, report)
    print(f"Built and verified: {destination}\nSHA-256: {digest}\nNot installed automatically.")


if __name__ == "__main__":
    main()
