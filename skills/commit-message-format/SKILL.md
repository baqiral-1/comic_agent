---
name: commit-message-format
description: Format or rewrite Git commit messages as one concise summary line followed by up to a few bullet points. Use when creating new commits, amending commit messages, or standardizing message style across history.
---

# Commit Message Format

Use this structure:
- First line: single summary sentence in imperative mood.
- Blank line.
- `- ` bullet lines (1-5 bullets) describing key changes.
- Do not insert blank lines between bullet lines.
- Blank line.
- `Closes https://github.com/<owner>/<repo>/issues/<number>`.

Before running `git commit` or `git commit --amend`:
- Ask explicitly: "What issue number should I link in this commit message?"
- Wait for the user response.
- If the user provides only a number, convert it to the full GitHub issue URL for this repository.

Write summary guidelines:
- Keep it short and specific.
- Mention primary user-visible or architectural change.
- Avoid trailing punctuation noise and filler words.

Write bullet guidelines:
- Keep each bullet focused on one change.
- Mention touched subsystem/file area when useful.
- Skip trivial implementation detail.

Docs filtering rule:
- Ignore docs-related changes when writing commit messages.
- Do not mention docs, README, GitHub Pages, galleries, screenshots, or static assets in the summary or bullets.
- Focus message content on functional/runtime/agent/code behavior changes only.

Use this script for deterministic formatting:
- `scripts/format_commit_message.py --summary "..." --bullet "..." --bullet "..." --issue-url "https://github.com/<owner>/<repo>/issues/<number>"`

Use with Git:
- Do not use repeated `git commit -m ... -m ...` because Git separates each paragraph with a blank line.
- `git commit -F /tmp/commit-msg.txt`
- `git commit --amend -F /tmp/commit-msg.txt`
