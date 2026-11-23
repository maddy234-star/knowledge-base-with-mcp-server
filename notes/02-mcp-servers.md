---
topic: mcp
tags: [mcp, stdio, tools]
source: Claude Code in Action course
date: 2026-10-10
---
# MCP servers

> Starter note. Replace with your own words from the course.

MCP (Model Context Protocol) is an open standard for connecting AI tools to external data and
actions. An MCP server exposes tools, and Claude Code acts as the client that calls them.

## Registering a server
Use `claude mcp add <name> -- <command>` to register a local stdio server, or commit a `.mcp.json`
file at the repo root to share the configuration with the project. Run /mcp inside Claude Code to
check connection status.

## Transports
Local servers usually use stdio. Remote servers use HTTP. A stdio server must never print to
standard output, because that stream carries the protocol messages. Log to stderr instead.

## Tool design
Give each tool a clear name and a descriptive docstring, since Claude reads the description to
decide when to call it. Keep tools small and single-purpose.
