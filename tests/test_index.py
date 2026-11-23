"""Tests for the FTS5 index. Run: python3 -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-servers" / "knowledge-base"))
import index  # noqa: E402

A = """---
topic: mcp
source: course
date: 2026-03-01
tags: [mcp, stdio]
---
# MCP servers

## Transports
A stdio server must never print to standard output.

## Tools
Give each tool a clear name.
"""
B = "# Hooks\n\n## Basics\nHooks run shell commands at lifecycle events.\n"


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.notes = Path(self.tmp.name) / "notes"
        (self.notes / "sub").mkdir(parents=True)
        (self.notes / "a.md").write_text(A)
        (self.notes / "sub" / "b.md").write_text(B)
        self.conn = index.connect(Path(self.tmp.name) / "idx.db")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def sync(self, **kw):
        return index.sync(self.conn, self.notes, **kw)

    def test_first_sync_indexes_chunks(self):
        s = self.sync()
        self.assertEqual((s.added, s.updated, s.removed), (2, 0, 0))
        self.assertGreaterEqual(index.stats(self.conn)["chunks"], 3)

    def test_unchanged_files_are_skipped(self):
        self.sync()
        s = self.sync()
        self.assertEqual((s.added, s.updated, s.unchanged, s.chunks_written), (0, 0, 2, 0))

    def test_only_modified_file_is_rechunked(self):
        self.sync()
        (self.notes / "a.md").write_text(A + "\n## New\nBM25 ranking is great.\n")
        s = self.sync()
        self.assertEqual((s.updated, s.unchanged), (1, 1))
        self.assertTrue(index.search(self.conn, "BM25 ranking"))

    def test_touch_without_content_change_is_not_rechunked(self):
        self.sync()
        future = time.time() + 100
        os.utime(self.notes / "a.md", (future, future))
        s = self.sync()
        self.assertEqual((s.touched, s.updated, s.chunks_written), (1, 0, 0))

    def test_old_text_disappears_after_edit(self):
        self.sync()
        (self.notes / "sub" / "b.md").write_text("# Hooks\n\n## Basics\nCompletely different words: zebra.\n")
        self.sync()
        self.assertEqual(index.search(self.conn, "lifecycle"), [])
        self.assertTrue(index.search(self.conn, "zebra"))

    def test_deleted_and_added_files(self):
        self.sync()
        (self.notes / "sub" / "b.md").unlink()
        (self.notes / "c.md").write_text("# C\n\nPlain text about embeddings.\n")
        s = self.sync()
        self.assertEqual((s.added, s.removed), (1, 1))
        self.assertEqual(index.search(self.conn, "lifecycle"), [])
        self.assertTrue(index.search(self.conn, "embeddings"))
        n = self.conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
        self.assertEqual(n, index.stats(self.conn)["chunks"])

    def test_metadata_filters(self):
        self.sync()
        self.assertTrue(all(h["topic"] == "mcp" for h in index.search(self.conn, "server", topic="MCP")))
        self.assertEqual(index.search(self.conn, "server", topic="nothing"), [])
        self.assertTrue(index.search(self.conn, "server", tags=["stdio"]))
        self.assertEqual(index.search(self.conn, "server", tags=["stdio", "missing"]), [])
        self.assertTrue(index.search(self.conn, "server", source="cour"))
        self.assertTrue(index.search(self.conn, "server", date_from="2026-03-01", date_to="2026-03-01"))
        self.assertEqual(index.search(self.conn, "server", date_from="2026-03-02"), [])

    def test_filter_only_browse_and_default_topic(self):
        self.sync()
        hits = index.search(self.conn, "", topic="sub")  # b.md lives in sub/ -> topic "sub"
        self.assertTrue(hits and all(h["path"] == "sub/b.md" for h in hits))

    def test_bm25_prefers_heading_and_more_matches(self):
        self.sync()
        top = index.search(self.conn, "transports stdio")[0]
        self.assertEqual(top["heading"], "MCP servers > Transports")

    def test_special_characters_in_query_do_not_break_fts(self):
        self.sync()
        for q in ['"unbalanced', "a AND (b", "NEAR/2 -x *", "C++ ; DROP TABLE", "''", "mcp: stdio"]:
            index.search(self.conn, q)  # must not raise

    def test_code_fence_hash_is_not_a_heading(self):
        chunks = index.chunk_markdown("# T\n\n```\n# not a heading\n```\n", "T")
        self.assertEqual([c.heading for c in chunks], ["T"])

    def test_long_section_is_split(self):
        body = "# T\n\n" + "\n\n".join(f"Paragraph {i} " + "word " * 80 for i in range(10))
        chunks = index.chunk_markdown(body, "T")
        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(len(c.text) <= index.MAX_CHARS for c in chunks))

    def test_chunker_version_bump_forces_rechunk(self):
        self.sync()
        self.conn.execute("UPDATE meta SET value='old' WHERE key='chunker_version'")
        self.conn.close()
        self.conn = index.connect(Path(self.tmp.name) / "idx.db")
        s = self.sync()
        self.assertEqual((s.updated, s.unchanged), (2, 0))  # hashes were cleared: every file is re-chunked

    def test_rebuild(self):
        self.sync()
        self.conn.close()
        s = index.rebuild(Path(self.tmp.name) / "idx.db", self.notes)
        self.assertEqual(s.added, 2)
        self.conn = index.connect(Path(self.tmp.name) / "idx.db")


if __name__ == "__main__":
    unittest.main()
