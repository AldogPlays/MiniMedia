package com.android.settings;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

/** Temporary BOOMAIR firmware compatibility entry; no certificate bytes or privileges. */
public final class MiniMediaCertificateActivity extends Activity {
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        if (state != null) return;
        if (getIntent().getBooleanExtra("verify_certificate", false)) {
            verifyCertificate();
            finish();
            return;
        }
        // Android 11's unmodified installer checks the actual calling package against
        // com.android.settings, which is missing on this TV firmware. It then retains
        // its normal file chooser, CA warning and user approval flow.
        Intent intent = new Intent("android.credentials.INSTALL")
            .setClassName("com.android.certinstaller", "com.android.certinstaller.CertInstallerMain")
            .putExtra("certificate_install_usage", "ca");
        startActivityForResult(intent, 1);
    }
    private void verifyCertificate() {
        final String expected = "5551cac552c5368d52aae138c4c0d41c89deeba20c5ea91fe4dcae1f4e1ecd43";
        try {
            java.security.KeyStore store = java.security.KeyStore.getInstance("AndroidCAStore");
            store.load(null);
            java.util.Enumeration<String> aliases = store.aliases();
            while (aliases.hasMoreElements()) {
                java.security.cert.Certificate certificate = store.getCertificate(aliases.nextElement());
                byte[] digest = java.security.MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded());
                StringBuilder hex = new StringBuilder();
                for (byte value : digest) hex.append(String.format(java.util.Locale.ROOT, "%02x", value & 255));
                if (expected.equals(hex.toString())) {
                    android.util.Log.i("MiniMediaCA", "Verified exact Caddy root in AndroidCAStore: " + expected);
                    return;
                }
            }
            android.util.Log.e("MiniMediaCA", "Expected Caddy root absent from AndroidCAStore");
        } catch (Exception error) { android.util.Log.e("MiniMediaCA", "Certificate verification failed", error); }
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == 1) {
            android.util.Log.i("MiniMediaCA", "System installer returned result " + result);
            finish();
        }
    }
}
