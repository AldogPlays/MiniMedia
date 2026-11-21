# MiniMedia

MiniMedia is a local Android TV launcher and a set of device-specific builds and
reversible configuration passes for the BOOMAIR projector.

## Language

**Verified APK**:
A locally signed Android application package that has passed signature and
alignment checks for its intended Android version.

**Signing identity**:
The local cryptographic identity used to authorize updates to MiniMedia's
installed applications.

**Retained app**:
An application that must remain installed and enabled after either device pass.

**Finalization pass**:
The BOOMAIR configuration pass that selects MiniMedia as Home and disables the
explicitly unwanted applications while retaining their data.

**Privacy pass**:
The BOOMAIR configuration pass that applies the selected package, permission,
scanning and debugging changes and attempts restoration if verification fails.

**Recovery record**:
The saved prior device state and attempted changes needed to restore a particular
configuration pass.

**Launcher controls**:
The app list, search, top bar and nested menus revealed over the wallpaper.

**Menu path**:
The sequence of nested launcher pages from the entry page to the current page.
