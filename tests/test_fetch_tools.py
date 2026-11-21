import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

spec = importlib.util.spec_from_file_location("fetch_tools", Path(__file__).parents[1] / "scripts/fetch-tools.py")
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


class FetchToolsTests(unittest.TestCase):
    def test_archive_path_escape_is_rejected_before_extracting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("safe/file", "safe")
                output.writestr("../escaped", "bad")
            with self.assertRaisesRegex(RuntimeError, "outside"):
                tools.extract(archive, root / "out")
            self.assertFalse((root / "escaped").exists())
            self.assertFalse((root / "out/safe/file").exists())

    def test_symlink_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as output:
                entry = zipfile.ZipInfo("link")
                entry.create_system = 3
                entry.external_attr = 0o120777 << 16
                output.writestr(entry, "../../outside")
            with self.assertRaisesRegex(RuntimeError, "symlink"):
                tools.extract(archive, root / "out")

    def test_unsupported_checksum_is_rejected(self):
        repository = ET.fromstring('''<repository><remotePackage path="build-tools;35.0.0">
          <archives><archive><host-os>linux</host-os><complete><size>4</size>
          <checksum type="md5">abcd</checksum><url>tools.zip</url></complete></archive></archives>
          </remotePackage></repository>''')
        with self.assertRaisesRegex(RuntimeError, "Unsupported checksum"):
            tools.sdk_archive(repository, "build-tools;35.0.0")

    def test_download_checksum_failure_preserves_previous_file(self):
        class Response(io.BytesIO):
            url = "https://example.org/input.zip"
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "input.zip"
            destination.write_bytes(b"previous")
            with patch.object(tools.urllib.request, "urlopen", return_value=Response(b"corrupt")):
                with self.assertRaisesRegex(RuntimeError, "Checksum mismatch"):
                    tools.fetch(Response.url, destination, "sha256", "0" * 64)
            self.assertEqual(destination.read_bytes(), b"previous")
            self.assertFalse(destination.with_name("input.zip.partial").exists())

    def test_redirect_to_plain_http_is_rejected(self):
        class Response(io.BytesIO):
            url = "http://example.org/input.zip"
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "input.zip"
            with patch.object(tools.urllib.request, "urlopen", return_value=Response(b"input")):
                with self.assertRaisesRegex(RuntimeError, "HTTPS"):
                    tools.fetch("https://example.org/input.zip", destination)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
