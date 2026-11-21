package local.minimedia.youtube;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.util.Log;
import dev.cobalt.shell.Shell;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import org.chromium.content_public.browser.WebContents;

/** Adds only our local page policy to the pinned upstream Cobalt activity. */
public final class CustomActivity extends dev.cobalt.app.MainActivity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private String script;
    private long started;
    private boolean visible;
    private int lastFailureCount;
    private final Runnable probe = new Runnable() {
        @Override public void run() {
            if (!visible) return;
            try {
                Shell shell = getActiveShell();
                WebContents contents = shell == null ? null : shell.getWebContents();
                if (contents != null && script != null) {
                    contents.evaluateJavaScript("(function(){if(!/(^|\\.)youtube\\.com$/.test(location.hostname))return 'waiting';return window.__miniMediaYT?'ready':'missing';})()", value -> {
                        if (!visible) return;
                        if ("\"missing\"".equals(value)) {
                            contents.evaluateJavaScript(script, result -> Log.i("MiniMediaYT", "Local policy injection: " + result));
                        }
                    });
                }
            } catch (RuntimeException e) {
                if (lastFailureCount++ < 3) Log.w("MiniMediaYT", "Page not ready for local policy", e);
            }
            handler.postDelayed(this, SystemClock.uptimeMillis() - started < 15000 ? 300 : 5000);
        }
    };

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        try (InputStream input = getAssets().open("minimedia/policy.js")) {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            script = output.toString("UTF-8");
        } catch (IOException e) { throw new IllegalStateException("Bundled local policy is missing", e); }
        Log.i("MiniMediaYT", "Custom Cobalt build; local policy asset loaded");
    }
    @Override protected void onResume() {
        super.onResume();
        visible = true;
        started = SystemClock.uptimeMillis();
        handler.removeCallbacks(probe);
        handler.post(probe);
    }
    @Override protected void onPause() {
        visible = false;
        handler.removeCallbacks(probe);
        super.onPause();
    }
    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }
}
