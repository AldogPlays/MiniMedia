# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `AldogPlays/MiniMedia`.
Use the `gh` CLI from this clone.

## Operations

- Verify the target with `gh repo view --json nameWithOwner`.
- Create: `gh issue create --title "..." --body-file <file>`.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open`, with appropriate label filters.
- Comment: `gh issue comment <number> --body-file <file>`.
- Label: `gh issue edit <number> --add-label "..."` or
  `--remove-label "..."`.
- Close: post the explanation as a comment, then close the issue.

Use native GitHub sub-issues and issue dependencies when available.
Otherwise, record `Part of #<parent>` and `Blocked by: #<number>` in
the issue body. An issue is unblocked when every blocker is closed.

When a skill says to publish to the issue tracker, create a GitHub issue.
When it says to fetch a ticket, read the corresponding GitHub issue.

## Pull requests as a triage surface

**PRs as a request surface: no.**
