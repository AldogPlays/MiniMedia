# BOOMAIR privacy pass

This pass preserves the six retained applications, Android/Google core, Play
Store, certificates, WireGuard configuration, Bluetooth/remote, HDMI, audio,
projector controls and firmware update components. No application data is erased.

## Applied changes

- Disabled `com.google.android.apps.nbu.smartconnect.tv` (Data Saver).
- Disabled `com.google.android.sss.authbridge` (Second Screen Setup Auth Bridge).
- Disabled `com.google.android.partnersetup` (Google Partner Setup).
- Set global `ble_scan_always_enabled=0`: disable BLE scanning while Bluetooth
  is off. Bluetooth itself remains available.
- Set global `send_action_app_error=0`: disable the Android crash-report action.
  This does not control every vendor/Google diagnostics mechanism.
- Revoked `android.permission.RECORD_AUDIO` for `local.minimedia.youtube` and
  `com.google.android.inputmethod.latin`, as requested. Typed search remains usable.
- Switched ADB from TCP port 5555 plus USB to USB-only. The 5555 listener is absent.
  The subsequent VPN reboot test showed that this firmware resets the TCP port
  to 5555 at startup, despite `adb_wifi_enabled=0`. The USB-only change is
  session-scoped; it has to be repeated after reboot until a persistent firmware
  control is established. Phone-remote ports 6466/6467 remain available.

The package identities/components were inspected from APKs installed on this
BOOMAIR, rather than inferred from a generic removal list. Partner Setup's
manifest includes RLZ ping and installed-app jobs. The vendor factory suite
includes focus/keystone/calibration tools and log/TCP services; it was retained
because those hardware dependencies have not been established. Local audit
manifests and APK copies are under ignored `private/privacy-audit/`.

Location was already disabled and always-on Wi-Fi scanning was already off.
Google Play services and vendor services still run. No packet-capture audit or
claim of eliminating telemetry is made.

## Reproduction and recovery

Run from the project directory, with the BOOMAIR attached over USB:

```bash
nix-shell -p python3 --run 'python3 scripts/privacy-device.py --apply --no-microphone'
```

The script records prior values before mutations and attempts rollback on failure.
It distinguishes an absent setting from an explicit value when restoring. It
waits for USB re-enumeration to settle and verifies the resulting ADB mode.

The applied recovery record is:
`private/device-changes/20261120T012858855542Z-privacy.json`.
Its initial verification hit a transient USB disconnect; all intended changes
were subsequently verified and the journal was completed, retaining the original
states and the transient-error history. The corrected reconnect path was then
successfully exercised on the device.

Restore the original state with:

```bash
nix-shell -p python3 --run 'python3 scripts/privacy-device.py --restore private/device-changes/20261120T012858855542Z-privacy.json'
```

Restoration also re-enables the original TCP debugging port 5555 and restores
both prior microphone grants. This recovery record is separate from the earlier
Home/debloat record; restoring one does not undo the other pass.

## Validation

- Recovery checks cover missing settings, exact values, allowlists, rollback
  continuation, user-specific permission parsing and interrupted ADB restarts.
- Three package states, two settings, both microphone permissions, USB-only ADB,
  absence of the 5555 listener, retained applications and default Home verified.
- YouTube starts with microphone access revoked and installs the bundled policy;
  playback/ad-filter behavior still needs its separate end-to-end check.
- The TV keyboard opens for typed search with microphone permission revoked.

The VPN icon now subscribes to Android's default-network callbacks while Home
is resumed, using callback-supplied capabilities. It unregisters when Home pauses
and ignores stale callbacks. Device checks found one subscription in Home and
zero while YouTube was open. A minute timer remains for clock/wallpaper and
fallback refresh. No new permission or background service was added. The icon
reports Android's active VPN transport, not WireGuard handshake freshness.
