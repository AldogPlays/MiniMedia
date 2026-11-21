import importlib.util
import os
from pathlib import Path
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

spec = importlib.util.spec_from_file_location('privacy_device', Path(__file__).resolve().parents[1] / 'scripts/privacy-device.py')
privacy = importlib.util.module_from_spec(spec)
with patch.dict(os.environ, {'MINIMEDIA_SERIAL': 'TEST_BOOMAIR'}):
    spec.loader.exec_module(privacy)


class PrivacyRecoveryTests(unittest.TestCase):
    def test_absent_setting_is_deleted_not_written_as_null(self):
        with patch.object(privacy.base, 'shell', return_value='null') as shell:
            privacy.restore_setting('ble_scan_always_enabled', 'null')
        self.assertEqual(shell.call_args_list[0].args, ('settings', 'delete', 'global', 'ble_scan_always_enabled'))

    def test_prior_setting_is_verified(self):
        with patch.object(privacy.base, 'shell', return_value='0'):
            with self.assertRaisesRegex(RuntimeError, 'Could not restore'):
                privacy.restore_setting('send_action_app_error', '1')

    def test_unknown_setting_never_reaches_device(self):
        with patch.object(privacy.base, 'shell') as shell:
            with self.assertRaisesRegex(RuntimeError, 'Unexpected setting'):
                privacy.restore_setting('adb_enabled', '0')
            shell.assert_not_called()

    def test_rollback_continues_after_permission_failure(self):
        pkg = privacy.PACKAGES[0]
        mic = privacy.MIC_PACKAGES[0]
        record = dict(usb_attempted=False, microphones_attempted=[mic],
                      microphones_before={mic: True}, settings_attempted=['ble_scan_always_enabled'],
                      settings_before={'ble_scan_always_enabled': 'null'},
                      packages_attempted=[pkg], packages_before={pkg: 0})
        def shell(*args):
            if args[:2] == ('pm', 'grant'):
                raise RuntimeError('permission denied')
            return 'null'
        with patch.object(privacy.base, 'shell', side_effect=shell) as call, \
             patch.object(privacy.base, 'package_state', return_value=0):
            failures = privacy.rollback(record)
        self.assertEqual(len(failures), 1)
        self.assertIn('permission denied', failures[0])
        calls = [c.args for c in call.call_args_list]
        self.assertIn(('settings', 'delete', 'global', 'ble_scan_always_enabled'), calls)
        self.assertIn(('pm', 'default-state', '--user', '0', pkg), calls)

    def test_mic_parser_does_not_read_secondary_user_grant(self):
        data = ('  User 0: installed=true enabled=0\n'
                '    runtime permissions:\n'
                '      android.permission.RECORD_AUDIO: granted=false\n'
                '  User 10: installed=true enabled=0\n'
                '    runtime permissions:\n'
                '      android.permission.RECORD_AUDIO: granted=true\n')
        with patch.object(privacy.base, 'shell', return_value=data):
            self.assertFalse(privacy.base.mic_granted(privacy.MIC_PACKAGES[0]))

    def test_adb_restart_checks_final_mode_even_if_response_is_interrupted(self):
        with patch.object(privacy.base, 'adb', side_effect=RuntimeError('device not found')), \
             patch.object(privacy.base, 'reconnect') as reconnect, \
             patch.object(privacy.base, 'shell', return_value='0'):
            privacy.base.restart_adb('usb')
            reconnect.assert_called_once()

    def test_adb_restart_rejects_unchanged_network_mode(self):
        with patch.object(privacy.base, 'adb'), patch.object(privacy.base, 'reconnect'), \
             patch.object(privacy.base, 'shell', return_value='5555'):
            with self.assertRaisesRegex(RuntimeError, 'could not be verified'):
                privacy.base.restart_adb('usb')
