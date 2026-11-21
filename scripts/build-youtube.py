#!/usr/bin/env python3
"""Build a locally signed Cobalt derivative with a bundled MiniMedia page policy."""
import hashlib
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
import apk_build as build
from apk_binary import patch_manifest

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "private/downloads/cobalt-arm-2.0.3.apk"
EXPECTED_APK = "72a3527f520db3a1b414916ad96481244e451c41e272ae33344ae5e79abb37dd"
EXPECTED_NATIVE = "49fb79adf6cb02c5ab66a13173cc25ff536346705d8460c9bd30c543ea15fa95"
NATIVE_PATH = "lib/armeabi-v7a/libchrobalt.so"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_bridge(stage, source):
    classes = {}
    for name in source.namelist():
        if not name.endswith(".dex"):
            continue
        path = stage / name
        path.write_bytes(source.read(name))
        xml = path.with_suffix(".xml")
        build.run([*build.native("dexdump"), "-l", "xml", "-o", xml, path])
        for package in ET.parse(xml).getroot().findall("package"):
            for cls in package.findall("class"):
                classes[package.get("name") + "." + cls.get("name")] = cls
    targets = {
        "dev.cobalt.app.MainActivity": [("onCreate", "void", ["android.os.Bundle"])],
        "dev.cobalt.coat.CobaltActivity": [("getActiveShell", "dev.cobalt.shell.Shell", [])],
        "dev.cobalt.shell.Shell": [("getWebContents", "org.chromium.content_public.browser.WebContents", [])],
        "org.chromium.content_public.browser.WebContents": [("evaluateJavaScript", "void", ["java.lang.String", "org.chromium.content_public.browser.JavaScriptCallback"])],
        "org.chromium.content_public.browser.JavaScriptCallback": [("handleJavaScriptResult", "void", ["java.lang.String"])],
    }
    for name, methods in targets.items():
        cls = classes.get(name)
        if cls is None:
            raise RuntimeError(f"Missing original bridge class: {name}")
        if name.endswith("MainActivity") and (cls.get("final") != "false" or cls.get("abstract") != "false"):
            raise RuntimeError("Original launcher is not safely subclassable")
        for method_name, return_type, parameters in methods:
            matches = [m for m in cls.findall("method") if m.get("name") == method_name
                       and m.get("return") == return_type
                       and [p.get("type") for p in m.findall("parameter")] == parameters]
            if len(matches) != 1 or matches[0].get("visibility") != "public":
                raise RuntimeError(f"Unsupported bridge method: {name}.{method_name}")
    return targets


def patch_native(original):
    if digest(original) != EXPECTED_NATIVE:
        raise RuntimeError("Unsupported native library")
    url = b"https://cdn.jsdelivr.net/npm/@foxreis/tizentube/dist/userScript.js?v="
    marker = b"fetch('https://cdn.jsdelivr.net/npm/@foxreis/tizentube/dist/userScript.js', { method: 'HEAD' })"
    if original.count(url) != 1 or original.count(marker) != 1:
        raise RuntimeError("Missing or ambiguous remote-script bootstrap")
    index = original.index(marker)
    start = original.rfind(b"\0", 0, index) + 1
    end = original.index(b"\0", index)
    old_check = original[start:end]
    if len(old_check) != 686 or b"h5vcc.tizentube.ShowAlertDialog" not in old_check:
        raise RuntimeError("Unsupported remote-script availability check")
    new_url = b"data:text/javascript,void%200;//"
    new_check = b"/* Remote executable scripts are disabled; this build injects a local policy. */"
    modified = original.replace(url, new_url.ljust(len(url), b" "), 1)
    modified = modified[:start] + new_check.ljust(end - start, b" ") + modified[end:]
    assert len(modified) == len(original)
    return modified, [{"offset": original.index(url), "length": len(url), "purpose": "disable remote script URL"},
                      {"offset": start, "length": end - start, "purpose": "disable remote script HEAD check"}]


def main():
    raw = ORIGINAL.read_bytes()
    if digest(raw) != EXPECTED_APK:
        raise SystemExit("Unsupported original APK: checksum mismatch")
    build.signing_identity()
    java_home = build.jdk()
    build.run([*build.signer(), "verify", "--min-sdk-version", "26", ORIGINAL])
    destination = ROOT / "dist/minimedia-youtube.apk"
    with zipfile.ZipFile(ORIGINAL) as source, tempfile.TemporaryDirectory(dir=ROOT / "build") as directory:
        stage = Path(directory)
        bridge = validate_bridge(stage, source)
        replacements = {
            "io.gh.reisxd.tizentube.cobalt": "local.minimedia.youtube",
            "io.gh.reisxd.tizentube.cobalt.fileprovider": "local.minimedia.youtube.fileprovider",
            "dev.cobalt.app.MainActivity": "local.minimedia.youtube.CustomActivity",
            "TizenTube": "YouTube",
        }
        removed_permissions = {
            "android.permission.ACCESS_COARSE_LOCATION", "android.permission.CAMERA",
            "android.permission.WRITE_EXTERNAL_STORAGE", "android.permission.GET_ACCOUNTS",
            "android.permission.REQUEST_INSTALL_PACKAGES", "android.permission.QUERY_ALL_PACKAGES",
            "android.permission.GET_TASKS", "com.google.android.gms.permission.AD_ID",
        }
        manifest, removed = patch_manifest(source.read("AndroidManifest.xml"), replacements, removed_permissions)
        native, edits = patch_native(source.read(NATIVE_PATH))
        classes = stage / "classes"
        classes.mkdir()
        stubs = sorted((ROOT / "youtube/stubs").rglob("*.java"))
        custom = sorted((ROOT / "youtube/src").rglob("*.java"))
        build.run([java_home / "bin/javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
                   "-bootclasspath", str(build.ANDROID) + os.pathsep + str(build.BUILD_TOOLS / "core-lambda-stubs.jar"),
                   "-d", classes, *stubs, *custom])
        jar = stage / "custom.jar"
        with zipfile.ZipFile(jar, "w", zipfile.ZIP_DEFLATED) as output:
            for path in sorted((classes / "local/minimedia/youtube").rglob("*.class")):
                output.write(path, path.relative_to(classes))
        dex = stage / "dex"
        dex.mkdir()
        build.run([java_home / "bin/java", "-cp", build.BUILD_TOOLS / "lib/d8.jar", "com.android.tools.r8.D8",
                   "--release", "--min-api", "26", "--lib", build.ANDROID, "--classpath", classes,
                   "--output", dex, jar])
        if "classes4.dex" in source.namelist():
            raise RuntimeError("Original APK already has classes4.dex")
        unsigned = stage / "unsigned.apk"
        modified_entries = {"AndroidManifest.xml": manifest, NATIVE_PATH: native}
        unchanged = {}
        with zipfile.ZipFile(unsigned, "w") as output:
            for info in source.infolist():
                name = info.filename
                if name == "stamp-cert-sha256" or (name.startswith("META-INF/") and name.upper().endswith((".SF", ".RSA", ".DSA", ".EC", "MANIFEST.MF"))):
                    continue
                original_data = source.read(name)
                data = modified_entries.get(name, original_data)
                output.writestr(copy.copy(info), data)
                if name.endswith(".dex"):
                    unchanged[name] = digest(data)
                    if data != original_data:
                        raise RuntimeError("An original DEX file was changed")
            output.write(dex / "classes.dex", "classes4.dex", compress_type=zipfile.ZIP_DEFLATED)
            output.write(ROOT / "youtube/assets/policy.js", "assets/minimedia/policy.js", compress_type=zipfile.ZIP_DEFLATED)
        signed = build.finish_apk(unsigned, stage, min_sdk=26, page_size=16)
        report = {"package": "local.minimedia.youtube", "base": "TizenTube Cobalt 2.0.3 ARMv7",
                  "original_sha256": EXPECTED_APK, "apk_sha256": digest(signed.read_bytes()),
                  "native_original_sha256": EXPECTED_NATIVE, "native_patched_sha256": digest(native),
                  "native_string_edits": edits, "removed_permissions": removed,
                  "original_dex_unchanged": unchanged, "bridge": bridge,
                  "source_hashes": {str(p.relative_to(ROOT)): digest(p.read_bytes())
                                    for p in sorted((ROOT / "youtube").rglob("*")) if p.is_file()},
                  "device_validation": "pending"}
        build.publish_apk(signed, destination, report)
    print(f"Built custom prototype: {destination}; device testing remains required.")


if __name__ == "__main__":
    main()
