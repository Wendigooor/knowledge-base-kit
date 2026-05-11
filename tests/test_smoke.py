"""Smoke tests for KBK v2 — Enterprise Semantic Index."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kbk.document import IndexedDocument
from kbk.config import KBKConfig
from kbk.store import KnowledgeStore
from kbk.indexer import Indexer


def test_document_create():
    doc = IndexedDocument(summary="API Gateway on K8s", tags=["architecture", "k8s"])
    assert doc.id
    assert doc.summary == "API Gateway on K8s"
    assert "k8s" in doc.tags
    print("✅ IndexedDocument create")


def test_document_source_url():
    doc = IndexedDocument(metadata={"source_url": "https://confluence/page/123"})
    assert doc.source_url == "https://confluence/page/123"
    print("✅ IndexedDocument source_url")


def test_document_from_dict():
    data = {"id": "abc123", "summary": "test", "tags": ["a"], "collection": "arch"}
    doc = IndexedDocument.from_dict(data)
    assert doc.id == "abc123"
    assert doc.summary == "test"
    assert doc.collection == "arch"
    print("✅ IndexedDocument from_dict")


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
        doc = IndexedDocument(summary="PostgreSQL migration guide", tags=["db", "postgres"], collection="arch")
        store.upsert(doc)
        assert store.count("arch") == 1
        results = store.search("postgres", collection_filter="arch")
        assert len(results) >= 1
        assert results[0].summary == doc.summary
    print("✅ Store upsert & search")


def test_store_get():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        doc = IndexedDocument(summary="Test doc", collection="test")
        store.upsert(doc)
        retrieved = store.get(doc.id, "test")
        assert retrieved is not None
        assert retrieved.summary == "Test doc"
    print("✅ Store get")


def test_store_delete():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        doc = IndexedDocument(summary="Delete me", collection="test")
        store.upsert(doc)
        assert store.delete(doc.id, "test") is True
        assert store.count("test") == 0
    print("✅ Store delete")


def test_store_stats():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        stats = store.get_stats()
        assert "collections" in stats
        assert "total" in stats
        assert stats["total"] == 0
        doc = IndexedDocument(summary="Doc 1", collection="arch")
        store.upsert(doc)
        stats = store.get_stats()
        assert stats["total"] == 1
    print("✅ Store stats")


def test_indexer_clean():
    store = KnowledgeStore(KBKConfig(db_path="/tmp/_kbk_test_indexer"))
    indexer = Indexer(store)
    cleaned = indexer._clean("<html><body><p>Hello</p></body></html>")
    assert "Hello" in cleaned
    assert "<html>" not in cleaned
    print("✅ Indexer clean")


def test_indexer_chunk():
    store = KnowledgeStore(KBKConfig(db_path="/tmp/_kbk_test_indexer_chunk"))
    indexer = Indexer(store)
    text = "word " * 2000
    chunks = indexer._chunk(text, chunk_size=512)
    assert len(chunks) >= 3
    print("✅ Indexer chunk")


def test_indexer_full_flow():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        indexer = Indexer(store)
        doc = indexer.index(
            raw_text="<h1>API Gateway Migration</h1><p>Moving to K8s for scalability</p>",
            source_url="https://confluence/page/123",
            source_type="confluence",
            collection="architecture",
        )
        assert doc.id
        assert "API" in doc.summary or "Migration" in doc.summary
        assert doc.source_url == "https://confluence/page/123"
        assert doc.source_type == "confluence"
        assert store.count("architecture") == 1
    print("✅ Indexer full flow")


if __name__ == "__main__":
    tests = [
        test_document_create,
        test_document_source_url,
        test_document_from_dict,
        test_store_init,
        test_store_upsert_and_search,
        test_store_get,
        test_store_delete,
        test_store_stats,
        test_indexer_clean,
        test_indexer_chunk,
        test_indexer_full_flow,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)
