#!/usr/bin/env python3
"""Command-line front end for the knowledge-base search index.

    kb_index.py sync              # incremental: only changed files are re-chunked (default)
    kb_index.py sync --verify     # hash every file instead of trusting mtime+size
    kb_index.py rebuild           # delete the index and build from scratch
    kb_index.py watch             # the indexing agent: re-sync whenever notes change
    kb_index.py search "query" --topic mcp --tag stdio --from 2026-01-01
    kb_index.py stats

Notes dir: --notes or $KB_NOTES_DIR (default: <repo>/notes).  Index file: --db or $KB_INDEX_PATH
(default: <repo>/.kb/index.db).
"""
import argparse
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import index  # noqa: E402


def _log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def cmd_sync(conn, args) -> int:
    print(index.sync(conn, args.notes, verify=args.verify).summary())
    return 0


def cmd_rebuild(args) -> int:
    print(index.rebuild(args.db, args.notes).summary())
    return 0


def cmd_stats(conn, args) -> int:
    s = index.stats(conn, args.db)
    mb = f"{s['db_bytes'] / 1e6:.2f} MB" if s["db_bytes"] is not None else "n/a"
    print(f"files={s['files']} chunks={s['chunks']} db={mb} last_indexed={s['last_indexed']}")
    for topic, n in s["topics"].items():
        print(f"  {topic}: {n} chunks")
    return 0


def cmd_search(conn, args) -> int:
    t0 = time.perf_counter()
    hits = index.search(
        conn, args.query, topic=args.topic, source=args.source, tags=args.tag,
        date_from=args.date_from, date_to=args.date_to, limit=args.limit,
    )
    ms = (time.perf_counter() - t0) * 1000
    for h in hits:
        tags = ",".join(h["tags"]) or "-"
        print(f"{h['score']:8.3f}  {h['name']} > {h['heading']}  [{h['topic']} | {h['date']} | {tags}]")
        print(f"          {h['snippet']}")
    print(f"{len(hits)} hit(s) in {ms:.1f} ms")
    return 0


def cmd_watch(args) -> int:
    """Poll the notes folder and re-index on any add / modify / delete.

    Polling is cheap because sync() skips unchanged files after one stat(). Stop with Ctrl-C.
    """
    stop = False

    def _stop(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    conn = index.connect(args.db)
    _log(f"watching {args.notes} (every {args.interval}s) -> {args.db}")
    first = True
    while not stop:
        try:
            st = index.sync(conn, args.notes)
            if first or st.changed:
                _log("sync: " + st.summary())
            first = False
        except Exception as exc:  # e.g. database locked, file mid-write: retry next tick
            _log(f"sync failed, will retry: {exc!r}")
        for _ in range(int(args.interval * 10)):  # sleep in small steps so Ctrl-C is prompt
            if stop:
                break
            time.sleep(0.1)
    conn.close()
    _log("stopped")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--notes", type=Path, default=None, help="notes directory")
    ap.add_argument("--db", type=Path, default=None, help="index database file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sync"); p.add_argument("--verify", action="store_true")
    sub.add_parser("rebuild")
    sub.add_parser("stats")
    p = sub.add_parser("watch"); p.add_argument("--interval", type=float, default=2.0)
    p = sub.add_parser("search")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--topic"); p.add_argument("--source"); p.add_argument("--tag", action="append")
    p.add_argument("--from", dest="date_from"); p.add_argument("--to", dest="date_to")
    p.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()

    args.notes = (args.notes or index.default_notes_dir()).resolve()
    args.db = args.db or index.default_db_path(args.notes)

    if args.cmd == "rebuild":
        return cmd_rebuild(args)
    if args.cmd == "watch":
        return cmd_watch(args)
    conn = index.connect(args.db)
    try:
        return {"sync": cmd_sync, "stats": cmd_stats, "search": cmd_search}[args.cmd](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
