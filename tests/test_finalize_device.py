import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))

spec = importlib.util.spec_from_file_location('finalize_device', Path(__file__).parents[1]/'scripts/finalize-device.py')
module = importlib.util.module_from_spec(spec)
with patch.dict(os.environ, {'MINIMEDIA_SERIAL': 'TEST_BOOMAIR'}):
    spec.loader.exec_module(module)


class DeviceFinalizationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.calls = []
        self.states = {name: 0 for name in module.KEEP}
        self.states.update({'example.first': 1, 'example.second': 3})
        self.home = 'com.google.android.apps.tv.launcherx/.home.HomeActivity'
        self.fail_home = False
        self.fail_disable = False
        self.patches = [
            patch.object(module, 'SERIAL', 'TEST_BOOMAIR'),
            patch.object(module.device, 'SERIAL', 'TEST_BOOMAIR'),
            patch.object(module, 'ROOT', self.root),
            patch.object(module, 'DISABLE', ('example.first','example.second')),
            patch.object(module.device, 'adb', side_effect=self.adb),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def adb(self, *args):
        if args == ('get-state',): return 'device'
        self.assertEqual(args[0], 'shell')
        return self.shell(*args[1:])

    def shell(self, *args):
        self.calls.append(args)
        if args == ('getprop', 'ro.product.model'): return 'BOOMAIR'
        if args == ('am', 'get-current-user'): return '0'
        if args[:2] == ('dumpsys', 'package'):
            return '  User 0: installed=true enabled=' + str(self.states[args[2]]) + '\n'
        if args[:3] == ('cmd', 'package', 'resolve-activity'): return self.home
        if args[:3] == ('pm','list','packages'):
            return '\n'.join('package:'+p for p in self.states)
        if args[:3] == ('cmd','package','set-home-activity') and not self.fail_home:
            self.home = args[-1]
        if args[:2] == ('pm','disable-user'):
            # The on-disk recovery record must name the package before mutation.
            self.assertIn(args[-1], self.record()[1]['attempted'])
            if self.fail_disable:
                raise RuntimeError('device denied change')
            self.states[args[-1]] = 3
        if args[:2] == ('pm','enable'):
            self.states[args[-1]] = 1
        return ''

    def apply(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return module.apply()

    def record(self):
        paths = list((self.root/'private/device-changes').glob('*.json'))
        self.assertEqual(len(paths),1)
        return paths[0],json.loads(paths[0].read_text())

    def test_failed_home_verification_never_disables_packages(self):
        self.fail_home = True
        with self.assertRaises(RuntimeError): self.apply()
        self.assertFalse(any(call[:2] == ('pm','disable-user') for call in self.calls))
        self.assertEqual(self.record()[1]['status'],'prepared')

    def test_restore_keeps_preexisting_disabled_state_and_original_explicit_enable(self):
        self.assertFalse(self.apply())
        path,record = self.record()
        self.assertEqual(record['attempted'],['example.first'])
        self.assertEqual(self.states['example.second'],3)
        with contextlib.redirect_stdout(io.StringIO()): module.restore(path)
        self.assertEqual(self.states['example.first'],1)
        self.assertEqual(self.states['example.second'],3)
        self.assertTrue(self.home.startswith('com.google.android.apps.tv.launcherx/'))

    def test_rejected_disable_is_recorded_without_claiming_success(self):
        self.fail_disable = True
        self.assertTrue(self.apply())
        _,record = self.record()
        self.assertEqual(record['disabled'],[])
        self.assertIn('example.first',record['failures'])
        self.assertEqual(record['status'],'complete-with-failures')

    def test_missing_required_app_prevents_all_mutations(self):
        self.states[module.KEEP[0]] = 3
        with self.assertRaises(RuntimeError): self.apply()
        self.assertFalse(any(call[:3] == ('cmd','package','set-home-activity') for call in self.calls))
        self.assertFalse((self.root/'private').exists())

    def test_priority_workaround_verifies_implicit_home(self):
        record = dict(previous_home=self.home, enabled_states={module.STOCK: 0,module.RECOVERY_PACKAGE: 0},
                      attempted=[], disabled=[], component_states={module.RECOVERY: 0}, attempted_components=[])
        calls = []
        def shell(*args):
            calls.append(args)
            if args[:3] == ('cmd','package','query-activities'): return module.HOME
            if args[:3] == ('am','start','-W'): return 'Status: ok\nActivity: ' + module.HOME
            return 'Success'
        with patch.object(module.device, 'shell',side_effect=shell), \
             patch.object(module.device, 'resolve_home',side_effect=[self.home,module.RECOVERY,module.HOME]), \
             patch.object(module.device, 'package_state',return_value=3), \
             patch.object(module.device, 'component_state',return_value=2), \
             contextlib.redirect_stdout(io.StringIO()):
            module.select_home(record,self.root/'record.json')
        self.assertEqual(record['disabled'],[module.STOCK,module.RECOVERY_PACKAGE])
        self.assertEqual(record['attempted_components'],[])
        self.assertIn(('pm','disable-user','--user','0',module.RECOVERY_PACKAGE),calls)
        self.assertEqual(record['resolved_home_after_workaround'],module.HOME)

    def test_priority_workaround_restores_both_changes_on_failed_home(self):
        record = dict(previous_home=self.home, enabled_states={module.STOCK: 1,module.RECOVERY_PACKAGE: 0},
                      attempted=[], disabled=[], component_states={module.RECOVERY: 0}, attempted_components=[])
        calls = []
        def shell(*args):
            calls.append(args)
            if args[:3] == ('cmd','package','query-activities'): return module.HOME
            if args[:3] == ('am','start','-W'): return 'Status: ok\nActivity: ' + module.HOME
            return 'Success'
        with patch.object(module.device, 'shell',side_effect=shell), \
             patch.object(module.device, 'resolve_home',side_effect=[self.home,module.RECOVERY,'android/.ResolverActivity']), \
             patch.object(module.device, 'package_state',side_effect=[3,3,3,0,3,1]), \
             patch.object(module.device, 'component_state',return_value=2), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'rolled back'):
                module.select_home(record,self.root/'record.json')
        self.assertIn(('pm','default-state','--user','0',module.RECOVERY_PACKAGE),calls)
        self.assertIn(('pm','enable','--user','0',module.STOCK),calls)
        self.assertEqual(record['disabled'],[])

    def test_component_parser_does_not_mix_adjacent_enabled_and_disabled_lists(self):
        dump = ('  User 0: installed=true enabled=0\n'
                '    enabledComponents:\n      unrelated.Activity\n'
                '    disabledComponents:\n      com.google.android.tungsten.setupwraith.RecoveryActivity\n'
                '  User 10: installed=true enabled=0\n')
        # The method itself is patched in these tests only when needed above.
        with patch.object(module.device, 'shell',return_value=dump):
            self.assertEqual(module.device.component_state(module.RECOVERY),2)


if __name__ == '__main__': unittest.main()
