# Third-party notices

The root MIT license covers original MiniMedia source and documentation.
Third-party material retains its own terms.

## Bundled font

`app/assets/MonaspaceNeon-Regular.otf` is Monaspace Neon, copyright GitHub,
licensed under the SIL Open Font License 1.1. Its complete notice and license
are included in `app/assets/Monaspace-LICENSE.txt` and packaged with Home.
The font is not relicensed under MIT.

Upstream: https://github.com/githubnext/monaspace

## Locally acquired build inputs

Android SDK tools, platform files, Apktool, upstream WireGuard and TizenTube Cobalt
APKs, private wallpapers and locally generated derivatives are not distributed
by this source repository. Their own licenses and any source-distribution
requirements remain applicable when acquiring, building or distributing them.
The root MIT license does not grant rights to those inputs or outputs.

- Android SDK: https://developer.android.com/studio
- Apktool: https://github.com/iBotPeaches/Apktool
- WireGuard Android: https://github.com/WireGuard/wireguard-android
- TizenTube Cobalt: https://github.com/reisxd/TizenTubeCobalt

The Cobalt/Chromium declarations in `youtube/stubs` are minimal compile-only
bridge declarations. They are excluded from generated APKs. Derivative build
checks and preservation of upstream license resources are described in
`docs/youtube.md` and `docs/wireguard-compat.md`.
