# Claude Code in Action — Field Notes

## Long Sessions & Workflow Habits
* **Scope first, steer second** — Don't let it run blind on a massive vague prompt.
* **Direct compaction** — Tell it what to keep in the summary so you don't lose critical context.
* **Rewind menu** — Use it to course-correct immediately when Claude starts drifting.
* **Goal-oriented prompting** — When you can define "done" better than the exact steps, just give it the end-state goal.
* **Parallelize with worktrees** — Run separate tasks in git worktrees so they don't step on each other.

---

## Where Rules Live (Instruction Surfaces)

| Surface | Use When... | Enforcement |
| :--- | :--- | :--- |
| **`CLAUDE.md`** | Global conventions that apply 100% of the time (naming, folder structure). | Soft (LLM follows instructions) |
| **Skills** | Task-specific workflows, procedures, and reference docs. | Soft (LLM follows instructions) |
| **Hooks** | Hard guardrails Claude **cannot** be allowed to skip. | **Hard** (Deterministic code execution) |

---

## Hooks Cheat Sheet
* **`PreToolUse`** — Runs before a tool executes. Your main enforcement gate to block or rewrite calls.
* **`PostToolUse`** — Runs after a tool succeeds. Good for auto-linting or formatting.
* **`Stop` / `SubagentStop`** — Fires when Claude (or a subagent) tries to finish its turn. Can reject the stop and force it to keep going if exit criteria aren't met.
* **`InstructionsLoaded`** — Fires when `CLAUDE.md` or rule files load. Use to debug/audit what's actually in context.
* **`SessionStart`** — Fires at session init to prime the env (use `startup` source for fresh starts only).
* **`PreCompact` / `PostCompact`** — Fires around context compaction. 
  * *Gotcha:* Don't use `PostCompact` to re-inject context. Use `SessionStart` with the `compact` matcher—that's what actually feeds stdout back into the conversation.

### `PreToolUse` JSON Decision Payload
Print JSON to `stdout` and exit `0` to control execution:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny", 
    "permissionDecisionReason": "Explain why here",
    "updatedInput": {
      "command": "sanitized_command_here"
    }
  }
}
```

* **`permissionDecision` options:** `allow`, `deny`, `ask` (prompts user), or `defer` (rare; pauses non-interactive `-p` runs for external resume).
* **`updatedInput` gotcha:** Overwrites the *entire* input object. Always echo back unchanged fields or they'll get wiped (useful for redacting secrets from bash commands before execution).

---

## Automation & Headless Execution

### Which Tool for the Job?
* **Routines:** Default for recurring background tasks. Hosted by Anthropic, zero infra to manage.
* **Headless (`claude -p`):** Best for local scripts/pipelines where you need to pipe data in and out.
* **`--bare` flag:** Use in CI when you need deterministic, repeatable runs without extra context bloat.
* **Agent SDK:** When you're embedding agentic workflows directly inside your own product.

### Routines Setup & Gotchas
* **How to create:** Web UI (`claude.ai/code/routines`) or straight from CLI via `/schedule daily dependency audit at 9am`.
* **Preview status:** Still a research preview—expect behavior and limits to shift.
* **Rate limit:** Max frequency is **hourly**. Anything faster needs a different tool.
* **Git/Branch rules:** Clones fresh from default branch. Can push freely to `claude/*` branches, but pushes to other branches fail if protected on GitHub, someone else has an open PR on it, or it has external commits. Keep `main` locked down.

---

## Quick CLI Snippets

### Structured JSON Output (Headless)
```bash
claude -p "Extract the exported function names from src/core/style.js" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}},"required":["functions"]}' \
  | jq '.structured_output.functions'
```

### Plugins
```bash
# Install official plugin
/plugin install github@claude-plugins-official

# Add custom/org plugin marketplace
/plugin marketplace add your-org/claude-plugins
```