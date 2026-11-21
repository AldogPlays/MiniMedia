# Architecture workflow reconciliation

## Workflow record

The user accepted all three recommendations from the architecture review. The
implementation was then completed before invoking `to-spec` and `implement`.
Tests were added after the implementation. The earlier claim of completion
therefore described code and validation, not completion of those skill workflows.

Reconciliation uses [the local spec](specs/architecture-deepening.md), synthesized
from the accepted review and conversation. The user explicitly confirmed all
three testing seams and original local baseline (archived privately). New regression fixes must follow
red → green at those seams. The earlier implementation remains implementation-first.

## Requirement mapping

| Accepted recommendation | Implementation | Existing evidence | Remaining reconciliation |
| --- | --- | --- | --- |
| Verified APK production | `scripts/apk_build.py`; all five build callers | Production and publication tests; scratch Home, certificate-helper and pressure builds; real 16 KiB alignment check | No finding in initial independent reviews |
| BOOMAIR device module | `scripts/boomair_device.py`; finalization and privacy callers | Real parsing behind simulated ADB; journal failure and restore tests; complete privacy apply/rollback checks | No finding in initial independent reviews |
| Launcher interaction | `LauncherInteraction.java`; host adapter in `HomeActivity.java` | Nine event-sequence scenarios; activity compilation against local SDK | Keyboard/focus ordering regression fixed using red → green |
| Shared domain language | `GLOSSARY.md`; `docs/architecture.md` | Terms and module responsibilities documented | No finding in initial independent reviews |

## Known workflow gaps

- **Original tracker publication:** no remote, issue tracker or triage vocabulary
  was configured during architecture reconciliation, so its spec remained local.
  The later public-source release configures GitHub as the tracker and publishes
  its own release spec. This preserves the historical workflow record.
- **Original TDD:** no historical red-first evidence exists for the completed
  extraction. New tests alone cannot change that history.
- **Review:** independent standards and spec reviews ran against the confirmed
  baseline, including untracked files. Standards found no violations or
  meaningful new smells. Spec found one keyboard/focus ordering regression;
  final independent reviews confirmed its fix and found no unresolved Standards
  or Spec defects.
- **Commit:** `implement` requires a commit to the current branch after review
  and checks. This reconciliation is included with the reviewed implementation
  in that commit; use Git history to identify it.

## Validation already performed

Before reconciliation, all 50 Python-suite tests and six JavaScript response-policy
checks passed. The Python suite includes the Java interaction harness and adapter
compilation. Scratch builds used temporary signing identities; production signing
material and device configuration were not modified. No physical-device runtime
validation was performed.

## Regression fix and final checks

The extracted launcher hid controls by closing the menu before asking its Android
host to dismiss the keyboard. The baseline dismissed the keyboard first, before
menu-close focus restoration. The spec review independently identified this
ordering regression.

At the confirmed launcher interaction seam, a new effect-sequence test first
failed with a Java assertion on the existing implementation. The test harness
was updated to display Java assertion diagnostics. The minimal fix made keyboard
dismissal an explicit host effect before menu closure and removed the later
duplicate dismissal from rendering. All ten launcher tests, including Android
adapter compilation, then passed.

The final full suite passed 51 tests, and all six JavaScript response-policy
checks passed. `git diff --check` passed. No device mutation or installation was
performed during reconciliation.
