import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
with patch.dict(os.environ, {'MINIMEDIA_SERIAL': 'TEST_BOOMAIR'}):
    import boomair_device as device

spec = importlib.util.spec_from_file_location('privacy_workflow', Path(__file__).parents[1]/'scripts/privacy-device.py')
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


class DeviceModuleTests(unittest.TestCase):
    def test_workflow_test_collection_ignores_malformed_owner_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = Path(__file__).parents[1]
            shutil.copytree(source/'scripts', root/'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            (root/'tests').mkdir()
            (root/'private').mkdir()
            (root/'private/device.json').write_text('invalid local JSON')
            for name in ['test_boomair_device.py', 'test_finalize_device.py', 'test_privacy_device.py']:
                with self.subTest(module=name):
                    shutil.copyfile(source/'tests'/name, root/'tests'/name)
                    env = {key: value for key, value in os.environ.items() if key != 'MINIMEDIA_SERIAL'}
                    result = subprocess.run([sys.executable, '-c',
                                             'import runpy; runpy.run_path(' + repr('tests/'+name) + ', run_name="collected_test")'],
                                            cwd=root, env=env, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_fresh_checkout_has_no_implicit_device_and_empty_override_stays_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(device, 'ROOT', root), patch.dict(device.os.environ, {}, clear=True):
                self.assertEqual(device.configured_serial(), '')
            (root/'private').mkdir()
            (root/'private/device.json').write_text('{"serial": "LOCAL_TEST_DEVICE"}')
            with patch.object(device, 'ROOT', root), patch.dict(device.os.environ, {'MINIMEDIA_SERIAL': ''}, clear=True):
                self.assertEqual(device.configured_serial(), '')

    def test_environment_serial_overrides_ignored_owner_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'private').mkdir()
            (root/'private/device.json').write_text('{"serial": "LOCAL_TEST_DEVICE"}')
            with patch.object(device, 'ROOT', root), patch.dict(device.os.environ, {'MINIMEDIA_SERIAL': 'ENV_TEST_DEVICE'}, clear=True):
                self.assertEqual(device.configured_serial(), 'ENV_TEST_DEVICE')

    def test_malformed_serial_is_rejected_before_transport(self):
        with patch.object(device, 'SERIAL', 'invalid serial'), patch.object(device.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Invalid device serial'):
                device.adb('get-state')
            run.assert_not_called()

    def test_private_device_configuration_keeps_owner_transport_serial_scoped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'private').mkdir()
            (root/'private/device.json').write_text('{"serial": "TEST_BOOMAIR"}')
            with patch.object(device, 'ROOT', root), patch.dict(device.os.environ, {}, clear=True):
                serial = device.configured_serial()
            with patch.object(device, 'SERIAL', serial), patch.object(device.subprocess, 'run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = 'device\n'
                self.assertEqual(device.adb('get-state'), 'device')
                self.assertEqual(run.call_args.args[0], ['adb', '-s', 'TEST_BOOMAIR', 'get-state'])

    def test_unconfigured_serial_rejects_device_commands_before_transport(self):
        with patch.object(device, 'SERIAL', ''), patch.object(device.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'MINIMEDIA_SERIAL'):
                device.adb('get-state')
            run.assert_not_called()

    def test_identity_checks_use_serial_scoped_transport_and_reject_other_users(self):
        responses = ['device', 'BOOMAIR', '10']
        with patch.object(device, 'adb', side_effect=responses) as adb:
            with self.assertRaisesRegex(RuntimeError, 'user 0'):
                device.verify_device()
        self.assertEqual(adb.call_args_list[0].args, ('get-state',))
        with patch.object(device, 'SERIAL', 'TEST_BOOMAIR'), patch.object(device.subprocess, 'run') as run:
            run.return_value.returncode = 0
            run.return_value.stdout = ' device\n'
            self.assertEqual(device.adb('get-state'), 'device')
            self.assertEqual(run.call_args.args[0], ['adb', '-s', device.SERIAL, 'get-state'])

    def test_disable_persists_intent_before_mutation_and_restores_exact_prior_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'records/test.json'
            record = {'attempted': []}
            state = [1]
            def adb(*args):
                if args[:3] == ('shell', 'pm', 'disable-user'):
                    self.assertEqual(json.loads(path.read_text())['attempted'], ['example.app'])
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                    state[0] = 3
                elif args[:3] == ('shell', 'pm', 'enable'):
                    state[0] = 1
                elif args[:3] == ('shell', 'dumpsys', 'package'):
                    return '  User 0: installed=true enabled=' + str(state[0]) + '\n  User 10: enabled=2\n'
                else:
                    raise AssertionError(args)
                return ''
            with patch.object(device, 'adb', side_effect=adb):
                device.disable_package('example.app', record, path)
                self.assertEqual(device.package_state('example.app'), 3)
                device.restore_package('example.app', 1)
                self.assertEqual(device.package_state('example.app'), 1)

    def test_failed_journal_write_never_reaches_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'record.json'
            device.write_record(path, {'attempted': []})
            with patch.object(device.os, 'replace', side_effect=OSError('disk unavailable')), \
                 patch.object(device, 'adb') as adb:
                with self.assertRaises(OSError):
                    device.disable_package('example.app', {'attempted': []}, path)
                adb.assert_not_called()
            self.assertEqual(json.loads(path.read_text()), {'attempted': []})
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_rejected_disable_remains_recorded_for_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'record.json'
            with patch.object(device, 'adb', return_value='  User 0: installed=true enabled=1'):
                with self.assertRaisesRegex(RuntimeError, 'disabled-user'):
                    device.disable_package('example.app', {'packages_attempted': []}, path,
                                           attempts='packages_attempted')
            self.assertEqual(json.loads(path.read_text())['packages_attempted'], ['example.app'])

    def test_missing_user_zero_never_reads_other_users_package_or_permission(self):
        with patch.object(device, 'adb', return_value='  User 10: installed=true enabled=1\n'
                          '    android.permission.RECORD_AUDIO: granted=true\n'):
            with self.assertRaisesRegex(RuntimeError, 'user-0'):
                device.package_state('example.app')
            with self.assertRaisesRegex(RuntimeError, 'microphone'):
                device.mic_granted('example.app')

    def test_interrupted_restart_reconnects_and_checks_mode_using_real_device_checks(self):
        clock = [0.0]
        def adb(*args):
            if args == ('usb',): raise RuntimeError('interrupted restart response')
            if args == ('get-state',):
                if clock[0] < 1: raise RuntimeError('not ready')
                return 'device'
            if args == ('shell', 'getprop', 'ro.product.model'): return 'BOOMAIR'
            if args == ('shell', 'am', 'get-current-user'): return '0'
            if args == ('shell', 'getprop', 'service.adb.tcp.port'): return '-1'
            raise AssertionError(args)
        with patch.object(device, 'adb', side_effect=adb), \
             patch.object(device.time, 'monotonic', side_effect=lambda: clock[0]), \
             patch.object(device.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0]+seconds)):
            device.restart_adb('usb')
        self.assertGreaterEqual(clock[0], 2.5)


class PrivacyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.packages = {p: 0 for p in device.KEEP + privacy.PACKAGES}
        self.settings = {k: 'null' for k in privacy.SETTINGS}
        self.grants = {p: True for p in privacy.MIC_PACKAGES}
        self.fail_setting = False
        for item in [patch.object(device, 'ROOT', self.root),
                     patch.object(device, 'SERIAL', 'TEST_BOOMAIR'),
                     patch.object(device, 'adb', side_effect=self.adb)]:
            item.start()
            self.addCleanup(item.stop)

    def latest_record(self):
        paths = list((self.root/'private/device-changes').glob('*.json'))
        self.assertEqual(len(paths), 1)
        return json.loads(paths[0].read_text())

    def adb(self, *args):
        if args == ('get-state',): return 'device'
        self.assertEqual(args[0], 'shell')
        args = args[1:]
        if args == ('getprop', 'ro.product.model'): return 'BOOMAIR'
        if args == ('am', 'get-current-user'): return '0'
        if args == ('getprop', 'service.adb.tcp.port'): return '-1'
        if args[:3] == ('cmd', 'package', 'resolve-activity'): return device.HOME
        if args[:2] == ('dumpsys', 'package'):
            return ('  User 0: installed=true enabled=' + str(self.packages.get(args[2], 0)) + '\n'
                    '    android.permission.RECORD_AUDIO: granted=' + str(self.grants.get(args[2], False)).lower() + '\n')
        if args[:2] == ('settings', 'get'): return self.settings[args[-1]]
        if args[:2] == ('settings', 'put'):
            self.assertIn(args[-2], self.latest_record()['settings_attempted'])
            if self.fail_setting: raise RuntimeError('setting denied')
            self.settings[args[-2]] = args[-1]
        elif args[:2] == ('settings', 'delete'):
            self.settings[args[-1]] = 'null'
        elif args[:2] == ('pm', 'disable-user'):
            self.assertIn(args[-1], self.latest_record()['packages_attempted'])
            self.packages[args[-1]] = 3
        elif args[:2] == ('pm', 'default-state'):
            self.packages[args[-1]] = 0
        elif args[:2] in [('pm', 'revoke'), ('pm', 'grant')]:
            self.assertIn(args[-2], self.latest_record()['microphones_attempted'])
            self.grants[args[-2]] = args[1] == 'grant'
        else:
            raise AssertionError(args)
        return ''

    def assert_original_states(self):
        self.assertTrue(all(state == 0 for state in self.packages.values()))
        self.assertTrue(all(state == 'null' for state in self.settings.values()))
        self.assertTrue(all(self.grants.values()))

    def test_full_apply_and_recovery_use_real_parsers_and_legacy_record(self):
        with contextlib.redirect_stdout(io.StringIO()):
            privacy.apply(True)
        record = self.latest_record()
        self.assertEqual(record['kind'], 'minimedia-privacy-v1')
        self.assertEqual(record['status'], 'complete')
        self.assertTrue(all(self.packages[p] == 3 for p in privacy.PACKAGES))
        self.assertEqual(self.settings, privacy.SETTINGS)
        self.assertFalse(any(self.grants.values()))
        self.assertEqual(privacy.rollback(record), [])
        self.assert_original_states()

    def test_failure_rolls_back_attempts_without_replacing_recovery_schema(self):
        self.fail_setting = True
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'rolled-back'):
                privacy.apply(True)
        self.assertEqual(self.latest_record()['status'], 'rolled-back')
        self.assert_original_states()


if __name__ == '__main__':
    unittest.main()
