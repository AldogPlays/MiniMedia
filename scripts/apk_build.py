#!/usr/bin/env python3
"""Local Android toolchain and verified APK production shared by MiniMedia builds."""
import glob
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / ".tools/sdk"
BUILD_TOOLS = SDK / "build-tools/35.0.0"
ANDROID = SDK / "platforms/android-30/android.jar"


def jdk():
    if os.environ.get("JAVA_HOME"):
        candidate = Path(os.environ["JAVA_HOME"])
        if (candidate / "bin/javac").is_file():
            return candidate
    compiler = shutil.which("javac")
    if compiler:
        return Path(compiler).resolve().parents[1]
    for pattern in ("/nix/store/*-openjdk-17*/bin/javac", "/nix/store/*-openjdk-21*/bin/javac"):
        matches = sorted(glob.glob(pattern))
        if matches:
            return Path(matches[0]).parents[1]
    raise RuntimeError("A JDK is required (Java 17 or 21).")


def elf_interpreter(executable):
    data = Path(executable).read_bytes()
    if data[:6] != b"\x7fELF\x02\x01":
        raise RuntimeError("Expected a Linux x86-64 ELF executable")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 54)
    for index in range(phcount):
        offset = phoff + index * phsize
        if struct.unpack_from("<I", data, offset)[0] == 3:
            start = struct.unpack_from("<Q", data, offset + 8)[0]
            size = struct.unpack_from("<Q", data, offset + 32)[0]
            return data[start:start + size].rstrip(b"\0").decode()
    raise RuntimeError("No ELF interpreter found")


def native(name):
    binary = BUILD_TOOLS / name
    if Path("/etc/NIXOS").exists():
        # Run Google's Linux tools with NixOS's loader; leave the downloaded files unchanged.
        loader = elf_interpreter("/run/current-system/sw/bin/bash")
        libraries = [str(BUILD_TOOLS / "lib64"), str(Path(loader).parent)]
        for pattern in ("/nix/store/*-gcc-*-lib/lib/libstdc++.so.6", "/nix/store/*-zlib-*/lib/libz.so.1"):
            libraries.extend(str(Path(p).parent) for p in sorted(glob.glob(pattern), reverse=True))
        return [loader, "--library-path", ":".join(dict.fromkeys(libraries)), str(binary)]
    return [str(binary)]


def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def signing_identity(*, create=False):
    """Load the existing identity; only the Home build may bootstrap it."""
    signing = ROOT / "private/signing"
    key, password = signing / "minimedia.p12", signing / "password"
    if not key.is_file():
        if not create or password.exists() or (ROOT / "dist/minimedia-home.apk").exists():
            raise RuntimeError("Signing key is missing; restore it instead of creating a new identity.")
        signing.mkdir(parents=True, exist_ok=True, mode=0o700)
        password.write_text(secrets.token_urlsafe(32))
        password.chmod(0o600)
        env = dict(os.environ, MINIMEDIA_KEY_PASS=password.read_text())
        run([jdk() / "bin/keytool", "-genkeypair", "-keystore", key,
             "-storetype", "PKCS12", "-alias", "minimedia", "-keyalg", "RSA", "-keysize", "3072",
             "-validity", "10000", "-dname", "CN=MiniMedia local build",
             "-storepass:env", "MINIMEDIA_KEY_PASS"], env=env)
        key.chmod(0o600)
    if not password.is_file():
        raise RuntimeError("Signing password is missing; restore private/signing from your backup.")
    return key, dict(os.environ, MINIMEDIA_KEY_PASS=password.read_text())


def signer():
    return [jdk() / "bin/java", "-jar", BUILD_TOOLS / "lib/apksigner.jar"]


def finish_apk(unsigned, stage, *, min_sdk, page_size=None, legacy_pages=False,
               print_certs=False):
    """Return a staged APK only after signing and both verification gates succeed."""
    key, env = signing_identity()
    aligned, signed = stage / "aligned.apk", stage / "signed.apk"
    alignment = ["-P", str(page_size)] if page_size is not None else ["-p"] if legacy_pages else []
    run([*native("zipalign"), *alignment, "-f", "4", unsigned, aligned])
    run([*signer(), "sign", "--ks", key, "--ks-key-alias", "minimedia",
         "--ks-pass", "env:MINIMEDIA_KEY_PASS", "--out", signed, aligned], env=env)
    details = ["--verbose", "--print-certs"] if print_certs else []
    run([*signer(), "verify", *details, "--min-sdk-version", str(min_sdk), signed])
    run([*native("zipalign"), "-c", *alignment, "4", signed])
    return signed


def publish_apk(signed, destination, report=None, *, backup=True):
    """Publish staged output, restoring the previous files on a handled write failure.

    APK/report replacement is not crash-atomic as a pair. Reports must be prepared
    before publication; a failed verification must never call this function.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    report_path = destination.with_suffix(".build.json")
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        stage = Path(temporary)
        pending = stage / "output.apk"
        shutil.copyfile(signed, pending)
        updates = [(pending, destination)]
        if report is not None:
            pending_report = stage / "report.json"
            pending_report.write_text(json.dumps(report, indent=2) + "\n")
            updates.append((pending_report, report_path))
        originals = {}
        for index, (_, target) in enumerate(updates):
            previous = stage / (str(index) + ".previous")
            if target.exists():
                shutil.copyfile(target, previous)
                originals[target] = previous
            else:
                originals[target] = None
        if backup and originals[destination] is not None:
            shutil.copyfile(originals[destination], destination.with_name(destination.stem + ".previous.apk"))
        replaced = []
        try:
            for pending_file, target in updates:
                os.replace(pending_file, target)
                replaced.append(target)
        except OSError:
            for target in reversed(replaced):
                previous = originals[target]
                if previous is None:
                    target.unlink()
                else:
                    os.replace(previous, target)
            raise
