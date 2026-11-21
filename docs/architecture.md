# Architecture

MiniMedia keeps its dependency-free Android build and device-specific workflows.
Three modules concentrate behavior that previously depended on ordering rules
spread across callers.

## Verified APK production

`scripts/apk_build.py` owns local tool discovery, signing identity handling,
alignment, signing, signature/alignment verification and staged publication.
The five `build*.py` entry points retain their packaging and transformation rules.
Only the Home build can create an initial signing identity; existing identity
fragments or a previous Home output prevent automatic replacement of a lost key.

`finish_apk` returns a staged APK after both verification checks pass. Callers
supply the intended minimum SDK and alignment policy: Home and YouTube verify
against 26, WireGuard against 24, and the derivative builds use 16 KiB native
alignment. The CA helper retains legacy native page alignment. Both helper builds
now check alignment after signing as well as checking the signature.

`publish_apk` prepares the optional report before replacing output, preserves the
existing previous-APK convention, and restores replaced files if a replacement
raises an operating-system error. The APK and report are separate filesystem
replacements; they are not a crash-atomic pair. Publication does not install an APK.

## BOOMAIR device behavior

`scripts/boomair_device.py` owns the serial-scoped ADB adapter, user-0 state
interpretation, physical-device checks, reconnection, verification and recovery
record writing. Privacy imports this module directly rather than importing the
finalization entry point.

A journaled package disable persists intent before the command and checks the
resulting package state. Record writes flush contents and the containing directory
before returning. Failed staging files are removed. Existing finalization and
privacy record fields remain readable by their respective restore commands.

The serial comes from `MINIMEDIA_SERIAL` or ignored `private/device.json`; an
unconfigured or invalid serial is rejected before ADB executes. See
[local setup](local-setup.md) for owner context and archived personal history.

The workflow callers retain their package allowlists and failure policies:
finalization records individual package failures and continues; privacy attempts
rollback. Home-priority recovery remains part of finalization. The shared module
does not turn these policies into a general transaction framework.

## Launcher interaction

`LauncherInteraction.java` owns reveal-gesture consumption, controls visibility,
menu paths and remembered positions, Back precedence and idle eligibility across
resume/pause. Its host adapter in `HomeActivity.java` handles Android views,
keyboard effects, timers and focus requests. Rendering, wallpaper decoding,
network observation and app discovery remain in the activity.

The first navigation gesture reveals the controls and consumes its repeats and
release. Back traverses menus before clearing a query and hiding controls. Pause
hides controls and clears reveal gestures; resume leaves controls hidden. A hidden
or paused launcher and the Never timeout do not schedule an idle deadline.

## Validation

From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node tests/test_youtube_policy.cjs
```

The Python suite includes a Java interaction harness, requiring a JDK discoverable
through `JAVA_HOME`, `PATH` or the local Nix store. It also compiles the activity
adapter when the local Android SDK is available. Tests substitute tool execution
or raw ADB responses, preserving production sequencing, parsing and verification.
All generated test files live in temporary directories.

Local tests do not establish physical remote feel, keyboard behavior, focus
rendering, live YouTube playback or unattended VPN reliability. Those retain their
existing device validation requirements.
