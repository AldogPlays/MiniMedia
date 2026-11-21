import importlib.util
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('build_wireguard', ROOT / 'scripts/build-wireguard.py')
wg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wg)


class WireGuardBuildTests(unittest.TestCase):
    def test_unknown_updater_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            wg.patch_updater('.method public final monitorForUpdates()V\n.locals 0\nreturn-void\n.end method')

    @unittest.skipUnless((ROOT / 'build/wireguard-inspect/smali/com/wireguard/android/updater/Updater.smali').exists(), 'decoded private input not present')
    def test_updater_patch_leaves_other_methods_untouched(self):
        source = (ROOT / 'build/wireguard-inspect/smali/com/wireguard/android/updater/Updater.smali').read_text()
        original = wg.UPDATER_METHOD.search(source)
        modified = wg.patch_updater(source)
        patched = wg.UPDATER_METHOD.search(modified)
        self.assertEqual(source[:original.start()], modified[:patched.start()])
        self.assertEqual(source[original.end():], modified[patched.end():])
        self.assertEqual(patched[0], '.method public final monitorForUpdates()V\n    .locals 0\n    return-void\n.end method')

    @unittest.skipUnless((ROOT / 'dist/minimedia-wireguard.apk').exists(), 'local derivative not built')
    def test_native_resources_and_other_payloads_preserved(self):
        with zipfile.ZipFile(wg.BASE) as original, zipfile.ZipFile(ROOT / 'dist/minimedia-wireguard.apk') as patched:
            for name in original.namelist():
                if name in wg.NATIVE_SHA:
                    old = original.read(name)
                    expected, edit = wg.patch_native_path(name, old)
                    actual = patched.read(name)
                    self.assertEqual(expected, actual)
                    start, size = edit['offset'], edit['length']
                    self.assertEqual(old[:start], actual[:start])
                    self.assertEqual(old[start + size:], actual[start + size:])
                    self.assertEqual(len(old), len(actual))
                elif name.startswith(('lib/', 'res/')) or name == 'resources.arsc':
                    self.assertEqual(original.read(name), patched.read(name), name)
            manifest = patched.read('AndroidManifest.xml')
        from apk_binary import chunks, read_pool
        strings = next(read_pool(c) for kind, c in chunks(manifest) if kind == 1)
        self.assertIn(wg.PACKAGE, strings)
        self.assertIn(wg.PACKAGE + '.permission.CONTROL_TUNNELS', strings)
        self.assertIn(wg.PACKAGE + '.exported-log', strings)
        self.assertIn(wg.PACKAGE + '.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION', strings)
        self.assertNotIn('com.wireguard.android.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION', strings)

    def test_native_patch_rejects_unknown_library(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported native'):
            wg.patch_native_path('lib/armeabi-v7a/libwg-go.so', b'unknown')


if __name__ == '__main__':
    unittest.main()
