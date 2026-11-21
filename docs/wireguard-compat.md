# BOOMAIR-compatible WireGuard

> Public-source note: device serials are configured locally; network addresses
> below are illustrative replacements. See [local setup](local-setup.md).

Package: `local.minimedia.sdmcw`, based on official WireGuard Android
`1.0.20260315`. This is a locally maintained derivative, not an official release.
The package name satisfies the installed SDMC memory-cleanup exemption. It has
an ordinary application UID and the existing MiniMedia signing identity; it
does not impersonate a platform-signed application or acquire system privileges.

## Bounded changes

`python3 scripts/build-wireguard.py` verifies the official APK's SHA-256 and
WireGuard publisher certificate, then uses checksum-pinned Apktool 3.0.3.
It changes the manifest's application ID, two provider authorities, custom
control permission and AndroidX-generated receiver permission. Fully qualified
Java component names stay unchanged. Min/target SDK levels are preserved.

Only three disassembled Java classes change: the application-ID literal in the
user agent, log-export URI, and updater class. The update monitor becomes a
no-op and the APK-name prefix changes; `REQUEST_INSTALL_PACKAGES` is removed.
The reassembled DEX is disassembled again, verifying every class against the
declared transformation (ignoring whitespace and equivalent implicit false/null
static initializers). All 2,099 classes are checked. No tunnel/backend or
cryptographic Java code is changed.

Revision 1 preserved native libraries entirely. Startup exposed an inherited
optional UAPI socket path under the stock app's private directory, producing a
permission-denied log despite working JNI control and traffic. Revision 2 moves
that one same-length path literal in each checksum-pinned `libwg-go.so` to the
compatible app's own private cache. Every byte outside that declared range is
preserved; all other native libraries and resources remain identical. The native
networking and cryptographic instructions are unchanged. Root/wg-quick operation
is not a supported mode for this device-specific derivative.

The build report in `dist/minimedia-wireguard.build.json` records inputs,
publisher identity, tool hash, patch ranges, unchanged/changed entry hashes,
class checks and final APK hash. The APK retains existing license resources and
adds `assets/minimedia/NOTICE.txt`. Updates must be rebuilt and signed locally;
the official app updater cannot update this package/signature.

## Device migration and validation

The corrected split-tunnel profile was re-imported with the existing private key,
address, peer and DNS settings; `AllowedIPs` remain `192.0.2.0/24,198.51.100.0/24`.
The original host export remains unchanged. Temporary plaintext export and UI
dump were removed from projector Downloads after import.

Always-on now selects `local.minimedia.sdmcw`, with lockdown `0`. MiniMedia's
Settings shortcut opens this copy. Stock `com.wireguard.android` is disabled
for user 0 with its data retained. Finalize/privacy scripts now retain the
compatible app and the debloat plan includes the stock copy.

The recorded memory-pressure test reached 374 MiB available, dispatched the
vendor trim callback and observed the service force-stop stock WireGuard,
MiniMedia and other non-exempt apps. Compatible WireGuard retained PID 3272
and private pings passed. The temporary pressure app was uninstalled. See
[the bounded test](../device-tests/vpn-pressure/README.md).

Both revisions passed unattended reboot startup: Android logged an always-on
service launch, the clock synchronized, and the tunnel restored and received a
handshake response. Revision 1 also retained the same VPN process across the
physical sleep/wake test, with private and public reachability restored on wake.
Revision 2 eliminated the native socket-path error and passed Wi-Fi
disconnect/reconnect with the same VPN process and 3/3 private and 2/2 public
ping replies. The Home shortcut opens its TV activity. Installed APK hash,
retained app states, default Home and microphone revocations were checked;
network ADB was returned to USB-only after the final reboot. Firmware can still
reopen port 5555 on a future reboot. An overnight soak has not yet
been completed; successful short tests do not prove indefinite connectivity.

## Recovery

Journal: `private/device-changes/20261120T043401665415Z-wireguard-compat.json`.
Before migration, stock enabled-state was Android default (`0`) and always-on
selected `com.wireguard.android`, with lockdown `0`. Launcher backup is
`private/original/pre-wireguard-compat-home.apk`.

To restore that previous configuration, with USB debugging attached:

```bash
adb -s "$MINIMEDIA_SERIAL" shell pm default-state --user 0 com.wireguard.android
adb -s "$MINIMEDIA_SERIAL" shell settings --user 0 put secure always_on_vpn_app com.wireguard.android
adb -s "$MINIMEDIA_SERIAL" shell settings --user 0 put secure always_on_vpn_lockdown 0
adb -s "$MINIMEDIA_SERIAL" shell pm disable-user --user 0 local.minimedia.sdmcw
adb -s "$MINIMEDIA_SERIAL" install -r private/original/pre-wireguard-compat-home.apk
adb -s "$MINIMEDIA_SERIAL" reboot
```

This preserves both apps' saved profiles. Restoring stock also restores its
vulnerability to the vendor cleanup; it is a recovery path, not the recommended
reliability setup. The independent earlier privacy/debloat journals and CA store
are unchanged.
