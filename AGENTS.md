# MiniMedia agent context

For owner-specific device, theme, network, recovery or history work, read
`private/OWNER-CONTEXT.md` when it exists. Its absence is normal in public clones;
use the documented local setup instead.

The complete pre-public Git history is preserved locally in
`private/history/pre-public-history.bundle`. Inspect it in a temporary clone when
personal history is needed. Keep that bundle, its refs and owner context local;
push only the sanitized public branch. Ignore rules exclude files, not Git refs.

Use `docs/architecture.md` for module responsibilities and validation commands.
Keep actual serials, network details and credentials in ignored owner storage;
tracked examples and tests use synthetic values.

## Agent skills

### Issue tracker

For issues and specs, use GitHub Issues in `AldogPlays/MiniMedia`.
Read `docs/agents/issue-tracker.md` before tracker operations.

### Triage labels

Before triaging or changing triage labels, read
`docs/agents/triage-labels.md` for the five canonical roles.

### Domain docs

This repo uses a single-context glossary and ADR layout.
Before exploring domain concepts or decisions, read `docs/agents/domain.md`.
