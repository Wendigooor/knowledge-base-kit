"""Smoke tests for KBK v0.2 — Enterprise Semantic Index."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kbk.models import IndexedChunk
from kbk.config import KBKConfig
from kbk.store import KnowledgeStore
from kbk.state import StateTracker
from kbk.indexer import Indexer


def test_chunk_create():
    c = IndexedChunk(source_url="https://example.com/page", content="test", tags=["a"])
    assert c.id
    assert c.source_url == "https://example.com/page"
    assert "a" in c.tags
    print("✅ Chunk create")


def test_chunk_from_dict():
    data = {"id": "abc", "source_url": "https://x", "content": "hello", "tags": ["t1"]}
    c = IndexedChunk.from_dict(data)
    assert c.id == "abc"
    assert c.content == "hello"
    print("✅ Chunk from_dict")


def test_state_tracker():
    with tempfile.TemporaryDirectory() as tmp:
        state = StateTracker(os.path.join(tmp, "state.json"))
        url = "https://example.com/doc"
        h = StateTracker.hash_content("content v1")
        assert state.has_changed(url, h) is True
        state.mark_indexed(url, h, ["chunk1", "chunk2"])
        assert state.has_changed(url, h) is False
        h2 = StateTracker.hash_content("content v2")
        assert state.has_changed(url, h2) is True
    print("✅ State tracker hash/diff")


def test_store_init():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        store._init_client()
        assert store.list_collections() == []
    print("✅ Store init")


def test_store_upsert_and_search():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp, top_k=5)
        store = KnowledgeStore(cfg)
        c = IndexedChunk(source_url="https://x", content="PostgreSQL migration guide", tags=["db"], collection="arch")
        store.upsert_chunk(c)
        assert store.count("arch") == 1
        results = store.search("postgres", collection_filter="arch")
        assert len(results) >= 1
        assert "postgres" in results[0].content.lower()
    print("✅ Store upsert & search")


def test_store_delete():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        c = IndexedChunk(source_url="https://x", content="delete me", collection="test")
        store.upsert_chunk(c)
        store.delete_chunks([c.id], "test")
        assert store.count("test") == 0
    print("✅ Store delete chunks")


def test_store_stats():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        stats = store.get_stats()
        assert stats["total"] == 0
        store.upsert_chunk(IndexedChunk(source_url="https://x", content="doc 1", collection="arch"))
        stats = store.get_stats()
        assert stats["total"] == 1
    print("✅ Store stats")


def test_indexer_clean():
    store = KnowledgeStore(KBKConfig(db_path="/tmp/_kbk_test_clean"))
    state = StateTracker("/tmp/_kbk_test_clean_state.json")
    idx = Indexer(store, state)
    cleaned = idx.clean_html("<html><body><p>Hello</p></body></html>")
    assert "Hello" in cleaned
    assert "<html>" not in cleaned
    print("✅ Indexer clean HTML")


def test_indexer_chunk():
    store = KnowledgeStore(KBKConfig(db_path="/tmp/_kbk_test_chunk"))
    state = StateTracker("/tmp/_kbk_test_chunk_state.json")
    idx = Indexer(store, state)
    # Split on periods to create sentence boundaries
    text = ". ".join(["word"] * 200)
    chunks = idx.chunk(text, chunk_size=10)
    assert len(chunks) >= 2
    print("✅ Indexer chunk")


def test_indexer_full_flow():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp, state_path=os.path.join(tmp, "state.json"))
        store = KnowledgeStore(cfg)
        state = StateTracker(cfg.state_path)
        idx = Indexer(store, state, llm_api_key="")
        doc_hash = StateTracker.hash_content("<h1>Test</h1><p>API Gateway on K8s</p>")
        chunks = idx.process_document(
            url="https://confluence/page/123",
            raw_html="<h1>Test</h1><p>API Gateway on K8s</p>",
            title="API Gateway Migration",
            content_hash=doc_hash,
        )
        assert len(chunks) >= 1
        assert store.count("unclassified") >= 1
        results = store.search("api gateway", collection_filter="unclassified")
        assert len(results) >= 1
    print("✅ Indexer full flow")


def test_targets_config():
    from kbk.config import load_targets
    targets = load_targets("targets.yaml")
    assert len(targets) >= 1
    assert targets[0]["type"] in ("confluence", "gitlab")
    print("✅ Targets config")


if __name__ == "__main__":
    tests = [
        test_chunk_create,
        test_chunk_from_dict,
        test_state_tracker,
        test_store_init,
        test_store_upsert_and_search,
        test_store_delete,
        test_store_stats,
        test_indexer_clean,
        test_indexer_chunk,
        test_indexer_full_flow,
        test_targets_config,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"❌ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
