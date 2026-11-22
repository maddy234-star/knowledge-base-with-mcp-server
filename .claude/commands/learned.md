# /learned

Record a new learning about **$ARGUMENTS** in `LEARNINGS.md`.

## Steps

1. Use the `search_notes` MCP tool to find any existing notes related to **$ARGUMENTS**.
2. If relevant notes are found, use `get_note` to read them for context.
3. Based on what you find (and what the user has told you), write a concise bullet-point summary of the key learning(s) about **$ARGUMENTS**.
4. Append the learning under the appropriate course section in `LEARNINGS.md`.
   - If a matching section already exists, add bullet points to it.
   - If no matching section exists, create a new `## <Topic>` section at the end of the file.
5. Confirm to the user what was added and which section it went into.

## Rules
- Keep each bullet short (one line ideally).
- Do not duplicate existing bullets.
- Never overwrite existing content in `LEARNINGS.md`.
