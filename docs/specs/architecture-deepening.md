# MiniMedia architecture deepening

## Problem Statement

Maintaining MiniMedia requires remembering repeated APK production rules, device
state parsing and recovery rules, and launcher interaction rules spread across
callers and callbacks. This makes changes harder to verify while preserving the
working BOOMAIR configuration and remote-control behavior.

## Solution

Concentrate verified APK production, BOOMAIR device behavior and launcher
interaction in three deep modules. Preserve the existing build commands,
artifact names, signing identity, device scope, recovery records and launcher
behavior. Verify each module through the interfaces used by its callers.

## User Stories

1. As a maintainer, I want all five APK builds to share production rules, so that
   signing and verification changes apply consistently.
2. As a device owner, I want builds to retain my signing identity, so that locally
   built applications remain compatible with installed updates.
3. As a maintainer, I want only the Home build to bootstrap an identity, so that a
   derivative build cannot silently create a replacement identity.
4. As a device owner, I want incomplete identity files or an existing Home APK to
   prevent replacement-key generation, so that a lost identity requires recovery.
5. As a maintainer, I want the builds to retain their minimum Android versions, so
   that shared production does not change compatibility requirements.
6. As a maintainer, I want native alignment requirements to remain explicit, so
   that derivative APKs retain their intended alignment.
7. As a maintainer, I want signature and alignment checks to finish before
   publication, so that a failed build does not replace a working APK.
8. As a maintainer, I want reports prepared before output replacement, so that
   report serialization failure preserves previous output.
9. As a maintainer, I want recoverable publication failures to restore previous
   output, so that an APK and its report remain consistent after handled failures.
10. As a maintainer, I want existing previous-APK conventions preserved, so that
    the existing fallback artifacts remain available.
11. As a maintainer, I want product-specific packaging and transformations to stay
    with their respective builds, so that shared production does not weaken
    bounded derivative checks.
12. As a maintainer, I want shared BOOMAIR transport and state interpretation, so
    that privacy does not import the finalization workflow for basic device work.
13. As a device owner, I want device commands scoped to the expected serial,
    model and foreground user, so that these passes retain their existing scope.
14. As a device owner, I want state parsing to read user 0, so that another user's
    package or microphone state cannot influence my configuration pass.
15. As a device owner, I want package-disable intent saved before mutation, so
    that attempted changes remain recoverable even if verification fails.
16. As a device owner, I want resulting package states verified, so that a denied
    command is not reported as a successful change.
17. As a device owner, I want prior package states restored exactly, so that
    restoration preserves default, enabled and disabled distinctions.
18. As a device owner, I want existing recovery records to remain usable, so that
    this refactor does not invalidate earlier recovery instructions.
19. As a device owner, I want finalization to retain its Home-priority workaround
    and per-package failure reporting, so that existing BOOMAIR behavior survives.
20. As a device owner, I want privacy to retain rollback on failure, so that it
    remains distinct from finalization's continuation policy.
21. As a device owner, I want interrupted ADB restarts to reconnect and verify
    the resulting mode, so that an interrupted response is not mistaken for the
    final device state.
22. As a remote user, I want the first navigation gesture to reveal controls
    without activating an entry, so that opening the launcher is predictable.
23. As a remote user, I want repeats and release of that reveal gesture consumed,
    so that a held key does not accidentally activate an entry.
24. As a touch user, I want the whole reveal gesture consumed, so that revealing
    controls does not activate a newly visible entry.
25. As a remote user, I want Back to traverse menus before clearing a query and
    hiding controls, so that existing navigation precedence is preserved.
26. As a remote user, I want menu positions and entry-specific return focus
    preserved, so that returning from Settings or Theme Selector is predictable.
27. As a keyboard user, I want printable Unicode input to reveal controls and
    enter search while respecting modifiers, focused search and open menus, so
    that local search continues to work.
28. As a device owner, I want pause to hide controls and clear reveal gestures,
    so that returning from another application starts with the wallpaper.
29. As a device owner, I want idle eligibility to follow visibility, lifecycle
    state and the Never preference, so that hidden or paused controls do not
    schedule an idle deadline.
30. As a maintainer, I want tests to exercise these behaviors through the caller
    interfaces, so that implementation changes do not require rewriting tests.
31. As a maintainer, I want documented module responsibilities and terminology,
    so that future changes concentrate knowledge in the appropriate module.

## Implementation Decisions

- The verified APK production module owns local tool discovery, signing identity
  handling, alignment, signing, verification and staged output publication.
- Home and YouTube verify against Android SDK 26; WireGuard verifies against 24.
  YouTube and WireGuard retain 16 KiB native alignment, and the certificate helper
  retains its legacy native page-alignment policy.
- All five builds use the shared production implementation. The certificate
  helper and pressure-test builds gain post-sign alignment verification.
- Reports retain their existing fields and names. APK/report replacement is not
  crash-atomic as a pair; handled write failures attempt restoration of replaced
  files. No guarantee extends to an unrecoverable filesystem failure.
- The BOOMAIR device module owns serial-scoped transport, user-0 interpretation,
  device identity checks, reconnection, verified package changes and recovery
  record writing. Workflow allowlists and failure policies remain with callers.
- Shared journaled package changes support the two existing attempt-list names;
  there is no recovery schema migration or general transaction framework.
- Recovery records are staged privately, flushed before replacement and cleaned
  up after failed staging. Package mutation follows successful intent persistence.
- The launcher interaction module owns gesture consumption, controls visibility,
  menu paths, remembered positions, Back precedence and idle eligibility.
- The Android host adapter retains rendering, keyboard effects, scheduling and
  focus effects. Rendering, wallpaper decoding, app discovery and VPN observation
  otherwise retain their existing behavior.
- Keyboard dismissal and focus effects retain their existing ordering when
  controls hide. After pause, resume does not reveal controls automatically.
- Build and device entry-point commands retain their existing opt-in mutation
  behavior. Reconciliation does not install applications or apply device passes.

## Testing Decisions

The user confirmed the following three testing seams during reconciliation:

1. **Verified APK production interface:** exercise production and publication
   with temporary artifacts and a recording/failing tool adapter. Verify output
   preservation, compatibility settings, alignment and signing failures. This
   catches production ordering and publication mistakes; it does not establish
   application runtime correctness.
2. **BOOMAIR device operations and workflow interfaces:** supply simulated raw
   ADB responses while retaining real parsing, journaling and verification. Test
   user isolation, durable intent before mutation, exact restoration, reconnect
   verification and the two distinct workflow failure policies. This catches
   command interpretation and orchestration errors; it does not establish
   firmware behavior or physical connectivity.
3. **Launcher interaction interface through the host adapter:** send input and
   lifecycle sequences and observe visibility, consumption, menu paths, focus
   intent and idle eligibility. This catches transition mistakes; it does not
   establish physical focus rendering, keyboard behavior or remote feel.

Prefer observable results over private-method tests or assertions tied to
temporary implementation names. Existing manifest transformation, recovery and
JavaScript response-policy tests provide prior art. Retain distinct behavioral
coverage; replace lower-level tests only when the same guarantees are exercised
through a higher confirmed seam.

Compile the Android adapter when local SDK inputs are available. Use scratch
builds with temporary signing identities to exercise real Android tools without
replacing production artifacts. For new fixes, write and run one failing test,
make the minimal implementation change, and rerun that test before continuing.
Run the full suite once the reconciliation changes are complete.

## Out of Scope

- Device installation, configuration changes, rebooting or publishing releases.
- New launcher features, permissions, network access or background execution.
- Changes to derivative payload transformations or VPN behavior.
- New signing identities for existing installations or recovery-record migration.
- A general build framework or general device transaction framework.
- Claims of physical-device validation, live playback, ad removal or unattended
  VPN reliability based solely on local tests.

## Further Notes

- This spec reconciles already implemented work with the accepted architecture
  review. The original implementation was not spec-first or test-first; this
  document does not retroactively claim either workflow occurred.
- The three testing seams and review original local baseline (archived privately) were explicitly confirmed
  by the user during reconciliation.
- The checkout has no Git remote or issue-tracker/triage configuration. This is
  the local spec until tracker setup permits publication with `ready-for-agent`.
- The required review compares the uncommitted worktree, including new files,
  against the confirmed baseline. A three-dot comparison to HEAD alone would
  omit this work because HEAD remains the baseline.
