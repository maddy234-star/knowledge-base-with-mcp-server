---
topic: claude-code
tags: [claude-code, claude-md, context]
source: Claude Code in Action course
date: 2026-10-10
---
# Claude Code basics

> Starter note. Replace with your own words from the course.

Claude Code is Anthropic's agentic coding tool that runs in your terminal. It can read files,
edit code, run commands and use tools you connect to it.

## CLAUDE.md
CLAUDE.md is a markdown file Claude Code loads into context at the start of a session. Put project
conventions, build and test commands, and architecture notes in it. Keep it short and specific,
because everything in it consumes context on every request.

## Plan mode
Plan mode lets Claude research and propose a plan before touching any files. Use it for larger
changes so you can review the approach first.

## Context management
Long sessions fill the context window. Use /clear between unrelated tasks and /compact to
summarize a long conversation when you want to keep going.
