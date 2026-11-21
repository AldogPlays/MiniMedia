import importlib.util
from pathlib import Path
import struct
import sys
import unittest
import zipfile

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from apk_binary import chunks, read_pool, write_pool, patch_manifest


class ManifestTests(unittest.TestCase):
    def pool(self):
        header = struct.pack('<HH6I', 1, 28, 32, 1, 0, 256, 32, 0)
        return header + b'\0\0\0\0' + b'\x01\x01x\0'

    def test_string_pool_preserves_unicode_and_long_lengths(self):
        values = ['写真 🌓 ' + 'a' * 180]
        updated = write_pool(self.pool(), values)
        self.assertEqual(read_pool(updated), values)
        self.assertEqual(len(updated), struct.unpack_from('<I', updated, 4)[0])

    def test_missing_exact_manifest_match_is_rejected(self):
        pool = write_pool(self.pool(), ['known'])
        document = struct.pack('<HHI', 3, 8, 8 + len(pool)) + pool
        with self.assertRaisesRegex(ValueError, 'Missing or ambiguous'):
            patch_manifest(document, {'unknown': 'new'}, set())

    @unittest.skipUnless((ROOT / 'private/downloads/cobalt-arm-2.0.3.apk').exists(), 'private upstream APK not present')
    def test_original_manifest_pool_round_trip(self):
        with zipfile.ZipFile(ROOT / 'private/downloads/cobalt-arm-2.0.3.apk') as source:
            manifest = source.read('AndroidManifest.xml')
        for kind, pool in chunks(manifest):
            if kind == 1:
                strings = read_pool(pool)
                self.assertEqual(read_pool(write_pool(pool, strings)), strings)

    @unittest.skipUnless((ROOT / 'private/downloads/cobalt-arm-2.0.3.apk').exists(), 'private upstream APK not present')
    def test_native_patch_changes_only_the_declared_literal_ranges(self):
        spec = importlib.util.spec_from_file_location('build_youtube', ROOT / 'scripts/build-youtube.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with zipfile.ZipFile(ROOT / 'private/downloads/cobalt-arm-2.0.3.apk') as source:
            original = source.read(module.NATIVE_PATH)
        modified, edits = module.patch_native(original)
        self.assertEqual(len(original), len(modified))
        position = 0
        for edit in sorted(edits, key=lambda e: e['offset']):
            self.assertEqual(original[position:edit['offset']], modified[position:edit['offset']])
            position = edit['offset'] + edit['length']
        self.assertEqual(original[position:], modified[position:])
        with self.assertRaisesRegex(RuntimeError, 'Unsupported native'):
            module.patch_native(b'unknown library')


if __name__ == '__main__':
    unittest.main()
