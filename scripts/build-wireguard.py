#!/usr/bin/env python3
"""Bounded compatibility derivative; VPN code preserved, private socket path relocated."""
import copy
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.request import urlopen
import zipfile

import apk_build as build
from apk_binary import patch_manifest

ROOT = build.ROOT
PACKAGE = 'local.minimedia.sdmcw'
BASE = ROOT / 'private/downloads/com.wireguard.android-1.0.20260315.apk'
BASE_SHA = 'f92971bc804f4c448e8845ae97e426095eab06ec09a2473a3fa2cfe7288e3298'
BASE_CERT = '84a13fa2c4e0064b0c11654b8a86574b7a9b9352a3834cee32455b061c3d4127'
TOOL = ROOT / '.tools/downloads/apktool_3.0.3.jar'
TOOL_SHA = 'dbf930b076c6b9be08d57c449cacefc3bdd6b71ebd59b3066fc0e1f5b14f9423'
UPDATER_SHA = 'c89ba53ab037d946c1807f94fd4c9ba596c83e318b785e8ddf47c181dad806b3'
NATIVE_SHA = {
    'lib/arm64-v8a/libwg-go.so': 'fb256b163743984bb2736b3bc81e48b6e76baadb01ef0fdca57024556240cd0d',
    'lib/armeabi-v7a/libwg-go.so': '8a3b76dcde012be64780cdd9f462db616838408b973e4cf855aa6b3c88c23e54',
    'lib/x86/libwg-go.so': '091f9a8a73acc274e608e8f439479e0d5be76222aeba71a7212198fc158142be',
    'lib/x86_64/libwg-go.so': '0dc65b642b14f7c687c4234442a83f0f5bacde3949bbc36857f3b39c234af6ea',
}
UPDATER_METHOD = re.compile(r'^\.method public final monitorForUpdates\(\)V\n.*?^\.end method', re.M | re.S)
NOTICE = '''MiniMedia WireGuard compatibility build, revision 2.
Based on WireGuard Android 1.0.20260315, copyright WireGuard LLC and contributors.
Source and licenses: https://github.com/WireGuard/wireguard-android/tree/1.0.20260315
Changes: independent application ID local.minimedia.sdmcw; scoped provider and
permission identities; upstream update monitor disabled; install-app permission
removed. Native wg-go libraries have only their private control-socket directory
literal relocated to this app's directory. VPN and cryptographic code are unchanged.
This is a locally maintained derivative, not an official WireGuard release.
Build/patch source: scripts/build-wireguard.py in the MiniMedia project.
Non-root userspace backend is the supported mode on BOOMAIR.
'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_native_path(name, original):
    if name not in NATIVE_SHA or sha(original) != NATIVE_SHA[name]:
        raise ValueError('Unsupported native WireGuard library')
    old = b'/data/data/com.wireguard.android/cache/wireguard'
    new = f'/data/data/{PACKAGE}/cache/wireguard'.encode()
    if len(old) != len(new) or original.count(old) != 1:
        raise ValueError('Missing or ambiguous native socket directory')
    offset = original.index(old)
    modified = original[:offset] + new + original[offset + len(old):]
    return modified, {'offset': offset, 'length': len(old), 'before_sha256': sha(original),
                      'after_sha256': sha(modified)}


def patch_updater(text):
    matches = list(UPDATER_METHOD.finditer(text))
    if len(matches) != 1 or sha(matches[0][0].encode()) != UPDATER_SHA:
        raise ValueError('Unsupported or ambiguous upstream updater method')
    replacement = '.method public final monitorForUpdates()V\n    .locals 0\n    return-void\n.end method'
    match = matches[0]
    return text[:match.start()] + replacement + text[match.end():]


def transform_smali(decoded):
    expected = {
        'com/wireguard/android/Application.smali': ('"com.wireguard.android"', f'"{PACKAGE}"'),
        'com/wireguard/android/model/TunnelManager$create$2.smali':
            ('"content://com.wireguard.android.exported-log/"', f'"content://{PACKAGE}.exported-log/"'),
        'com/wireguard/android/updater/Updater.smali': ('"com.wireguard.android-"', f'"{PACKAGE}-"'),
    }
    changes = []
    for relative, (old, new) in expected.items():
        paths = list(decoded.glob('smali*/' + relative))
        if len(paths) != 1:
            raise ValueError(f'Missing or ambiguous class: {relative}')
        path = paths[0]
        original = path.read_text()
        if original.count(old) != 1:
            raise ValueError(f'Unexpected literal in {relative}')
        modified = patch_updater(original) if relative.endswith('/Updater.smali') else original
        modified = modified.replace(old, new)
        path.write_text(modified)
        changes.append({'file': str(path.relative_to(decoded)), 'before': sha(original.encode()),
                        'after': sha(modified.encode())})
    return changes


def normalized_smali(text):
    # Smali omits explicit zero/null static initializers on reassembly. Both
    # representations initialize the field to the same Java default value.
    text = re.sub(r'(?m)^(\.field [^\n]*:[^ \n]+) = (?:false|null)$', r'\1', text)
    return '\n'.join(line for line in text.splitlines() if line.strip())


def main():
    if sha(BASE.read_bytes()) != BASE_SHA:
        raise ValueError('Unsupported original WireGuard APK')
    if not TOOL.exists():
        raw = urlopen('https://github.com/iBotPeaches/Apktool/releases/download/v3.0.3/apktool_3.0.3.jar', timeout=60).read()
        if sha(raw) != TOOL_SHA:
            raise ValueError('Apktool download checksum mismatch')
        TOOL.write_bytes(raw)
    if sha(TOOL.read_bytes()) != TOOL_SHA:
        raise ValueError('Apktool checksum mismatch')
    java = build.jdk() / 'bin/java'
    signer = build.signer()
    certs = subprocess.check_output([str(x) for x in [*signer, 'verify', '--print-certs', BASE]], text=True)
    if f'certificate SHA-256 digest: {BASE_CERT}' not in certs:
        raise ValueError('Unexpected original publisher certificate')
    build.signing_identity()
    destination = ROOT / 'dist/minimedia-wireguard.apk'
    with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory, zipfile.ZipFile(BASE) as original:
        stage = Path(directory)
        decoded = stage / 'decoded'
        tool = [java, '-jar', TOOL]
        build.run([*tool, 'd', '-r', '-j', '4', '-o', decoded, BASE])
        modifications = transform_smali(decoded)
        expected_classes = {str(p.relative_to(decoded)): normalized_smali(p.read_text())
                            for p in decoded.glob('smali*/**/*.smali')}
        rebuilt = stage / 'code.apk'
        build.run([*tool, 'b', '-j', '4', '-o', rebuilt, decoded])
        checked = stage / 'checked'
        build.run([*tool, 'd', '-r', '-j', '4', '-o', checked, rebuilt])
        actual_classes = {str(p.relative_to(checked)): normalized_smali(p.read_text())
                          for p in checked.glob('smali*/**/*.smali')}
        if expected_classes != actual_classes:
            raise ValueError('Reassembled code differs from the declared patches')
        replacements = {old: old.replace('com.wireguard.android', PACKAGE) for old in (
            'com.wireguard.android', 'com.wireguard.android.permission.CONTROL_TUNNELS',
            'com.wireguard.android.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION',
            'com.wireguard.android.exported-log', 'com.wireguard.android.androidx-startup')}
        replacements['1.0.20260315'] = '1.0.20260315-minimedia.2'
        manifest, removed = patch_manifest(original.read('AndroidManifest.xml'), replacements,
                                           {'android.permission.REQUEST_INSTALL_PACKAGES'}, min_sdk=None)
        if removed != ['android.permission.REQUEST_INSTALL_PACKAGES']:
            raise ValueError('Expected installer permission missing')
        unchanged, changed, native_edits = {}, {}, {}
        unsigned = stage / 'unsigned.apk'
        with zipfile.ZipFile(rebuilt) as code, zipfile.ZipFile(unsigned, 'w') as output:
            dex_names = {n for n in original.namelist() if n.endswith('.dex')}
            if dex_names != {n for n in code.namelist() if n.endswith('.dex')}:
                raise ValueError('Unexpected DEX set')
            for info in original.infolist():
                name = info.filename
                if name == 'stamp-cert-sha256' or (name.startswith('META-INF/') and name.upper().endswith(('.SF', '.RSA', '.DSA', '.EC', 'MANIFEST.MF'))):
                    continue
                old = original.read(name)
                data = manifest if name == 'AndroidManifest.xml' else code.read(name) if name in dex_names else old
                if name in NATIVE_SHA:
                    data, native_edits[name] = patch_native_path(name, old)
                output.writestr(copy.copy(info), data)
                (unchanged if old == data else changed)[name] = sha(data)
            output.writestr('assets/minimedia/NOTICE.txt', NOTICE)
        # Native edits are bounded, same-length path literals. All other resources
        # and payloads remain byte-for-byte preserved.
        if any(name != 'AndroidManifest.xml' and name not in dex_names and name not in NATIVE_SHA for name in changed):
            raise ValueError('Unexpected non-code modification')
        signed = build.finish_apk(unsigned, stage, min_sdk=24, page_size=16)
        report = {'package': PACKAGE, 'base_sha256': BASE_SHA, 'base_certificate_sha256': BASE_CERT,
                  'apktool_sha256': TOOL_SHA, 'apk_sha256': sha(signed.read_bytes()),
                  'smali_changes': modifications, 'changed_entries': changed,
                  'native_socket_path_edits': native_edits,
                  'verified_roundtrip_classes': len(actual_classes),
                  'unchanged_entries': unchanged, 'notice': NOTICE,
                  'device_validation': 'pending', 'script_sha256': sha(Path(__file__).read_bytes())}
        build.publish_apk(signed, destination, report)
    print(f'Built and verified {destination}; not installed automatically.')


if __name__ == '__main__':
    main()
