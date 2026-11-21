import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import apk_build


class ApkProductionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        signing = self.root / 'private/signing'
        signing.mkdir(parents=True)
        (signing / 'minimedia.p12').write_bytes(b'test identity')
        (signing / 'password').write_text('test-only-password')
        self.stage = self.root / 'stage'
        self.stage.mkdir()
        self.unsigned = self.stage / 'unsigned.apk'
        self.unsigned.write_bytes(b'unsigned')
        self.destination = self.root / 'dist/example.apk'
        self.destination.parent.mkdir()
        self.destination.write_bytes(b'previous')
        self.calls = []
        self.fail = None
        for item in [patch.object(apk_build, 'ROOT', self.root),
                     patch.object(apk_build, 'jdk', return_value=Path('/test/jdk')),
                     patch.object(apk_build, 'native', side_effect=lambda name: [name]),
                     patch.object(apk_build, 'run', side_effect=self.command)]:
            item.start()
            self.addCleanup(item.stop)

    def command(self, args, **kwargs):
        args = [str(x) for x in args]
        self.calls.append(args)
        phase = 'align' if args[0] == 'zipalign' and '-f' in args else (
            'alignment-check' if args[0] == 'zipalign' else 'sign' if 'sign' in args else 'verify')
        if phase == self.fail:
            raise subprocess.CalledProcessError(1, args)
        if phase == 'align':
            Path(args[-1]).write_bytes(Path(args[-2]).read_bytes())
        elif phase == 'sign':
            Path(args[args.index('--out') + 1]).write_bytes(b'verified output')

    def test_production_preserves_sdk_and_native_alignment_policy(self):
        signed = apk_build.finish_apk(self.unsigned, self.stage, min_sdk=24, page_size=16)
        apk_build.publish_apk(signed, self.destination, {'sha256': 'example'})
        self.assertEqual(self.destination.read_bytes(), b'verified output')
        self.assertEqual(self.destination.with_name('example.previous.apk').read_bytes(), b'previous')
        self.assertEqual(json.loads(self.destination.with_suffix('.build.json').read_text()), {'sha256': 'example'})
        self.assertIn(['zipalign', '-P', '16', '-f', '4', str(self.unsigned), str(self.stage/'aligned.apk')], self.calls)
        self.assertEqual(self.calls[-1], ['zipalign', '-c', '-P', '16', '4', str(signed)])
        verification = self.calls[-2]
        self.assertEqual(verification[verification.index('--min-sdk-version') + 1], '24')

    def test_each_failed_verification_gate_preserves_previous_output(self):
        for phase in ['align', 'sign', 'verify', 'alignment-check']:
            with self.subTest(phase=phase):
                self.fail = phase
                with self.assertRaises(subprocess.CalledProcessError):
                    signed = apk_build.finish_apk(self.unsigned, self.stage, min_sdk=26)
                    apk_build.publish_apk(signed, self.destination)
                self.assertEqual(self.destination.read_bytes(), b'previous')
                self.assertFalse(self.destination.with_suffix('.build.json').exists())

    def test_report_replacement_failure_restores_the_old_apk_and_report(self):
        report_path = self.destination.with_suffix('.build.json')
        report_path.write_text('{"previous": true}')
        replace = os.replace
        def fail_report(source, target):
            if Path(source).name == 'report.json':
                raise OSError('simulated report failure')
            replace(source, target)
        with patch.object(apk_build.os, 'replace', side_effect=fail_report):
            with self.assertRaisesRegex(OSError, 'report failure'):
                apk_build.publish_apk(self.unsigned, self.destination, {'new': True})
        self.assertEqual(self.destination.read_bytes(), b'previous')
        self.assertEqual(json.loads(report_path.read_text()), {'previous': True})

    def test_unserializable_report_never_replaces_output(self):
        with self.assertRaises(TypeError):
            apk_build.publish_apk(self.unsigned, self.destination, {'invalid': object()})
        self.assertEqual(self.destination.read_bytes(), b'previous')

    def test_missing_identity_never_bootstraps_implicitly(self):
        (self.root/'private/signing/minimedia.p12').unlink()
        with self.assertRaisesRegex(RuntimeError, 'restore'):
            apk_build.finish_apk(self.unsigned, self.stage, min_sdk=26)
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(RuntimeError, 'restore'):
            apk_build.signing_identity(create=True)

    def test_helper_alignment_is_checked_after_signing(self):
        signed = apk_build.finish_apk(self.unsigned, self.stage, min_sdk=26, legacy_pages=True)
        self.assertEqual(self.calls[-1], ['zipalign', '-c', '-p', '4', str(signed)])


if __name__ == '__main__':
    unittest.main()
