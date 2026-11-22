# Hooks and custom commands

> Starter note. Replace with your own words from the course.

## Custom slash commands
A markdown file in `.claude/commands/` becomes a slash command. The filename is the command name,
and `$ARGUMENTS` in the file is replaced by whatever you type after the command.

## Hooks
Hooks are shell commands that run automatically at points in Claude Code's lifecycle, such as
before or after a tool runs, or when a session stops. Use them for deterministic things like
formatting files, running tests, or blocking edits to protected paths. Configure them in
`.claude/settings.json`.

## Subagents
Subagents are specialized assistants defined in `.claude/agents/`. Each runs with its own context
and instructions, which keeps the main conversation focused.
