# Public source release

## Problem Statement

The owner wants MiniMedia published on GitHub after verification, while retaining
personal device context and the complete original history for local agents.
The current commits contain device identifiers, internal network details and
personal commit metadata that should remain local.

## Solution

Archive the original history and owner context in ignored local storage. Publish
a sanitized source snapshot to a new private repository, verify the pushed
history and its contents, then make that repository public. Use MIT for original
MiniMedia source while retaining third-party license terms.

## User Stories

1. As the owner, I want the full original Git history archived locally, so that
   agents can recover the project as it related to my setup.
2. As the owner, I want personal context reachable from agent instructions, so
   that future agents can understand my actual device without public disclosure.
3. As the owner, I want that archive and context covered by ignore rules, so that
   ordinary commits exclude them.
4. As the owner, I want the archive verified before history changes, so that
   sanitization preserves a recoverable copy of every original commit.
5. As the owner, I want public history to omit personal identifiers and commit
   email, so that old revisions cannot undo source sanitization.
6. As the owner, I want my actual device selected from private local
   configuration, so that sanitizing public source does not break local scripts.
7. As a new user, I want explicit device configuration, so that the scripts never
   silently select an unrelated attached device.
8. As a new user, I want missing or malformed device configuration rejected
   before ADB executes, so that configuration errors cannot mutate a device.
9. As a maintainer, I want synthetic device identifiers in tests, so that tests
   do not depend on the owner's ignored configuration.
10. As a reader, I want network addresses clearly marked as illustrative, so that
    public documentation does not disclose the owner's network layout.
11. As a source recipient, I want original-source and third-party licensing
    clearly distinguished, so that bundled font terms remain intact.
12. As the owner, I want no signing keys, VPN profiles, proprietary APK inputs or
    generated build outputs published, so that the repository contains source.
13. As the owner, I want tests and all five APK build paths verified, so that
    publication follows concrete local checks.
14. As the owner, I want the first push private and rechecked remotely, so that
    visibility changes only after the published contents pass the audit.
15. As a future agent, I want normal Git pushes to include only public history,
    so that owner-specific context stays local after publication.

## Implementation Decisions

- Preserve the original reachable history in a verified Git bundle and retain
  an original tracked-source snapshot in ignored owner storage.
- Keep a concise owner-context document beside the archive. Public agent
  instructions explain when to read it and how to keep it local.
- Start public Git history from a sanitized root commit rather than copying
  existing commits and their personal metadata.
- Use the owner's GitHub no-reply identity for public commits. Preserve original
  author metadata in the ignored history bundle.
- Load the device serial from an explicit environment override or ignored local
  JSON configuration. Preserve serial-scoped transport, model and user-0 checks.
- An unconfigured checkout can print its device plan, but device commands reject
  missing or malformed serials before invoking ADB.
- Preserve the owner's current serial in ignored configuration. Public examples
  use placeholders and clearly illustrative subnet ranges.
- Add an MIT license for original source and explicit third-party notices for
  the bundled Monaspace font and locally acquired derivative build inputs.
- Exclude private material from the source snapshot, Git refs and push. An ignore
  rule protects files, not previously committed objects; only sanitized public
  refs are pushed.
- Keep the new repository private during the initial push and remote audit.
  Change visibility to public only after those checks pass.

## Testing Decisions

Use the already confirmed BOOMAIR device-operation seam for regression tests of
serial configuration and rejection before transport. Write one failing test and
the minimal implementation per cycle. Reuse existing temporary-file and raw ADB
test adapters; no new hardware-testing seam is introduced.

Run the complete suite and JavaScript checks after source changes. Compile the
Android adapter and build all five APKs in scratch directories with temporary
signing identities. Clean-source tests must pass without owner files, with
explicit skips for unavailable private inputs and SDK fixtures.

Verify the ignored bundle restores the complete original history. Scan every
publicly reachable commit and the staged source for secrets and personal markers;
verify excluded paths are absent from Git trees. Repeat the checks against the
private remote before making it public. These checks do not establish physical
remote behavior, live playback or unattended VPN reliability.

## Out of Scope

- Uploading binary releases, private build inputs, signing material or VPN data.
- Installing applications or applying configuration passes on the projector.
- Changing launcher behavior, derivative transformations or the owner's routes.
- Removing the owner's original history or personal context archive.
- Claiming open-source licensing for third-party inputs under different terms.

## Further Notes

The user selected sanitized public history with ignored local preservation of
the true history and personal context. They expressed no license preference;
MIT was the proposed default. The private GitHub repository has been created and
is empty. The original history already passed Gitleaks, but contains personal
identifiers that still require removal from the published history.
