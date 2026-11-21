from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import apk_build

ROOT = Path(__file__).parents[1]


class LauncherInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.jdk = apk_build.jdk()
        except RuntimeError as error:
            raise unittest.SkipTest(str(error))
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.classes = Path(cls.directory.name)
        subprocess.run([str(cls.jdk/'bin/javac'), '-encoding', 'UTF-8', '-source', '8', '-target', '8',
                        '-d', str(cls.classes),
                        str(ROOT/'app/src/local/minimedia/home/LauncherInteraction.java'),
                        str(ROOT/'tests/java/local/minimedia/home/LauncherInteractionTest.java')],
                       check=True, capture_output=True)

    def scenario(self, name):
        result = subprocess.run([str(self.jdk/'bin/java'), '-cp', str(self.classes),
                                 'local.minimedia.home.LauncherInteractionTest', name],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_reveal_consumes_key_repeats_and_release(self): self.scenario('reveal-key')
    def test_reveal_consumes_entire_touch_gesture(self): self.scenario('reveal-touch')
    def test_back_closes_menu_before_clearing_search_and_hiding(self): self.scenario('back-order')
    def test_hiding_dismisses_keyboard_before_restoring_menu_focus(self): self.scenario('hide-effect-order')
    def test_pause_resets_gestures_and_idle_until_controls_return(self): self.scenario('pause-resume')
    def test_idle_never_and_visibility_transitions(self): self.scenario('idle')
    def test_unicode_typing_reveals_and_searches_but_respects_modifiers_and_menus(self): self.scenario('search')
    def test_menu_focus_position_and_entry_return(self): self.scenario('focus')
    def test_query_clears_only_when_revealing_hidden_controls(self): self.scenario('fresh-reveal')

    @unittest.skipUnless(apk_build.ANDROID.is_file(), 'local Android SDK not available')
    def test_activity_adapter_compiles_with_the_android_sdk(self):
        sources = sorted((ROOT/'app/src').rglob('*.java'))
        subprocess.run([str(self.jdk/'bin/javac'), '-encoding', 'UTF-8', '-source', '8', '-target', '8',
                        '-bootclasspath', str(apk_build.ANDROID) + ':' + str(apk_build.BUILD_TOOLS/'core-lambda-stubs.jar'),
                        '-d', str(self.classes), *map(str, sources)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
