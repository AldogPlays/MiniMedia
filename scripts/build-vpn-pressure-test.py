#!/usr/bin/env python3
"""Build a temporary, bounded test app; never install or run it automatically."""
import os
import zipfile
import apk_build as b


def main():
    p = b.ROOT / 'build/vpn-pressure'
    p.mkdir(exist_ok=True)
    classes, dex = p / 'classes', p / 'dex'
    classes.mkdir(exist_ok=True)
    dex.mkdir(exist_ok=True)
    source = b.ROOT / 'device-tests/vpn-pressure'
    b.run([*b.native('aapt2'), 'link', '-o', p / 'res.apk', '-I', b.ANDROID,
           '--manifest', source / 'AndroidManifest.xml'])
    b.run([b.jdk() / 'bin/javac', '-source', '8', '-target', '8', '-bootclasspath',
           str(b.ANDROID) + os.pathsep + str(b.BUILD_TOOLS / 'core-lambda-stubs.jar'),
           '-d', classes, source / 'PressureActivity.java'])
    with zipfile.ZipFile(p / 'code.jar', 'w') as z:
        for f in classes.rglob('*.class'):
            z.write(f, f.relative_to(classes))
    b.run([b.jdk() / 'bin/java', '-cp', b.BUILD_TOOLS / 'lib/d8.jar',
           'com.android.tools.r8.D8', '--min-api', '26', '--lib', b.ANDROID,
           '--output', dex, p / 'code.jar'])
    with zipfile.ZipFile(p / 'res.apk', 'a') as z:
        z.write(dex / 'classes.dex', 'classes.dex')
    signed = b.finish_apk(p / 'res.apk', p, min_sdk=26)
    b.publish_apk(signed, p / 'test.apk', backup=False)
    print('Built temporary test APK; not installed or run.')


if __name__ == '__main__':
    main()
