# /save-discussion

Save what we discussed and did in this session so future sessions start fully up to date.

## Steps
1. Review this conversation and the current repo state (`git status`, `git log --oneline -5`).
2. Append a dated section to `discussions/LOG.md` (newest at the bottom; create today's heading if missing,
   otherwise add bullets under it). Record: what was discussed, decisions and why, what changed, problems hit.
3. Update `discussions/STATE.md` so it reflects the present: current status, decisions, open items. Remove
   items that are done. Keep it short (under ~60 lines).
4. If the user passed notes, include them: $ARGUMENTS
5. Tell the user what you saved. Do not commit unless asked.

## Rules
- Never delete past entries from `LOG.md`.
- No secrets, tokens or personal data beyond what is already in the repo.
- Only record things that happened or were decided; do not guess.
