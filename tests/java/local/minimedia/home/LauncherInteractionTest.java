package local.minimedia.home;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public final class LauncherInteractionTest {
    private static final class Host implements LauncherInteraction.Host {
        String query = "";
        boolean focused;
        boolean visible;
        boolean themeReturn;
        boolean resultFocus;
        int idleRefreshes;
        int renders;
        final List<String> effects = new ArrayList<>();
        public boolean hasQuery() { return !query.isEmpty(); }
        public boolean searchFocused() { return focused; }
        public void clearSearch(boolean focusResults) { query = ""; resultFocus = focusResults; effects.add("clear"); }
        public void typeSearch(int code) { focused = true; query += new String(Character.toChars(code)); effects.add("type"); }
        public void dismissSearchKeyboard() { effects.add("dismiss-keyboard"); }
        public void showControls(boolean animate, boolean wasHidden) { visible = true; effects.add("show"); }
        public void hideControls(boolean animate) { visible = false; effects.add(animate ? "hide-animated" : "hide"); }
        public void armIdle() { idleRefreshes++; }
        public void renderMenu() { renders++; }
        public void closeMenu(boolean fromThemeSelector) { themeReturn = fromThemeSelector; effects.add("close-menu"); }
    }
    private static void check(boolean condition) { if (!condition) throw new AssertionError(); }
    private static boolean down(LauncherInteraction interaction, int code) {
        return interaction.key(code, LauncherInteraction.KeyAction.DOWN, true, 0, false);
    }
    public static void main(String[] args) {
        Host host = new Host();
        LauncherInteraction interaction = new LauncherInteraction(host);
        switch (args[0]) {
        case "reveal-key":
            check(down(interaction, 23));
            check(interaction.controlsShown() && host.visible);
            check(down(interaction, 23));
            check(interaction.key(23, LauncherInteraction.KeyAction.UP, true, 0, false));
            check(!down(interaction, 23)); // Next gesture reaches Android activation.
            break;
        case "reveal-touch":
            check(interaction.touch(LauncherInteraction.TouchAction.DOWN));
            check(interaction.touch(LauncherInteraction.TouchAction.OTHER));
            check(interaction.touch(LauncherInteraction.TouchAction.END));
            check(!interaction.touch(LauncherInteraction.TouchAction.DOWN));
            check(!interaction.touch(LauncherInteraction.TouchAction.END));
            break;
        case "back-order":
            interaction.showControls(false);
            host.query = "wire";
            interaction.openMenu("Settings", false);
            interaction.pushMenu("Appearance");
            interaction.back();
            check(interaction.menuPath().equals(Arrays.asList("Settings")) && host.hasQuery());
            interaction.back();
            check(interaction.menuPath().isEmpty() && host.visible && host.hasQuery());
            interaction.back();
            check(!host.hasQuery() && host.resultFocus && host.visible);
            interaction.back();
            check(!host.visible && !interaction.controlsShown());
            break;
        case "hide-effect-order":
            interaction.showControls(false);
            host.effects.clear();
            interaction.hideControls(true);
            check(host.effects.equals(Arrays.asList("dismiss-keyboard", "close-menu", "hide-animated")));
            break;
        case "pause-resume":
            interaction.resume();
            down(interaction, 23);
            check(interaction.idleDelayMillis(30) == 30000);
            interaction.openMenu("Settings", false);
            interaction.pause();
            check(!host.visible && interaction.menuPath().isEmpty());
            check(interaction.idleDelayMillis(30) == 0);
            check(!interaction.key(23, LauncherInteraction.KeyAction.UP, true, 0, false));
            interaction.resume();
            check(!host.visible && interaction.idleDelayMillis(30) == 0);
            check(down(interaction, 23));
            check(interaction.idleDelayMillis(30) == 30000);
            break;
        case "idle":
            interaction.showControls(false);
            check(interaction.idleDelayMillis(30) == 0); // Not resumed yet.
            interaction.resume();
            check(interaction.idleDelayMillis(0) == 0); // Never hide.
            check(interaction.idleDelayMillis(15) == 15000);
            interaction.hideControls(true);
            check(interaction.idleDelayMillis(15) == 0 && !host.visible);
            interaction.showControls(true); // Supersedes an in-flight fade-out.
            check(interaction.controlsShown() && host.visible);
            break;
        case "search":
            check(interaction.key(40, LauncherInteraction.KeyAction.DOWN, false, 0x1f680, false));
            check(host.query.equals("🚀") && host.visible && host.focused);
            check(host.effects.equals(Arrays.asList("show", "type")));
            host.focused = false;
            check(!interaction.key(40, LauncherInteraction.KeyAction.DOWN, false, 'x', true));
            interaction.openMenu("Settings", false);
            check(!interaction.key(40, LauncherInteraction.KeyAction.DOWN, false, 'x', false));
            break;
        case "focus":
            interaction.showControls(false);
            interaction.openMenu("Theme Selector", true);
            interaction.rememberMenuPosition("Theme Selector", 1);
            interaction.pushMenu("Appearance");
            interaction.back();
            check(interaction.menuPosition("Theme Selector") == 1);
            interaction.back();
            check(host.themeReturn);
            interaction.openMenu("Settings", false);
            interaction.closeMenu();
            check(!host.themeReturn && interaction.menuPosition("unknown") == 0);
            break;
        case "fresh-reveal":
            host.query = "old";
            interaction.showControls(false);
            check(host.query.isEmpty() && host.effects.equals(Arrays.asList("clear", "show")));
            host.query = "keep";
            interaction.showControls(false);
            check(host.query.equals("keep"));
            interaction.touch(LauncherInteraction.TouchAction.DOWN);
            interaction.pause();
            check(!interaction.touch(LauncherInteraction.TouchAction.END));
            break;
        default: throw new AssertionError("Unknown scenario: " + args[0]);
        }
    }
}
