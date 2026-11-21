# Public source verification

Verification performed on 2026-11-21 before the initial public source release.

## Code and build checks

- All 57 tests pass in the owner's configured workspace. These include Java
  launcher interaction scenarios and Android adapter compilation.
- A clean source export also passes: 57 tests discovered, five explicitly skipped
  because private APK fixtures or the local Android SDK are absent.
- All six JavaScript response-policy checks pass.
- Scratch builds of Home, the certificate helper, the VPN pressure-test app,
  YouTube and WireGuard pass signing and alignment checks with temporary keys.
  The derivative checks preserve the original YouTube DEX and verify WireGuard's
  reassembled classes against declared transformations.
- Missing and malformed serials reject device commands before transport. Tests
  use synthetic identifiers and remain collectable with malformed owner config.
- Standards and spec review found a remaining owner CA identifier and test-import
  dependence on local configuration; both were corrected. The import regression
  was reproduced before its fix.

## Publication checks

- The public snapshot excludes actual device identifiers, owner network ranges,
  the owner's CA fingerprint and personal commit email. Network examples are
  illustrative and devices require explicit local configuration.
- Signing keys, VPN profiles, downloaded APKs, wallpapers, device-change records,
  owner context and history archives remain ignored and outside the snapshot.
- Gitleaks found no secrets in the original history or the clean public source
  export. Explicit owner-marker checks supplement secret scanning.
- The public Git branch starts with a sanitized root, using a GitHub no-reply
  author identity. Only that branch is pushed; archived original refs stay local.
- The complete original history bundle was verified and restored in a temporary
  clone, matching the original tip and commit count.
- Original source uses MIT. The bundled Monaspace font retains its complete SIL
  Open Font License notice; locally acquired third-party APKs are not published.

The publication process pushes privately, rechecks the remote branch and source
contents, and changes visibility only after that audit passes.

## Limits

These checks verify local source and build behavior. They do not establish
physical remote feel, focus rendering, live playback, complete ad filtering or
long-term VPN reliability. No new APK was installed and no device configuration
pass was applied during this release preparation. This is a source publication;
locally generated APKs are not uploaded as release assets.
