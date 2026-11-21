# MiniMedia

> Public-source note: device serials are configured locally; network addresses
> below are illustrative replacements. See [local setup](docs/local-setup.md).

A native Android TV home screen using the Monochrome theme from
`~/Projects/nixos-config`: charcoal surfaces, white/gray text, Monaspace Neon,
thin borders, and restrained spacing. Built for the AURZEN BOOMAIR's Android 11
and 32-bit ARM runtime. The launcher has no network access, recommendations,
advertising SDK, WebView, or resident background service. It can read network
state to display connection/VPN status.

WireGuard [always-on startup](docs/vpn-startup.md) is configured for user 0 with
lockdown disabled, using [a compatible local derivative](docs/wireguard-compat.md)
that survives the observed vendor memory cleanup. Reboot verification confirmed automatic tunnel startup,
handshake and private-network/Internet reachability. An IP-based Android NTP
setting resolves the boot-time clock/private-DNS dependency found during testing.

Original MiniMedia code is licensed under [MIT](LICENSE); bundled assets retain
the terms in [third-party notices](THIRD-PARTY-NOTICES.md). Owner-specific context
and the full original history are kept in ignored local storage, described in
[local setup](docs/local-setup.md).

Module responsibilities and local test commands are described in
[the architecture notes](docs/architecture.md); [the glossary](GLOSSARY.md) defines
shared project terms.

## Current state

The centered-list revision is built, signature/alignment verified and installed
on the BOOMAIR. Device captures verify the Monochrome and Latte app lists,
Monochrome Settings and Appearance pages, and wallpaper-only idle mode after
the 30-second timeout. ADB D-pad navigation opens Settings, nested Back returns to
its parent, and Back to the app list restores focus to Settings. Implicit Home
resolution still selects MiniMedia.
The top-bar/search revision is installed and visually checked in Latte.
Device checks cover installed-app filtering (WireGuard), no matches, keyboard
opening through Up/OK, query clearing, the bar in Settings, and a delayed
capture showing both the bar and launcher hidden after the idle timeout.

The native launcher uses a compact centered app list based on the desktop's
Rofi configuration: Monaspace Neon, a thin outer border, 4dp corners, 6dp panel
padding and flat rectangular selection highlights. Jellyfin, YouTube, Moonlight,
Theme Selector and Settings share one icon-free list with 32dp rows. Each label follows Rofi's
`{name} ({generic})` format with a smaller inline parenthetical description.
An icon-only VPN indicator sits at the right of a thin Waybar-style top bar, with the
desktop-style date/clock centered. The bar shares the launcher's visibility
and fade timing and stays visible through nested menus. Settings and nested pages replace the app list in the
same position, with breadcrumb navigation, remembered focus and wallpaper
thumbnails. Long lists scroll within the available screen height.
The 16dp VPN glyph uses the desktop network-role color and 6dp side padding.
A checked shield means Android reports an active VPN transport; a crossed
shield means no active VPN transport. Its accessibility label/tooltip includes
the status. This reports Android's VPN state, not a verified WireGuard handshake.
Status updates use Android network callbacks while Home is resumed, rather than
waiting for the minute timer. The listener is released when another app opens.

The reference is `nixos-config/home/<user>/programs.nix` (Rofi) and
`theme/common.nix` (geometry/type), with colors from `theme/monochrome.nix` and
`theme/latte.nix`. Text and row heights are adapted for a projector remote.
Panels are opaque for readability without live blur. The desktop's `dwindle`
layout controls running windows; the projector launcher opens Android apps
fullscreen. No simulated workspace numbers or window contents are shown.

MiniMedia is the default Home. Google TV and the completed Google TV setup
package are disabled for user 0. The launcher and nested menus use the same
local theme; no system-wide app theming is applied.

All 54 photos from `~/Pictures/Wallpapers` have projector-sized WebP copies under
`private/wallpapers/`, totaling about 10.6 MiB. The originals are untouched.
Monochrome applies grayscale at display time; Latte displays the color copy.
The projector's appearance selection is independent of the desktop's selection.
Wallpaper rotation defaults to on, matching the desktop's :00/:15/:30/:45
schedule and avoiding an immediate repeat when multiple images are available.
Settings → Appearance offers a rotation toggle, Next wallpaper, and manual
selection. Manual selection keeps the rotation setting; disable rotation to pin
a photo. The timer runs only while Home is visible, and reconciles an elapsed
quarter-hour on return from another app. No background service is added.
Full-size photos and sampled thumbnails decode on one worker rather than the UI
thread. Replaced menu/image requests are ignored, and the worker shuts down when
the activity is destroyed.

Home starts with only its wallpaper. The first D-pad/Enter/Menu press reveals
controls without activating a tile; Back hides controls after closing any nested
menus. Controls fade in/out in 100ms without movement, using the desktop's
`quick` Bézier curve (0.15, 0, 0.1, 1), and return to the wallpaper after 30 idle seconds by
default. Settings → Appearance → Hide controls offers 15/30/60 seconds or Never.
Activity pause stops the timer and hides controls for the next return. Latte
uses opaque panels, darker secondary text and a visible selection highlight.
Neither theme applies a full-screen wallpaper wash. Physical remote feel and
projected readability still need owner feedback.

The app panel has a Rofi-style search entry. With an empty query it shows the
five main entries; typing filters their names/descriptions and also finds other
installed launcher apps by name. Search is local and adds no network permission.
Up from the first result focuses search; OK opens the TV keyboard. Down or the
keyboard's Search action returns focus to results. A physical keyboard can type
directly from the app list. Back dismisses the keyboard, then clears a query,
then hides the launcher. Empty matches show a message; longer results scroll.

Theme Selector is a first-class searchable launcher entry, like the desktop's
`rofi-theme-selector.desktop`. It selects Monochrome or Catppuccin Latte for
MiniMedia's menus, top bar and wallpaper. Back returns focus to that entry.
The existing Settings → Appearance → Theme path remains available.

Cross-app theme synchronization is not implemented. BOOMAIR reports
`mNightModeLocked=true`; Android 11's UiModeManager requires the privileged
`MODIFY_DAY_NIGHT_MODE` permission in this state. No new privileged controller,
permission grant, keyboard installation or system-mode change was made.
Apps also have their own limits: Jellyfin TV 0.20.0 offers Dark, Emerald and
Muted Purple themes, while Material Files 1.7.5 has night-mode and color
preferences. Exact shared palettes require app-specific support or source changes.
LeanKeyboardF is the proposed TV keyboard candidate: remote navigation plus
Light/System themes, with dynamic color restricted to Android 12+.

WireGuard 1.0.20260315's compatible derivative (`local.minimedia.sdmcw`) and
Material Files 1.7.5 are installed. Stock WireGuard is disabled with data retained.
The WireGuard
configuration was copied to `/sdcard/Download/wireguard-peer.conf` with the
owner's explicit approval and successfully imported. The owner confirmed the VPN
works after applying the Projector peer to OpenWrt's running `wg0` interface and
adding an IoT-zone UDP 51820 input rule. Material Files' repeating permission
prompt and empty Downloads view were resolved with Android's documented
`appops set --uid me.zhanghai.android.files MANAGE_EXTERNAL_STORAGE allow`.
The temporary VPN configuration export was removed from the projector after
successful import. `caddy-root.crt` remains in Download and is installed as
trusted. Tailscale is disabled; its saved data is retained. Opening WireGuard
restored the saved tunnel and the log confirmed a fresh handshake response after
the debloat pass.

The original exported VPN profile contained default IPv4/IPv6 routes and broke
ordinary internet access while enabled. A corrected export was transferred and
re-imported with only `192.0.2.0/24, 198.51.100.0/24` in AllowedIPs, matching the
desktop's home-network routes. The owner confirmed existing YouTube/SmartTube
works with that tunnel enabled. Home DNS `192.0.2.1` remains configured;
Android WireGuard applies it globally, unlike the desktop's domain-specific DNS.
The original export on the computer is unchanged. Router-side access restrictions
are separate from these client routes.

A custom Cobalt-based YouTube prototype has been built, verified, and installed
as `local.minimedia.youtube`. With VPN routing corrected, YouTube now loads and
the runtime log confirms `Local policy injection: "installed-local-policy-v1"`.
Live playback, ad removal, and feed filtering still require owner validation. See
[the YouTube implementation](docs/youtube.md). Retained apps are accessible
under Settings → All apps. The debloat pass disabled 28 packages; 15 targeted
Freeview packages were already disabled. Those original 43 targets are disabled;
stock WireGuard was subsequently added to the plan after the compatibility migration, and
all six required apps remain installed and enabled.

## Default Home and reversible debloat

The subsequent [focused privacy pass](docs/privacy.md) disables three unused
Google setup/data-saver packages, revokes the requested YouTube/keyboard
microphone permissions, disables always-on BLE scans/the crash-report action,
and switches ADB to USB-only. Its separate recovery record preserves the prior
states. A reboot test subsequently showed the firmware reopens TCP ADB on startup;
USB-only mode is currently session-scoped. Core and vendor hardware services remain enabled.

`python3 scripts/finalize-device.py` prints the explicit package plan without
accessing or changing the device. `--apply` targets the explicitly configured
BOOMAIR, foreground Android user 0. It verifies the six required apps,
records prior Home/package enabled states under `private/device-changes/`, sets
and verifies MiniMedia as Home, and disables the listed unwanted packages for
user 0. It does not erase app data or remove system APKs. Unknown packages and
core OS/Google, Play Store, keyboard, accessibility, network, remote, picture,
audio, HDMI and update components are retained. Google TV is disabled only after
the replacement Home is verified, except for the recorded BOOMAIR priority
workaround described below. The script reports failures and prints its
record-specific `--restore` command; restore replays exact prior enabled states
and the old Home. Never share device records without reviewing them.

The pass completed on November 19, 2026 with 28 newly disabled packages and no
failures. Recovery record:
`private/device-changes/20261119T224746535862Z.json`.
Full shell access now permits direct ADB operation. Jellyfin, Moonlight, custom
YouTube and projector Settings launches succeeded after debloating. WireGuard
received a fresh handshake response. No network downloads or root are required.

This BOOMAIR saves MiniMedia as ROLE_HOME holder and preferred activity, but
resolves higher-priority Google TV/setup activities first. The script verifies
an explicit MiniMedia launch, records package states, disables Google TV, and
then disables the completed Google TV setup package if its recovery activity
wins Home resolution. Android 11 forbids shell changes to individual components
on non-test packages, so package-level disabled-user state is used instead.
The OEM projector Settings, Bluetooth pairing services, drivers and HDMI services
remain enabled. Both implicit Home resolution and actual launch must reach
MiniMedia before the remaining package pass runs. Rollback attempts every changed
package even if one restoration fails, records failures, and restores the old
Home role. Seven local finalization checks cover preflight, priority handling,
failed-Home rollback, legacy component-state parsing, failure recording and
exact-state recovery.

Restore from any directory:

```bash
nix-shell -p python3 --run 'python3 ~/Projects/MiniMedia/scripts/finalize-device.py --restore ~/Projects/MiniMedia/private/device-changes/20261119T224746535862Z.json'
```

## Certificate installation on this firmware

The installed Android 11 CertInstaller hardcodes `com.android.settings` as the
only accepted calling package for CA installation; this firmware instead ships
`com.android.tv.settings`. Its CA picker opens but the install is then rejected.
`cert-helper/` is a temporary compatibility entry using the otherwise missing
`com.android.settings` package name, clearly labeled MiniMedia CA setup. It has
no permissions, networking, service or certificate payload. It launches the
unmodified installer, retaining its CA warning and manual approval. This bypasses
the caller-name restriction and is only to be installed with the owner's explicit
approval after verifying the expected package is absent. The owner approved
this mechanism. Remove the helper after successful import; do not leave it
installed as an alternate Settings app. `scripts/build-cert-helper.py` builds and
signature-verifies the helper with the local signing identity.

The installer returned success. A read-only AndroidCAStore check in the temporary
helper verified the exact Caddy SHA-256 fingerprint, and the helper was then
removed from user 0. No system certificate files or TLS verification settings
were changed.

Verify your own Caddy root's SHA-256 fingerprint before trusting it; the owner's
exact certificate identifier is retained in ignored local context.
Jellyfin Android TV 0.20.0 opts into the user CA store in its network-security
configuration. Verify an actual homelab HTTPS connection after import; other
apps choose their own trust policy. Do not disable TLS verification.

## Download and build

Run the download step in a terminal with Internet access:

```bash
nix-shell -p python3 --run 'python3 scripts/fetch-tools.py'
```

The script downloads Google's Android SDK platform 30 and build tools 35.0.0,
checks the sizes and checksums in Google's HTTPS repository metadata, and records
that metadata. It also downloads the official WireGuard Android APK and a
SHA-256-pinned TizenTube Cobalt 2.0.3 ARMv7 APK as an input for inspection and
customization. No downloaded app is automatically installed or launched.

With Java 17 or 21 installed:

```bash
nix-shell -p python3 jdk17 --run 'python3 scripts/build.py'
```

The build uses aapt2, javac, D8, zipalign and apksigner directly. No Gradle plugins
or Maven dependencies are required. On NixOS the Google Linux binaries run with
the system's dynamic loader and available runtime libraries, without changing
the downloaded binaries. The first build creates a local signing identity under
`private/signing/`. Preserve that directory in private backups for future updates;
do not share or commit it. Successful builds produce `dist/minimedia-home.apk`
and a source/input hash report. A previous successful APK is retained.

## Preview on the projector

Install alongside the existing launcher first:

```bash
adb -s "$MINIMEDIA_SERIAL" install -r dist/minimedia-home.apk
adb -s "$MINIMEDIA_SERIAL" shell am start -n local.minimedia.home/.HomeActivity
```

Verify the D-pad, primary app launch buttons, All apps, Settings, return from an
app, sleep/wake, and readable focus before selecting it as Home. Home setup opens
Android's Home selector when the firmware provides one. The stock launcher APK and data are retained, but it is currently disabled.
Setting the Home role alone does not override this firmware's priorities; use
the finalization script for activation. The ordinary role-selection command is:

```bash
adb -s "$MINIMEDIA_SERIAL" shell cmd package set-home-activity --user 0 local.minimedia.home/.HomeActivity
```

Recovery, using the original focused Home component observed on this unit:

```bash
adb -s "$MINIMEDIA_SERIAL" shell pm default-state --user 0 com.google.android.apps.tv.launcherx
adb -s "$MINIMEDIA_SERIAL" shell cmd package set-home-activity --user 0 com.google.android.apps.tv.launcherx/.home.HomeActivity
adb -s "$MINIMEDIA_SERIAL" shell am start -a android.intent.action.MAIN -c android.intent.category.HOME
```

The recovery-record restore command above also restores the setup package and
all other changed package states. The two-line Home recovery is a quick fallback.

## VPN and YouTube

The intended VPN is standalone WireGuard. Never put its private key or
configuration in Git or chat. Tailscale is disabled and its saved configuration
is retained for recovery.

YouTube TV uses a Cobalt runtime. The Instagram Java patch does not transfer
directly. The custom prototype uses TizenTube Cobalt as its base and bundles a
local page policy. Preserve the original Google TV APK splits in `private/original/`
for local analysis; those proprietary inputs are not distributable project assets.

The Caddy CA is installed and its exact fingerprint was verified in AndroidCAStore.
Projector hardware services, remote controls, audio, focus/keystone, HDMI, updates,
and Google core services remain enabled. The temporary WireGuard export was
removed only from the projector; the computer's original is untouched.

## Deferred content rows

The owner chose the app panel first, with content rows deferred. No carousel,
new account login, TV-listings permission or network access was added to Home.
Candidate rows are Jellyfin Continue watching/Next up and recent uploads from
YouTube subscriptions; richer library recommendations need a separate choice.

Jellyfin Android TV 0.20.0 publishes preview channels and Watch Next programs
through [LeanbackChannelWorker](https://github.com/jellyfin/jellyfin-androidtv/blob/v0.20.0/app/src/main/java/org/jellyfin/androidtv/integration/LeanbackChannelWorker.kt).
It uses a content image provider and item-specific launch intents. A future
launcher integration should first inspect these published rows using the proper
TV-listings permission, filtering strictly to Jellyfin. A shell query returning
no rows is not proof that the integration has no data; shell permissions differ.
This path could avoid an additional Jellyfin login. If direct server access is
needed, [Quick Connect](https://jellyfin.org/docs/general/server/quick-connect/)
lets the owner approve it from an existing signed-in client.

The official YouTube API requires OAuth authorization for
[the signed-in user's subscriptions](https://developers.google.com/youtube/data/guides/implementation/subscriptions).
The custom YouTube app and Home are separate Android identities; Home must not
silently obtain another app's private login data. Subscription authorization and
the chosen data-sharing design remain to be decided before implementation.
