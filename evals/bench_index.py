"""Benchmark the FTS5 index on a synthetic corpus (nothing touches your real notes or index).

    python3 evals/bench_index.py [chunks=50000] [chunks_per_file=25]
"""
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "knowledge-base"))
import index  # noqa: E402

N_CHUNKS = int(sys.argv[1]) if len(sys.argv) > 1 else 50_000
PER_FILE = int(sys.argv[2]) if len(sys.argv) > 2 else 25
rng = random.Random(42)
VOCAB = ["".join(rng.choices("abcdefghijklmnopqrstuvwxyz", k=rng.randint(3, 9))) for _ in range(20_000)]
CUM = [sum(1 / (r + 1) for r in range(i + 1)) for i in range(len(VOCAB))]  # Zipf-like word frequencies
TOPICS = [f"topic{i}" for i in range(20)]
TAGS = [f"tag{i}" for i in range(30)]


def words(n):
    return " ".join(rng.choices(VOCAB, cum_weights=CUM, k=n))


def make_file(i):
    fm = (f"---\ntopic: {rng.choice(TOPICS)}\nsource: src{i % 50}\n"
          f"date: 2026-{rng.randint(1, 11):02d}-{rng.randint(1, 28):02d}\ntags: [{', '.join(rng.sample(TAGS, 3))}]\n---\n")
    body = "".join(f"## {words(3)}\n{words(90)}\n\n" for _ in range(PER_FILE))
    return fm + f"# {words(4)}\n\n" + body


def timed(fn):
    t = time.perf_counter()
    r = fn()
    return r, (time.perf_counter() - t) * 1000


def pct(xs, p):
    return sorted(xs)[min(len(xs) - 1, int(len(xs) * p))]


with tempfile.TemporaryDirectory() as tmp:
    notes = Path(tmp) / "notes"
    notes.mkdir()
    n_files = N_CHUNKS // PER_FILE
    for i in range(n_files):
        (notes / f"f{i:05d}.md").write_text(make_file(i))
    conn = index.connect(Path(tmp) / "idx.db")

    st, ms = timed(lambda: index.sync(conn, notes))
    print(f"initial build        : {st.added} files, {st.chunks_written} chunks in {ms / 1000:.1f} s")
    _, ms = timed(lambda: index.sync(conn, notes))
    print(f"no-change sync       : {ms:.0f} ms  ({n_files} files stat'ed, none re-chunked)")
    (notes / "f00007.md").write_text(make_file(7))
    st, ms = timed(lambda: index.sync(conn, notes))
    print(f"1 file edited sync   : {ms:.0f} ms  (updated={st.updated}, unchanged={st.unchanged})")
    (notes / "new.md").write_text(make_file(99999))
    st, ms = timed(lambda: index.sync(conn, notes))
    print(f"1 file added sync    : {ms:.0f} ms  (added={st.added})")
    _, ms = timed(lambda: index.sync(conn, notes, verify=True))
    print(f"verify sync (rehash) : {ms:.0f} ms  (hashes all files, re-chunks none)")

    s = index.stats(conn, Path(tmp) / "idx.db")
    print(f"index size           : {s['db_bytes'] / 1e6:.0f} MB for {s['chunks']} chunks")

    def run(label, make_kwargs, n=300):
        index.search(conn, "warm up")
        lat = []
        for _ in range(n):
            q, kw = make_kwargs()
            lat.append(timed(lambda: index.search(conn, q, **kw))[1])
        print(f"{label:<21}: p50 {statistics.median(lat):6.2f} ms   p95 {pct(lat, .95):6.2f} ms   max {max(lat):6.2f} ms")

    content = lambda k: " ".join(rng.sample(VOCAB[200:], k))  # mid/low-frequency "content" words
    run("query (content, 3w)", lambda: (content(3), {}))
    run("query (content+topic)", lambda: (content(3), {"topic": rng.choice(TOPICS)}))
    print("-- worst case: every word drawn from the Zipf head, so most terms match a large share of ALL chunks")
    run("query (2 common)", lambda: (words(2), {}))
    run("query (4 common)", lambda: (words(4), {}))
    run("+ topic filter", lambda: (words(3), {"topic": rng.choice(TOPICS)}))
    run("+ topic+tag+date", lambda: (words(3), {"topic": rng.choice(TOPICS), "tags": [rng.choice(TAGS)], "date_from": "2026-06-01"}))
    run("filter only", lambda: ("", {"topic": rng.choice(TOPICS), "tags": [rng.choice(TAGS)]}))
    conn.close()
