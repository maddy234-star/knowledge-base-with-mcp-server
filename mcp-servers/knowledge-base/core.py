"""Pure note-search logic. No MCP imports, so it is easy to test and to swap out.

Later courses (RAG / embeddings): replace the body of `search_notes` with vector
search. Keep the signature and return shape and nothing else needs to change.
"""
import re
from pathlib import Path

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "is",
    "are", "was", "were", "do", "does", "did", "how", "what", "why", "when",
    "i", "my", "me", "it", "this", "that", "about", "can", "use", "using", "learn", "learned",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if len(t) > 1 and t not in STOPWORDS]


def _note_files(notes_dir: Path) -> list[Path]:
    return sorted(p for p in notes_dir.rglob("*.md") if p.is_file())


def _name(notes_dir: Path, path: Path) -> str:
    return path.relative_to(notes_dir).with_suffix("").as_posix()


def _title(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem


def list_notes(notes_dir: Path) -> list[dict]:
    return [{"name": _name(notes_dir, p), "title": _title(p)} for p in _note_files(notes_dir)]


def get_note(notes_dir: Path, name: str) -> str | None:
    """Return a note's text, or None. Refuses anything outside notes_dir."""
    root = notes_dir.resolve()
    wanted = name.strip().removesuffix(".md").lower()
    for p in _note_files(notes_dir):
        if _name(notes_dir, p).lower() == wanted or p.stem.lower() == wanted:
            resolved = p.resolve()
            if resolved.is_relative_to(root):
                return resolved.read_text(encoding="utf-8")
    return None


def search_notes(notes_dir: Path, query: str, max_results: int = 5) -> list[dict]:
    """Keyword search. Score = body hits + 3x title hits."""
    tokens = _tokens(query)
    if not tokens:
        return []
    results = []
    for p in _note_files(notes_dir):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        lower, title = text.lower(), _title(p).lower()
        score = 0
        for t in tokens:
            pattern = rf"\b{re.escape(t)}\b"
            score += len(re.findall(pattern, lower)) + 3 * len(re.findall(pattern, title))
        if score == 0:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        body = [ln for ln in lines if not ln.startswith("#")]  # prefer content over headings
        snippet = next(
            (ln[:200] for ln in body + lines if any(t in ln.lower() for t in tokens)), ""
        )
        results.append({"name": _name(notes_dir, p), "title": _title(p), "score": score, "snippet": snippet})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:max_results]
