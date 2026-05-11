"""Smoke tests for Knowledge Base Kit."""
import os
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kbk.document import Document
from kbk.config import KBKConfig
from kbk.store import KnowledgeStore
from kbk.versioning import VersionManager
from kbk.exceptions import DocumentError


def test_document_create():
    doc = Document(content="Hello", tags=["test"])
    assert doc.id
    assert doc.version == 1
    assert doc.content == "Hello"
    assert doc.tags == ["test"]
    print("✅ Document create")


def test_document_update():
    doc = Document(content="v1", tags=["a"])
    doc.update(content="v2", tags=["a", "b"])
    assert doc.version == 2
    assert doc.content == "v2"
    assert len(doc.previous_versions) == 1
    print("✅ Document update")


def test_document_auto_prune():
    doc = Document(content="base", max_versions=3)
    for i in range(5):
        doc.update(content=f"v{i}")
    assert len(doc.previous_versions) <= 3
    assert doc.version == 6
    print("✅ Document auto-prune")


def test_document_empty_content():
    # Content can be empty at Document level — store.add() validates it
    doc = Document(content="")
    assert doc.content == ""
    print("✅ Document empty content allowed (validated at store level)")


def test_store_init():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        store._init_client()
        assert store.list_collections() == []
    print("✅ Store init")


def test_store_crud():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        doc = Document(content="Test content", tags=["smoke"], collection="smoke")
        doc_id = store.add(doc)
        assert doc_id == doc.id

        retrieved = store.get(doc_id, "smoke")
        assert retrieved is not None
        assert retrieved.content == "Test content"

        docs = store.list_documents("smoke")
        assert len(docs) == 1

        count = store.count("smoke")
        assert count == 1
    print("✅ Store CRUD")


def test_store_search():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp, top_k=5)
        store = KnowledgeStore(cfg)
        store.add(Document(content="Python programming", collection="dev"))
        store.add(Document(content="JavaScript programming", collection="dev"))
        results = store.search("Python", collection_filter="dev")
        assert len(results) > 0
    print("✅ Store search")


def test_store_export():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        store.add(Document(content="Doc 1", collection="test"))
        export_path = os.path.join(tmp, "export.json")
        count = store.export_to_json(export_path)
        assert count == 1
        assert os.path.exists(export_path)
    print("✅ Store export")


def test_versioning_save_history():
    with tempfile.TemporaryDirectory() as tmp:
        vm = VersionManager(versions_dir=tmp)
        doc = Document(content="v1", id="test-doc")
        vm.save_snapshot(doc)
        doc.update(content="v2")
        vm.save_snapshot(doc)
        history = vm.get_history("test-doc")
        assert len(history) >= 2
    print("✅ Versioning save & history")


def test_versioning_snapshot_count():
    with tempfile.TemporaryDirectory() as tmp:
        vm = VersionManager(versions_dir=tmp)
        assert vm.snapshot_count() == 0
        vm.save_snapshot(Document(content="test", id="d1"))
        assert vm.snapshot_count() == 1
    print("✅ Versioning snapshot count")


if __name__ == "__main__":
    tests = [
        test_document_create,
        test_document_update,
        test_document_auto_prune,
        test_document_empty_content,
        test_store_init,
        test_store_crud,
        test_store_search,
        test_store_export,
        test_versioning_save_history,
        test_versioning_snapshot_count,
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
