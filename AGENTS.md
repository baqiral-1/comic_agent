## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file.

### Available skills
- commit-message-format: Format or rewrite Git commit messages as one concise summary line followed by bullet points. Use when creating new commits, amending commit messages, or standardizing commit history style. (file: /Users/baqir/Python/comic_agent/skills/commit-message-format/SKILL.md)

### How to use skills
- Discovery: Use the list above to find skills available in this repository.
- Trigger rules: If a user names a skill or the task matches a skill description, use that skill for the turn.
- Missing/blocked: If a skill file cannot be read, continue with the best fallback.
- Progressive disclosure: Read only the `SKILL.md` and any directly-needed files under that skill.
