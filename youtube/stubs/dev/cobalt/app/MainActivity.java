package dev.cobalt.app;
// Compile-only API declarations, verified against the pinned original DEX.
// These stubs must never be packaged in the output APK.
public class MainActivity extends android.app.Activity {
    @Override public void onCreate(android.os.Bundle state) { super.onCreate(state); }
    public dev.cobalt.shell.Shell getActiveShell() { return null; }
}
