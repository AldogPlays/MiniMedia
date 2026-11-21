# Local owner setup and public history

The public repository starts with a sanitized source snapshot. Earlier personal
Git history, device identifiers and actual network details remain local.

## Select a device

Provide the exact ADB serial before using device commands:

```sh
export MINIMEDIA_SERIAL='your-adb-device-serial'
```

Alternatively, create an ignored `private/device.json`:

```json
{"serial": "your-adb-device-serial"}
```

The environment override takes precedence over the local file. An empty override
disables device access even when the file exists. Without a configured serial,
the scripts can print their plans but reject device commands. Model and user-0
checks remain in place. The operational command examples use the environment
variable; export it even if Python scripts normally use your local file.

Network addresses in public documentation are illustrative. Use your own routes
and DNS values rather than copying those examples into a VPN profile.

## Personal context for agents

The owner's checkout can include `private/OWNER-CONTEXT.md`, containing local
preferences, device and network context, recovery notes and archive instructions.
The tracked `AGENTS.md` directs agents there for owner-specific work. Public
clones normally do not contain this file.

The owner's verified original Git bundle is stored at
`private/history/pre-public-history.bundle`; a tracked-source snapshot is stored
alongside it. Inspect the original history separately:

```sh
git bundle verify private/history/pre-public-history.bundle
git clone private/history/pre-public-history.bundle /tmp/minimedia-original-history
```

Keep those original refs in the temporary clone. The public checkout's branch
contains only sanitized history. Push that branch explicitly, rather than
publishing original refs with an all-refs or mirror push. `.gitignore` covers the
archive and context files, but cannot hide commits added to a pushed branch.

Private context and signing material require separate local backups; GitHub's
public repository is not their backup.
