package local.minimedia.home;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;

/** Input, menu and visibility transitions; independent of Android views and clocks. */
final class LauncherInteraction {
    interface Host {
        boolean hasQuery();
        boolean searchFocused();
        void clearSearch(boolean focusResults);
        void typeSearch(int character);
        void dismissSearchKeyboard();
        void showControls(boolean animate, boolean wasHidden);
        void hideControls(boolean animate);
        void armIdle();
        void renderMenu();
        void closeMenu(boolean returnToThemeSelector);
    }

    enum KeyAction { DOWN, UP, OTHER }
    enum TouchAction { DOWN, END, OTHER }

    private final Host host;
    private final ArrayList<String> menuTrail = new ArrayList<>();
    private final LinkedHashMap<String, Integer> menuPositions = new LinkedHashMap<>();
    private boolean controlsShown;
    private boolean resumed;
    private boolean returnToThemeSelector;
    private int revealKey = -1;
    private boolean revealTouch;

    LauncherInteraction(Host host) { this.host = host; }

    boolean controlsShown() { return controlsShown; }
    List<String> menuPath() { return Collections.unmodifiableList(menuTrail); }
    int menuPosition(String page) { return menuPositions.containsKey(page) ? menuPositions.get(page) : 0; }
    void rememberMenuPosition(String page, int position) { menuPositions.put(page, position); }

    void openMenu(String page, boolean fromThemeSelector) {
        returnToThemeSelector = fromThemeSelector;
        menuTrail.clear();
        menuTrail.add(page);
        host.renderMenu();
    }

    void pushMenu(String page) {
        menuTrail.add(page);
        host.renderMenu();
    }

    void closeMenu() {
        menuTrail.clear();
        host.closeMenu(returnToThemeSelector);
    }

    void menuBack() {
        if (menuTrail.size() <= 1) closeMenu();
        else {
            menuTrail.remove(menuTrail.size() - 1);
            host.renderMenu();
        }
    }

    void showControls(boolean animate) {
        boolean wasHidden = !controlsShown;
        if (wasHidden && host.hasQuery()) host.clearSearch(false);
        controlsShown = true;
        host.showControls(animate, wasHidden);
        host.armIdle();
    }

    void hideControls(boolean animate) {
        host.dismissSearchKeyboard();
        closeMenu();
        controlsShown = false;
        host.hideControls(animate);
    }

    /** Consume the whole revealing key gesture, including repeats and release. */
    boolean key(int code, KeyAction action, boolean navigation, int character, boolean modified) {
        if (code == revealKey) {
            if (action == KeyAction.UP) revealKey = -1;
            return true;
        }
        if (action != KeyAction.DOWN) return false;
        if (!controlsShown && navigation) {
            revealKey = code;
            showControls(true);
            return true;
        }
        host.armIdle();
        if (menuTrail.isEmpty() && !host.searchFocused() && !modified
                && character > 0 && !Character.isISOControl(character)) {
            if (!controlsShown) showControls(true);
            host.typeSearch(character);
            return true;
        }
        return false;
    }

    boolean touch(TouchAction action) {
        if (action == TouchAction.DOWN) {
            if (!controlsShown) {
                revealTouch = true;
                showControls(true);
            } else host.armIdle();
        }
        if (!revealTouch) return false;
        if (action == TouchAction.END) revealTouch = false;
        return true;
    }

    void resume() {
        resumed = true;
        host.armIdle();
    }

    void pause() {
        resumed = false;
        revealKey = -1;
        revealTouch = false;
        hideControls(false);
    }

    long idleDelayMillis(int seconds) {
        return resumed && controlsShown && seconds > 0 ? seconds * 1000L : 0;
    }

    void back() {
        if (!menuTrail.isEmpty()) menuBack();
        else if (controlsShown && host.hasQuery()) host.clearSearch(true);
        else if (controlsShown) hideControls(true);
    }
}
