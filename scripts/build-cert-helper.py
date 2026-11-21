#!/usr/bin/env python3
"""Build the temporary, permission-free BOOMAIR CA installation compatibility entry."""
import os
from pathlib import Path
import tempfile
import zipfile
import apk_build as build


def main():
    root = build.ROOT
    jdk = build.jdk()
    with tempfile.TemporaryDirectory(dir=root/'build') as temporary:
        stage = Path(temporary)
        classes = stage/'classes'
        classes.mkdir()
        build.run([*build.native('aapt2'), 'link', '-o', stage/'resources.apk', '-I', build.ANDROID,
                   '--manifest', root/'cert-helper/AndroidManifest.xml'])
        boot = str(build.ANDROID) + os.pathsep + str(build.BUILD_TOOLS/'core-lambda-stubs.jar')
        build.run([jdk/'bin/javac', '-source', '8', '-target', '8', '-bootclasspath', boot,
                   '-d', classes, *sorted((root/'cert-helper/src').rglob('*.java'))])
        build.run([jdk/'bin/java', '-cp', build.BUILD_TOOLS/'lib/d8.jar', 'com.android.tools.r8.D8',
                   '--lib', build.ANDROID, '--min-api', '26', '--output', stage,
                   *sorted(classes.rglob('*.class'))])
        with zipfile.ZipFile(stage/'resources.apk') as source, zipfile.ZipFile(stage/'unsigned.apk','w') as out:
            for entry in source.infolist(): out.writestr(entry, source.read(entry.filename))
            out.write(stage/'classes.dex','classes.dex')
        signed = build.finish_apk(stage/'unsigned.apk', stage, min_sdk=26, legacy_pages=True)
        destination = root/'dist/minimedia-ca-helper.apk'
        build.publish_apk(signed, destination, backup=False)
        print('Built and verified:', destination)


if __name__ == "__main__":
    main()
