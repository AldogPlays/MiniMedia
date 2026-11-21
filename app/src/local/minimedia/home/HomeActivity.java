package local.minimedia.home;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.graphics.Canvas;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.RectF;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.widget.LinearLayout;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.ScrollView;
import android.widget.ImageView;
import android.widget.EditText;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.inputmethod.InputMethodManager;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.Arrays;

/** Native, remote-first home screen. No web view, recommendations or background service. */
public final class HomeActivity extends Activity {
    private int BG, SURFACE, FG, MUTED, ACCENT, BORDER;
    private boolean latte;
    private String[] wallpapers = new String[0];
    private Typeface font;
    private TextView clock;
    private VpnIndicator network;
    private ConnectivityManager.NetworkCallback networkCallback;
    private Network observedNetwork;
    private View firstTile;
    private FrameLayout homeFrame;
    private FrameLayout homeContent;
    private LinearLayout appPanel, appResults;
    private ScrollView appScroll;
    private EditText search;
    private List<ResolveInfo> searchableApps;
    private WallpaperView wallpaperView;
    private FrameLayout menuOverlay;
    private String menuPage;
    private final Random random = new Random();
    private final ExecutorService imageLoader = Executors.newSingleThreadExecutor();
    private volatile int menuGeneration;
    private volatile int wallpaperGeneration;
    private final LauncherInteraction interaction = new LauncherInteraction(new LauncherInteraction.Host() {
        @Override public boolean hasQuery() { return search != null && search.length() > 0; }
        @Override public boolean searchFocused() { return search != null && search.hasFocus(); }
        @Override public void clearSearch(boolean focusResults) {
            if (focusResults) dismissSearchKeyboard();
            search.setText("");
            if (focusResults) firstTile.requestFocus();
        }
        @Override public void typeSearch(int character) {
            search.requestFocus();
            search.append(new String(Character.toChars(character)));
        }
        @Override public void dismissSearchKeyboard() { HomeActivity.this.dismissSearchKeyboard(); }
        @Override public void showControls(boolean animate, boolean wasHidden) {
            renderShownControls(animate, wasHidden);
        }
        @Override public void hideControls(boolean animate) { renderHiddenControls(animate); }
        @Override public void armIdle() { HomeActivity.this.armIdle(); }
        @Override public void renderMenu() { HomeActivity.this.renderMenu(); }
        @Override public void closeMenu(boolean fromThemeSelector) { removeMenu(fromThemeSelector); }
    });
    private final Runnable idle = () -> interaction.hideControls(true);
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            refreshStatus();
            rotateWallpaperIfDue();
            handler.postDelayed(this, 60000 - System.currentTimeMillis() % 60000);
        }
    };

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN,
                WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
        try { font = Typeface.createFromAsset(getAssets(), "MonaspaceNeon-Regular.otf"); }
        catch (RuntimeException e) { font = Typeface.MONOSPACE; }
        try {
            wallpapers = getAssets().list("wallpapers");
            if (wallpapers == null) wallpapers = new String[0];
            Arrays.sort(wallpapers);
        } catch (IOException e) { wallpapers = new String[0]; }
        rotateWallpaperIfDue();
        makeHome();
        openPreviewMenu();
        captureIfRequested();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        openPreviewMenu();
        captureIfRequested();
    }

    private void openPreviewMenu() {
        String page = getIntent().getStringExtra("preview_menu");
        getIntent().removeExtra("preview_menu");
        if ("Home".equals(page)) interaction.showControls(false);
        if ("Theme Selector".equals(page)) {
            interaction.showControls(false);
            showThemeSelector();
        }
        if ("Settings".equals(page) || "Appearance".equals(page) || "Wallpapers".equals(page)) {
            interaction.showControls(false);
            interaction.openMenu("Settings", false);
            if (!"Settings".equals(page)) interaction.pushMenu("Appearance");
            if ("Wallpapers".equals(page)) interaction.pushMenu(page);
        }
    }

    private void captureIfRequested() {
        // Explicit, local QA only: capture this app's view, never other apps or playback.
        if (!getIntent().getBooleanExtra("capture_preview", false)) return;
        getIntent().removeExtra("capture_preview");
        int delay = Math.max(300, Math.min(60000, getIntent().getIntExtra("capture_delay_ms", 300)));
        getIntent().removeExtra("capture_delay_ms");
        getWindow().getDecorView().postDelayed(() -> {
            View view = getWindow().getDecorView();
            if (view.getWidth() == 0 || view.getHeight() == 0) return;
            Bitmap bitmap = Bitmap.createBitmap(view.getWidth(), view.getHeight(), Bitmap.Config.ARGB_8888);
            try {
                view.draw(new Canvas(bitmap));
                File directory = getExternalFilesDir(null);
                if (directory == null) return;
                try (FileOutputStream output = new FileOutputStream(new File(directory, "preview.png"))) {
                    bitmap.compress(Bitmap.CompressFormat.PNG, 100, output);
                }
            } catch (IOException e) {
                android.util.Log.w("MiniMedia", "Local preview capture failed", e);
            } finally { bitmap.recycle(); }
        }, delay);
    }

    private void makeHome() {
        latte = getPreferences(MODE_PRIVATE).getBoolean("latte", false);
        setTheme(latte ? android.R.style.Theme_Material_Light_NoActionBar : android.R.style.Theme_Material_NoActionBar);
        BG = Color.parseColor(latte ? "#eff1f5" : "#181818");
        SURFACE = Color.parseColor(latte ? "#ccd0da" : "#282828");
        FG = Color.parseColor(latte ? "#4c4f69" : "#eeeeee");
        MUTED = Color.parseColor(latte ? "#55586f" : "#aaaaaa");
        ACCENT = Color.parseColor(latte ? "#1e66f5" : "#dddddd");
        BORDER = Color.parseColor(latte ? "#bcc0cc" : "#666666");
        FrameLayout frame = new FrameLayout(this);
        homeFrame = frame;
        menuOverlay = null;
        frame.setBackgroundColor(BG);
        wallpaperView = new WallpaperView();
        frame.addView(wallpaperView, new FrameLayout.LayoutParams(-1, -1));
        FrameLayout root = new FrameLayout(this);
        homeContent = root;
        frame.addView(root, new FrameLayout.LayoutParams(-1, -1));
        root.setVisibility(interaction.controlsShown() ? View.VISIBLE : View.INVISIBLE);
        root.setDescendantFocusability(interaction.controlsShown() ? android.view.ViewGroup.FOCUS_AFTER_DESCENDANTS
                : android.view.ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        setContentView(frame);

        FrameLayout bar = new FrameLayout(this);
        GradientDrawable barBackground = new GradientDrawable();
        barBackground.setColor(BG);
        barBackground.setCornerRadius(dp(4));
        barBackground.setStroke(1, BORDER);
        bar.setBackground(barBackground);
        clock = text("", 11, FG);
        clock.setGravity(Gravity.CENTER);
        bar.addView(clock, new FrameLayout.LayoutParams(-2, -1, Gravity.CENTER));
        network = new VpnIndicator();
        FrameLayout.LayoutParams statusParams = new FrameLayout.LayoutParams(dp(28), -1, Gravity.RIGHT);
        bar.addView(network, statusParams);
        FrameLayout.LayoutParams barParams = new FrameLayout.LayoutParams(-1, dp(24), Gravity.TOP);
        barParams.setMargins(dp(4), dp(4), dp(4), 0);
        root.addView(bar, barParams);

        appPanel = launcherPanel();
        LinearLayout prompt = row();
        TextView promptLabel = text("Apps:", 13, FG);
        promptLabel.setPadding(dp(4), 0, dp(8), 0);
        prompt.addView(promptLabel);
        search = new EditText(this);
        search.setId(View.generateViewId());
        search.setTypeface(font);
        search.setTextSize(14);
        search.setTextColor(FG);
        search.setHintTextColor(MUTED);
        search.setHint("Search apps…");
        search.setSingleLine(true);
        search.setIncludeFontPadding(false);
        search.setPadding(0, 0, dp(4), 0);
        search.setBackgroundColor(Color.TRANSPARENT);
        search.setInputType(android.text.InputType.TYPE_CLASS_TEXT
                | android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        search.setImeOptions(android.view.inputmethod.EditorInfo.IME_ACTION_SEARCH
                | android.view.inputmethod.EditorInfo.IME_FLAG_NO_EXTRACT_UI);
        search.setShowSoftInputOnFocus(false);
        search.setOnClickListener(v -> openSearchKeyboard());
        search.setOnKeyListener((v, code, event) -> {
            if (code == KeyEvent.KEYCODE_DPAD_CENTER || code == KeyEvent.KEYCODE_ENTER) {
                if (event.getAction() == KeyEvent.ACTION_UP) openSearchKeyboard();
                return true;
            }
            if (code == KeyEvent.KEYCODE_DPAD_DOWN) {
                if (event.getAction() == KeyEvent.ACTION_DOWN && firstTile != search) {
                    dismissSearchKeyboard();
                    firstTile.requestFocus();
                }
                return true;
            }
            return false;
        });
        search.setOnEditorActionListener((v, action, event) -> {
            dismissSearchKeyboard();
            if (firstTile != search) firstTile.requestFocus();
            return true;
        });
        prompt.addView(search, new LinearLayout.LayoutParams(0, -1, 1));
        appPanel.addView(prompt, new LinearLayout.LayoutParams(-1, dp(32)));
        addDivider(appPanel);
        appScroll = new ScrollView(this);
        appScroll.setVerticalScrollBarEnabled(false);
        appResults = column();
        appScroll.addView(appResults);
        appPanel.addView(appScroll, new LinearLayout.LayoutParams(-1, dp(136)));
        root.addView(appPanel, new FrameLayout.LayoutParams(panelWidth(), -2, Gravity.CENTER));
        searchableApps = launcherApps();
        renderAppResults("");
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
            public void onTextChanged(CharSequence s, int start, int before, int count) {
                renderAppResults(s.toString());
                armIdle();
            }
            public void afterTextChanged(Editable s) { }
        });
        firstTile.requestFocus();
        refreshStatus();
    }

    private void openSearchKeyboard() {
        search.requestFocus();
        ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE)).showSoftInput(search,
                InputMethodManager.SHOW_IMPLICIT);
    }

    private void dismissSearchKeyboard() {
        if (search != null) ((InputMethodManager)getSystemService(INPUT_METHOD_SERVICE))
                .hideSoftInputFromWindow(search.getWindowToken(), 0);
    }

    private void renderAppResults(String value) {
        String query = value.trim().toLowerCase(Locale.ROOT);
        appResults.removeAllViews();
        firstTile = search;
        settingsButton = null;
        themeSelectorButton = null;
        String[] titles = {"Jellyfin", "YouTube", "Moonlight", "Theme Selector", "Settings"};
        String[] descriptions = {"Media player", "Video player", "Game streaming", "Theme & wallpaper", "Preferences"};
        String[] packages = {"org.jellyfin.androidtv", "local.minimedia.youtube", "com.limelight", "", "com.android.tv.settings"};
        for (int i = 0; i < titles.length; i++) {
            if (!(titles[i] + " " + descriptions[i]).toLowerCase(Locale.ROOT).contains(query)) continue;
            final int index = i;
            View button = appResult(titles[i], descriptions[i], () -> {
                dismissSearchKeyboard();
                if (index == 0) launch(packages[0]);
                else if (index == 1) openYouTube();
                else if (index == 2) launch(packages[2]);
                else if (index == 3) showThemeSelector();
                else showSettings();
            });
            if (i == 3) themeSelectorButton = button;
            if (i == 4) settingsButton = button;
        }
        if (!query.isEmpty()) for (ResolveInfo app : searchableApps) {
            final String name = app.loadLabel(getPackageManager()).toString();
            final String pkg = app.activityInfo.packageName;
            if (Arrays.asList(packages).contains(pkg) || !name.toLowerCase(Locale.ROOT).contains(query)) continue;
            appResult(name, null, () -> { dismissSearchKeyboard(); launch(pkg); });
        }
        int count = appResults.getChildCount();
        if (count == 0) {
            TextView empty = text("No matching apps", 13, MUTED);
            empty.setGravity(Gravity.CENTER_VERTICAL);
            empty.setPadding(dp(4), 0, 0, 0);
            appResults.addView(empty, new LinearLayout.LayoutParams(-1, dp(32)));
        }
        appScroll.getLayoutParams().height = dp(34 * Math.max(1, Math.min(6, count)));
        appScroll.requestLayout();
        appScroll.scrollTo(0, 0);
    }

    private View appResult(String name, String description, Runnable action) {
        LinearLayout button = row();
        button.setId(View.generateViewId());
        button.setPadding(dp(4), 0, dp(4), 0);
        button.setDescendantFocusability(android.view.ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        TextView label = text(name, 14, FG);
        if (description != null) {
            String value = name + " (" + description + ")";
            android.text.SpannableString formatted = new android.text.SpannableString(value);
            formatted.setSpan(new android.text.style.RelativeSizeSpan(0.833333f),
                    name.length() + 1, value.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
            label.setText(formatted);
        }
        label.setSingleLine(true);
        label.setEllipsize(android.text.TextUtils.TruncateAt.END);
        button.addView(label, new LinearLayout.LayoutParams(-1, -2));
        focusable(button, true);
        button.setOnClickListener(v -> action.run());
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(32));
        params.topMargin = dp(2);
        appResults.addView(button, params);
        if (firstTile == search) {
            firstTile = button;
            button.setNextFocusUpId(search.getId());
            search.setNextFocusDownId(button.getId());
        }
        return button;
    }

    private int panelWidth() {
        return Math.min(dp(400), getResources().getDisplayMetrics().widthPixels - dp(24));
    }

    private LinearLayout launcherPanel() {
        LinearLayout panel = column();
        panel.setPadding(dp(6), dp(6), dp(6), dp(6));
        GradientDrawable background = new GradientDrawable();
        // Opaque for projection readability; no expensive live blur on this device.
        background.setColor(BG);
        background.setCornerRadius(dp(4));
        background.setStroke(1, ACCENT);
        panel.setBackground(background);
        return panel;
    }

    private void addDivider(LinearLayout panel) {
        View divider = new View(this);
        divider.setBackgroundColor(BORDER);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, 1);
        params.setMargins(0, dp(4), 0, dp(4));
        panel.addView(divider, params);
    }

    private void showSettings() { interaction.openMenu("Settings", false); }

    private void showThemeSelector() { interaction.openMenu("Theme Selector", true); }

    private void pushMenu(String page) { interaction.pushMenu(page); }

    private void removeMenu(boolean returnToThemeSelector) {
        menuGeneration++;
        if (menuOverlay != null) homeFrame.removeView(menuOverlay);
        menuOverlay = null;
        appPanel.setVisibility(View.VISIBLE);
        homeContent.setVisibility(interaction.controlsShown() ? View.VISIBLE : View.INVISIBLE);
        homeContent.setDescendantFocusability(android.view.ViewGroup.FOCUS_AFTER_DESCENDANTS);
        View target = returnToThemeSelector ? themeSelectorButton : settingsButton;
        if (interaction.controlsShown()) (target != null ? target : firstTile).requestFocus();
    }

    private View settingsButton;
    private View themeSelectorButton;

    private void renderMenu() {
        final int generation = ++menuGeneration;
        if (menuOverlay != null) homeFrame.removeView(menuOverlay);
        homeContent.setDescendantFocusability(android.view.ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        dismissSearchKeyboard();
        appPanel.setVisibility(View.INVISIBLE);
        menuPage = interaction.menuPath().get(interaction.menuPath().size() - 1);
        final String page = menuPage;
        menuOverlay = new FrameLayout(this);
        menuOverlay.setOnClickListener(v -> interaction.closeMenu());
        homeFrame.addView(menuOverlay, new FrameLayout.LayoutParams(-1, -1));
        LinearLayout panel = launcherPanel();
        panel.setClickable(true);
        FrameLayout.LayoutParams panelParams = new FrameLayout.LayoutParams(
                panelWidth(), -2, Gravity.CENTER);
        menuOverlay.addView(panel, panelParams);
        TextView title = text(android.text.TextUtils.join(" / ", interaction.menuPath()), 13, FG);
        title.setGravity(Gravity.CENTER_VERTICAL);
        title.setPadding(dp(6), 0, dp(6), 0);
        title.setSingleLine(true);
        title.setEllipsize(android.text.TextUtils.TruncateAt.START);
        panel.addView(title, new LinearLayout.LayoutParams(-1, dp(32)));
        addDivider(panel);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(false);
        scroll.setVerticalScrollBarEnabled(false);
        LinearLayout items = column();
        scroll.addView(items);
        panel.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        if ("Settings".equals(page)) {
            menuItem(items, "Appearance", "Theme & wallpaper", "›", () -> pushMenu("Appearance"));
            menuItem(items, "All apps", "Your installed apps", "›", () -> pushMenu("All apps"));
            menuItem(items, "WireGuard", "Manage your tunnel", "↗", () -> launch("local.minimedia.sdmcw"));
            menuItem(items, "Projector settings", "Picture, sound & connections", "↗", this::openSettings);
            menuItem(items, "Home setup", "Choose your home screen", "↗", this::selectHome);
        } else if ("Appearance".equals(page)) {
            menuItem(items, "Theme", latte ? "Catppuccin Latte" : "Monochrome", "›", () -> pushMenu("Theme"));
            boolean rotate = getPreferences(MODE_PRIVATE).getBoolean("rotate", true);
            menuItem(items, "Wallpaper rotation", "Every 15 minutes", rotate ? "ON" : "OFF", () -> {
                getPreferences(MODE_PRIVATE).edit().putBoolean("rotate", !rotate)
                    .putLong("wallpaperEpoch", System.currentTimeMillis() / 900000L).apply();
                renderMenu();
            });
            menuItem(items, "Next wallpaper", "Choose another at random", "→", () -> {
                chooseNextWallpaper();
                renderMenu();
            });
            menuItem(items, "Wallpapers", "Browse your collection", "›", () -> pushMenu("Wallpapers"));
            int timeout = getPreferences(MODE_PRIVATE).getInt("idleSeconds", 30);
            menuItem(items, "Hide controls", timeout == 0 ? "Never" : "After " + timeout + " seconds", "›", () -> pushMenu("Hide controls"));
        } else if ("Hide controls".equals(page)) {
            int timeout = getPreferences(MODE_PRIVATE).getInt("idleSeconds", 30);
            for (int value : new int[]{15, 30, 60, 0}) {
                menuItem(items, value == 0 ? "Never" : value + " seconds", null, timeout == value ? "✓" : "", () -> {
                    getPreferences(MODE_PRIVATE).edit().putInt("idleSeconds", value).apply();
                    armIdle();
                    renderMenu();
                });
            }
        } else if ("Theme".equals(page) || "Theme Selector".equals(page)) {
            menuItem(items, "Monochrome", "Charcoal · grayscale photos", !latte ? "✓" : "", () -> changeTheme(false));
            menuItem(items, "Catppuccin Latte", "Light palette · color photos", latte ? "✓" : "", () -> changeTheme(true));
        } else if ("Wallpapers".equals(page)) {
            String selected = getPreferences(MODE_PRIVATE).getString("wallpaper", "");
            for (int i = 0; i < wallpapers.length; i++) {
                final String image = wallpapers[i];
                LinearLayout item = menuItem(items, String.format(Locale.ROOT, "Wallpaper %02d", i + 1),
                        null, image.equals(selected) ? "✓" : "", () -> { selectWallpaper(image); renderMenu(); });
                ImageView thumbnail = new ImageView(this);
                thumbnail.setFocusable(false);
                thumbnail.setScaleType(ImageView.ScaleType.CENTER_CROP);
                imageLoader.execute(() -> {
                    if (generation != menuGeneration) return;
                    Bitmap decoded = decodeWallpaper(image, 16);
                    handler.post(() -> {
                        if (generation == menuGeneration && !isDestroyed()) thumbnail.setImageBitmap(decoded);
                    });
                });
                if (!latte) {
                    ColorMatrix matrix = new ColorMatrix(); matrix.setSaturation(0);
                    thumbnail.setColorFilter(new ColorMatrixColorFilter(matrix));
                }
                LinearLayout.LayoutParams thumbParams = new LinearLayout.LayoutParams(dp(65), dp(38));
                thumbParams.setMargins(0, 0, dp(12), 0);
                item.addView(thumbnail, 0, thumbParams);
            }
        } else if ("All apps".equals(page)) {
            for (ResolveInfo app : launcherApps()) {
                menuItem(items, app.loadLabel(getPackageManager()).toString(), null, "↗",
                        () -> launch(app.activityInfo.packageName));
            }
        } else if ("Home setup".equals(page)) {
            TextView explanation = text("This projector does not provide a home selector. MiniMedia can be selected as Home using ADB after checking the remote and settings.", 12, FG);
            explanation.setPadding(0, 0, 0, dp(18));
            items.addView(explanation);
        } else if ("YouTube setup".equals(page)) {
            items.addView(text("The custom YouTube app is not installed yet.", 12, FG));
        }
        addDivider(panel);
        TextView back = text("‹  Back", 12, MUTED);
        back.setGravity(Gravity.CENTER_VERTICAL);
        back.setPadding(dp(8), 0, dp(8), 0);
        focusable(back, true);
        back.setOnClickListener(v -> interaction.menuBack());
        LinearLayout.LayoutParams backParams = new LinearLayout.LayoutParams(-1, dp(32));
        panel.addView(back, backParams);
        int contentHeight = 0;
        for (int i = 0; i < items.getChildCount(); i++) {
            LinearLayout.LayoutParams p = (LinearLayout.LayoutParams)items.getChildAt(i).getLayoutParams();
            contentHeight += (p.height > 0 ? p.height : dp(80)) + p.topMargin + p.bottomMargin;
        }
        panelParams.height = Math.min(getResources().getDisplayMetrics().heightPixels - dp(48),
                contentHeight + dp(92) + 2);
        panel.setLayoutParams(panelParams);
        int position = interaction.menuPosition(page);
        View target = items.getChildCount() > 0 ? items.getChildAt(Math.min(position, items.getChildCount() - 1)) : back;
        if (!target.isFocusable()) target = back;
        target.requestFocus();
        final View focused = target;
        scroll.post(() -> { if (focused.getParent() == items) scroll.scrollTo(0, Math.max(0, focused.getTop() - dp(70))); });
    }

    private LinearLayout menuItem(LinearLayout items, String title, String subtitle, String trailing, Runnable action) {
        final int index = items.getChildCount();
        final String page = menuPage;
        LinearLayout item = row();
        item.setPadding(dp(8), dp(4), dp(8), dp(4));
        item.setDescendantFocusability(android.view.ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        LinearLayout labels = column();
        labels.addView(text(title, 13, FG));
        if (subtitle != null) {
            TextView caption = text(subtitle, 9, MUTED);
            caption.setPadding(0, dp(5), 0, 0);
            labels.addView(caption);
        }
        item.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
        TextView marker = text(trailing, 12, ACCENT);
        marker.setPadding(dp(10), 0, 0, 0);
        item.addView(marker);
        focusable(item, true);
        item.setOnFocusChangeListener((v, focused) -> {
            v.setBackground(backplate(focused, true));
            if (focused) interaction.rememberMenuPosition(page, index);
        });
        item.setOnClickListener(v -> action.run());
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(subtitle == null ? 42 : 54));
        params.setMargins(0, dp(2), 0, 0);
        items.addView(item, params);
        return item;
    }

    private void changeTheme(boolean light) {
        getPreferences(MODE_PRIVATE).edit().putBoolean("latte", light).apply();
        makeHome();
        renderMenu();
    }

    private void rotateWallpaperIfDue() {
        if (wallpapers.length == 0 || !getPreferences(MODE_PRIVATE).getBoolean("rotate", true)) return;
        long epoch = System.currentTimeMillis() / 900000L;
        if (epoch != getPreferences(MODE_PRIVATE).getLong("wallpaperEpoch", -1)) chooseNextWallpaper();
    }

    private void chooseNextWallpaper() {
        if (wallpapers.length == 0) return;
        String previous = getPreferences(MODE_PRIVATE).getString("wallpaper", "");
        int oldIndex = Arrays.asList(wallpapers).indexOf(previous);
        int index = random.nextInt(wallpapers.length > 1 && oldIndex >= 0 ? wallpapers.length - 1 : wallpapers.length);
        if (wallpapers.length > 1 && oldIndex >= 0 && index >= oldIndex) index++;
        selectWallpaper(wallpapers[index]);
    }

    private void selectWallpaper(String image) {
        getPreferences(MODE_PRIVATE).edit().putString("wallpaper", image)
                .putLong("wallpaperEpoch", System.currentTimeMillis() / 900000L).apply();
        if (wallpaperView != null) wallpaperView.load();
    }

    private void openYouTube() {
        if (isInstalled("local.minimedia.youtube")) launch("local.minimedia.youtube");
        else pushMenu("YouTube setup");
    }

    private boolean isInstalled(String name) {
        try { getPackageManager().getApplicationInfo(name, 0); return true; }
        catch (android.content.pm.PackageManager.NameNotFoundException e) { return false; }
    }

    private void launch(String name) {
        Intent target = getPackageManager().getLeanbackLaunchIntentForPackage(name);
        if (target == null) target = getPackageManager().getLaunchIntentForPackage(name);
        if (target == null) {
            Toast.makeText(this, "App is not installed or cannot be opened", Toast.LENGTH_LONG).show();
            return;
        }
        try { startActivity(target); }
        catch (ActivityNotFoundException | SecurityException e) {
            Toast.makeText(this, "Unable to open this app", Toast.LENGTH_LONG).show();
        }
    }

    private void openSettings() {
        Intent target = getPackageManager().getLeanbackLaunchIntentForPackage("com.android.tv.settings");
        try { startActivity(target != null ? target : new Intent(Settings.ACTION_SETTINGS)); }
        catch (ActivityNotFoundException e) {
            Toast.makeText(this, "Settings is unavailable", Toast.LENGTH_LONG).show();
        }
    }

    private void selectHome() {
        try { startActivity(new Intent(Settings.ACTION_HOME_SETTINGS)); }
        catch (ActivityNotFoundException e) {
            pushMenu("Home setup");
        }
    }

    private List<ResolveInfo> launcherApps() {
        LinkedHashMap<String, ResolveInfo> unique = new LinkedHashMap<>();
        for (String category : new String[]{Intent.CATEGORY_LEANBACK_LAUNCHER, Intent.CATEGORY_LAUNCHER}) {
            Intent query = new Intent(Intent.ACTION_MAIN).addCategory(category);
            for (ResolveInfo info : getPackageManager().queryIntentActivities(query, 0)) {
                if (!getPackageName().equals(info.activityInfo.packageName))
                    unique.putIfAbsent(info.activityInfo.packageName, info);
            }
        }
        List<ResolveInfo> apps = new ArrayList<>(unique.values());
        Collections.sort(apps, (a, b) -> a.loadLabel(getPackageManager()).toString()
                .compareToIgnoreCase(b.loadLabel(getPackageManager()).toString()));
        return apps;
    }

    private void refreshStatus() {
        clock.setText(new SimpleDateFormat("EEE MMM d  hh:mm a", Locale.getDefault()).format(new Date()));
        ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
        NetworkCapabilities caps = cm == null ? null : cm.getNetworkCapabilities(cm.getActiveNetwork());
        updateConnection(caps);
    }

    private void updateConnection(NetworkCapabilities caps) {
        boolean vpn = caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN);
        network.update(vpn, vpn ? "VPN active" : caps == null ? "Offline · VPN inactive" : "VPN inactive");
    }

    private void startNetworkUpdates() {
        if (networkCallback != null) return;
        ConnectivityManager cm = (ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
        if (cm == null) return;
        networkCallback = new ConnectivityManager.NetworkCallback() {
            @Override public void onAvailable(Network value) {
                if (networkCallback == this) observedNetwork = value;
            }
            @Override public void onCapabilitiesChanged(Network value, NetworkCapabilities caps) {
                if (networkCallback == this && value.equals(observedNetwork)) updateConnection(caps);
            }
            @Override public void onLost(Network value) {
                if (networkCallback == this && value.equals(observedNetwork)) {
                    observedNetwork = null;
                    updateConnection(null);
                }
            }
        };
        try {
            // Main-thread delivery; use the supplied capabilities, avoiding a racy
            // synchronous capabilities query from inside a network callback.
            cm.registerDefaultNetworkCallback(networkCallback, handler);
        } catch (RuntimeException e) {
            networkCallback = null;
            android.util.Log.w("MiniMedia", "Network callback unavailable; retaining periodic status", e);
        }
    }

    private void stopNetworkUpdates() {
        ConnectivityManager.NetworkCallback callback = networkCallback;
        networkCallback = null;
        observedNetwork = null;
        if (callback == null) return;
        ConnectivityManager cm = (ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
        if (cm != null) try { cm.unregisterNetworkCallback(callback); }
        catch (IllegalArgumentException ignored) { }
    }

    /** Symbolic, 16dp status glyph with Waybar's 6dp side padding. */
    private final class VpnIndicator extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private boolean active;
        VpnIndicator() { super(HomeActivity.this); }
        void update(boolean value, String description) {
            active = value;
            setContentDescription(description);
            setTooltipText(description);
            invalidate();
        }
        @Override protected void onDraw(Canvas canvas) {
            canvas.save();
            float size = dp(16);
            canvas.translate((getWidth() - size) / 2f, (getHeight() - size) / 2f);
            canvas.scale(size / 24f, size / 24f);
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(1.5f);
            paint.setStrokeCap(Paint.Cap.ROUND);
            paint.setStrokeJoin(Paint.Join.ROUND);
            paint.setColor(active ? Color.parseColor(latte ? "#209fb5" : "#c0c0c0") : MUTED);
            android.graphics.Path shield = new android.graphics.Path();
            shield.moveTo(12, 2); shield.lineTo(20, 5); shield.lineTo(20, 11);
            shield.cubicTo(20, 16, 16, 20, 12, 22);
            shield.cubicTo(8, 20, 4, 16, 4, 11);
            shield.lineTo(4, 5); shield.close();
            canvas.drawPath(shield, paint);
            if (active) {
                android.graphics.Path check = new android.graphics.Path();
                check.moveTo(8, 12); check.lineTo(11, 15); check.lineTo(16, 9);
                canvas.drawPath(check, paint);
            } else canvas.drawLine(3, 3, 21, 21, paint);
            canvas.restore();
        }
    }

    private void focusable(View view, boolean quiet) {
        view.setFocusable(true);
        view.setClickable(true);
        view.setBackground(backplate(false, quiet));
        view.setOnFocusChangeListener((v, focused) -> {
            v.setBackground(backplate(focused, quiet));
            if (v instanceof TextView) ((TextView)v).setTextColor(focused ? FG : MUTED);
        });
    }

    private GradientDrawable backplate(boolean focused, boolean quiet) {
        GradientDrawable shape = new GradientDrawable();
        int color = focused ? (latte ? SURFACE : Color.rgb(68, 68, 68)) : SURFACE;
        shape.setColor(quiet && !focused ? Color.TRANSPARENT : color);
        shape.setCornerRadius(quiet ? 0 : dp(4));
        shape.setStroke(quiet ? 0 : 1, focused ? ACCENT : BORDER);
        return shape;
    }

    private LinearLayout row() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.HORIZONTAL);
        layout.setGravity(Gravity.CENTER_VERTICAL);
        return layout;
    }
    private LinearLayout column() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        return layout;
    }
    private TextView text(String value, float size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTypeface(font);
        view.setIncludeFontPadding(false);
        return view;
    }
    private int dp(float value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private void armIdle() {
        handler.removeCallbacks(idle);
        int seconds = getPreferences(MODE_PRIVATE).getInt("idleSeconds", 30);
        long delay = interaction.idleDelayMillis(seconds);
        if (delay > 0) handler.postDelayed(idle, delay);
    }

    private void renderShownControls(boolean animate, boolean wasHidden) {
        if (homeContent == null) return;
        homeContent.animate().cancel();
        homeContent.setVisibility(View.VISIBLE);
        homeContent.setDescendantFocusability(android.view.ViewGroup.FOCUS_AFTER_DESCENDANTS);
        if (animate && wasHidden) {
            homeContent.setAlpha(0f);
            homeContent.animate().alpha(1f).setDuration(100)
                .setInterpolator(new android.view.animation.PathInterpolator(0.15f, 0f, 0.1f, 1f))
                .withEndAction(null).start();
        } else homeContent.setAlpha(1f);
        wallpaperView.invalidate();
        if (wasHidden) firstTile.requestFocus();
    }

    private void renderHiddenControls(boolean animate) {
        handler.removeCallbacks(idle);
        if (homeContent == null) return;
        homeContent.setDescendantFocusability(android.view.ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        homeContent.animate().cancel();
        wallpaperView.invalidate();
        if (animate) homeContent.animate().alpha(0f).setDuration(100)
            .setInterpolator(new android.view.animation.PathInterpolator(0.15f, 0f, 0.1f, 1f))
            .withEndAction(() -> { if (!interaction.controlsShown()) homeContent.setVisibility(View.INVISIBLE); }).start();
        else { homeContent.setAlpha(0f); homeContent.setVisibility(View.INVISIBLE); }
    }

    private boolean navigationKey(int code) {
        return code == KeyEvent.KEYCODE_DPAD_DOWN || code == KeyEvent.KEYCODE_DPAD_UP
            || code == KeyEvent.KEYCODE_DPAD_LEFT || code == KeyEvent.KEYCODE_DPAD_RIGHT
            || code == KeyEvent.KEYCODE_DPAD_CENTER || code == KeyEvent.KEYCODE_ENTER
            || code == KeyEvent.KEYCODE_NUMPAD_ENTER || code == KeyEvent.KEYCODE_MENU;
    }

    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        LauncherInteraction.KeyAction action = event.getAction() == KeyEvent.ACTION_DOWN
                ? LauncherInteraction.KeyAction.DOWN : event.getAction() == KeyEvent.ACTION_UP
                ? LauncherInteraction.KeyAction.UP : LauncherInteraction.KeyAction.OTHER;
        if (interaction.key(event.getKeyCode(), action, navigationKey(event.getKeyCode()),
                event.getUnicodeChar(), event.isCtrlPressed() || event.isAltPressed())) return true;
        return super.dispatchKeyEvent(event);
    }

    @Override public boolean dispatchTouchEvent(MotionEvent event) {
        int masked = event.getActionMasked();
        LauncherInteraction.TouchAction action = masked == MotionEvent.ACTION_DOWN
                ? LauncherInteraction.TouchAction.DOWN
                : masked == MotionEvent.ACTION_UP || masked == MotionEvent.ACTION_CANCEL
                ? LauncherInteraction.TouchAction.END : LauncherInteraction.TouchAction.OTHER;
        if (interaction.touch(action)) return true;
        return super.dispatchTouchEvent(event);
    }

    @Override protected void onResume() {
        super.onResume();
        startNetworkUpdates();
        handler.removeCallbacks(tick);
        tick.run();
        interaction.resume();
    }
    @Override protected void onPause() {
        stopNetworkUpdates();
        handler.removeCallbacks(tick);
        handler.removeCallbacks(idle);
        interaction.pause();
        super.onPause();
    }
    @Override protected void onDestroy() {
        stopNetworkUpdates();
        menuGeneration++;
        wallpaperGeneration++;
        imageLoader.shutdownNow();
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
    @Override public void onBackPressed() { interaction.back(); }

    private Bitmap decodeWallpaper(String image, int sampleSize) {
        try (InputStream input = getAssets().open("wallpapers/" + image)) {
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inSampleSize = sampleSize;
            options.inPreferredConfig = Bitmap.Config.RGB_565;
            return BitmapFactory.decodeStream(input, null, options);
        } catch (IOException e) { return null; }
    }

    private final class WallpaperView extends View {
        private Bitmap bitmap;
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        WallpaperView() {
            super(HomeActivity.this);
            load();
        }
        void load() {
            final int generation = ++wallpaperGeneration;
            if (wallpapers.length > 0) {
                String selected = getPreferences(MODE_PRIVATE).getString("wallpaper", wallpapers[0]);
                if (!Arrays.asList(wallpapers).contains(selected)) selected = wallpapers[0];
                final String image = selected;
                imageLoader.execute(() -> {
                    if (generation != wallpaperGeneration) return;
                    Bitmap decoded = decodeWallpaper(image, 1);
                    handler.post(() -> {
                        if (generation != wallpaperGeneration || isDestroyed() || wallpaperView != this) return;
                        if (decoded != null) bitmap = decoded;
                        invalidate();
                    });
                });
            }
            if (!latte) {
                ColorMatrix matrix = new ColorMatrix();
                matrix.setSaturation(0);
                paint.setColorFilter(new ColorMatrixColorFilter(matrix));
            } else paint.setColorFilter(null);
            invalidate();
        }
        @Override protected void onDraw(Canvas canvas) {
            canvas.drawColor(BG);
            if (bitmap == null) return;
            float scale = Math.max(getWidth() / (float)bitmap.getWidth(), getHeight() / (float)bitmap.getHeight());
            float width = bitmap.getWidth() * scale, height = bitmap.getHeight() * scale;
            canvas.drawBitmap(bitmap, null, new RectF((getWidth() - width)/2, (getHeight() - height)/2,
                    (getWidth() + width)/2, (getHeight() + height)/2), paint);

        }
    }

}
