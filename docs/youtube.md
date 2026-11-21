# Custom TV YouTube build

Requested behavior:

- Search, subscriptions, and watch history remain available.
- Hide Shorts and recommendation feeds.
- Remove video advertising and promotional placements.
- Use TV remote controls and the native TV playback runtime.
- Preserve normal certificate validation. HTTPS certificate provisioning is deferred.

## Prototype implementation

Use the ARMv7 TizenTube Cobalt 2.0.3 runtime as the candidate base. Its release
SHA-256 is pinned in the download script. Upstream already supports ad blocking
and SponsorBlock in a Cobalt runtime. This is an independent TV app, not the
Google-signed stock YouTube app. Do not describe a repack of this app as an
original streaming engine or as a successfully patched stock YouTube APK.

`scripts/build-youtube.py` checks the complete upstream APK and native library
hashes, checks the original bridge class/method declarations with dexdump, and
adds `CustomActivity` in a separate DEX file. The original three DEX files remain
byte-for-byte unchanged; compile-only bridge stubs are excluded from the APK.
The manifest assigns the independent package `local.minimedia.youtube`, routes
its launcher to the subclass, disables debuggability, and removes location,
camera, ad ID, package-inventory, installer, account and storage permissions.

Two exact, hash-guarded string-literal replacements in the native library disable
the upstream remote JavaScript loader and its availability check. The library's
size and all bytes outside those literal ranges are preserved. A local policy
asset is injected through the existing Cobalt JavaScript bridge while the app
is visible. The subclass stops its callbacks when paused; it adds no Android
background service. It does not disable certificate checks or browser sandboxing.

The prototype filters known ad and Shorts renderer/response fields, removes
known unwanted guide endpoints and watch-next recommendations, rewrites Home
browse requests to subscriptions, and uses a limited DOM fallback for the TV
guide. SponsorBlock queries contain a public video ID with credentials omitted
and skip only the `sponsor` category. No remote executable script is loaded by
the custom policy. Actual DOM/schema compatibility and live ad removal remain
unverified; the response checks are not proof of either.

Build with `python3 scripts/build-youtube.py` after the normal tool-download and
launcher-signing setup. The signed result and input/source hash report are under
`dist/`. Preserve the local signing key for updates. The prototype was installed
on the BOOMAIR. Initial navigation failed with `net::ERR_CONNECTION_REFUSED`
while the original full-tunnel VPN profile blocked ordinary internet traffic.
After the owner re-imported a split-tunnel profile and confirmed existing
YouTube/SmartTube worked, Cobalt successfully navigated to YouTube. The log at
13:35:07 on November 19 confirms the local page policy returned
`installed-local-policy-v1`. This proves startup and injection, not ad removal.
Playback, navigation and filtering still require device testing.

The existing Instagram patch is useful as a build/provenance model; its bytecode
fingerprints and x86-64 inputs do not apply to this app. Cobalt bridge signatures
and page structures must be inspected and matched rather than guessed. Fail the
patch on an unsupported or ambiguous input.

## Required validation

Before calling the custom build working, verify its signature, package identity,
ARMv7 native libraries, injected asset, exact changed methods and permissions.
On the projector, test a cold launch, D-pad navigation, search, subscriptions,
history, video start and seek, an ad-eligible video, sponsor skipping, Back,
sleep/wake and return from another app. Check that hidden recommendations and
Shorts stay absent after navigation/reload. Never claim all future advertising
is prevented: YouTube's server responses can change.

Nine Python checks cover download/manifest guards and the native-literal patch
boundary. Six JavaScript fixture checks cover response filtering, retained
playback fields, guide entries and Home-request rewriting. These tests do not
establish working playback, complete recommendation removal or stable ad blocking.

## Sources

- [TizenTube Cobalt](https://github.com/reisxd/TizenTubeCobalt)
- [Pinned ARMv7 release](https://github.com/reisxd/TizenTubeCobalt/releases/tag/v2.0.3)
- [Morphe TV support discussion](https://github.com/MorpheApp/morphe-patches/issues/150)

The prototype home preview uses illustrative clock and VPN values, not live
device state. `HomeActivity` reads actual connection state when running.
