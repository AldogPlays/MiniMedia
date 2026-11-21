package local.minimedia.sdmcpressure;

import android.app.Activity;
import android.app.ActivityManager;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.Log;
import android.widget.TextView;
import java.util.ArrayList;

/** Temporary, bounded foreground test. No network, storage or VPN permissions. */
public final class PressureActivity extends Activity {
    private volatile boolean stopped;
    private final ArrayList<byte[]> allocations = new ArrayList<>();
    private TextView status;
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        status = new TextView(this);
        status.setText("Testing VPN survival during vendor memory cleanup…\nThis closes automatically.");
        status.setTextSize(24);
        status.setPadding(64, 64, 64, 64);
        setContentView(status);
        new Thread(this::test, "bounded-pressure-test").start();
    }
    private void test() {
        long started = SystemClock.elapsedRealtime();
        ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
        ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
        int allocated = 0;
        int limit = Math.max(0, Math.min(512, (int) (Runtime.getRuntime().maxMemory() / 1048576) - 64));
        try {
            while (!stopped && SystemClock.elapsedRealtime() - started < 45000) {
                am.getMemoryInfo(memory);
                long available = memory.availMem / 1048576;
                if (available < 300) {
                    Log.w("MiniMediaPressure", "Safety floor reached; releasing allocations");
                    break;
                }
                // Stay below the vendor's 450 MiB threshold, with >=300 MiB free.
                if (available > 400 && allocated + 8 <= limit) {
                    byte[] block = new byte[8 * 1048576];
                    for (int i = 0; i < block.length; i += 4096) block[i] = 1;
                    allocations.add(block);
                    allocated += 8;
                    SystemClock.sleep(80);
                } else {
                    Log.i("MiniMediaPressure", "HOLD availableMiB=" + available + " allocatedMiB=" + allocated);
                    SystemClock.sleep(1000);
                }
            }
        } catch (OutOfMemoryError error) {
            Log.w("MiniMediaPressure", "Application heap limit reached; releasing allocations");
        } finally {
            allocations.clear();
            Log.i("MiniMediaPressure", "DONE; allocations released");
            runOnUiThread(this::finish);
        }
    }
    @Override public void onPause() {
        stopped = true;
        super.onPause();
    }
}
