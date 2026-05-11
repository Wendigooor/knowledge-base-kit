"""ChromaDB-backed semantic index store for KBK v2."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from kbk.config import KBKConfig
from kbk.document import IndexedDocument
from kbk.exceptions import StoreError

# WhereFilter type — use dict for newer ChromaDB versions
WhereFilter = dict


class KnowledgeStore:
    """ChromaDB-backed semantic index.

    Stores vectors + metadata for each indexed document.
    Does NOT store full content — only LLM-generated summary + source pointers.
    """

    def __init__(self, config: Optional[KBKConfig] = None):
        self.config = config or KBKConfig()
        self._client: Optional[chromadb.PersistentClient] = None
        self._collections: dict[str, chromadb.Collection] = {}

    def _init_client(self) -> None:
        _ = self.client

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            db_path = Path(self.config.db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            settings = ChromaSettings(
                anonymized_telemetry=self.config.chroma_settings.get(
                    "anonymized_telemetry", False
                ),
            )
            try:
                self._client = chromadb.PersistentClient(
                    path=str(db_path), settings=settings,
                )
            except Exception as exc:
                raise StoreError(f"Failed to initialise ChromaDB: {exc}") from exc
        return self._client

    def _get_collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            try:
                self._collections[name] = self.client.get_or_create_collection(name)
            except Exception as exc:
                raise StoreError(
                    f"Failed to get/create collection '{name}': {exc}"
                ) from exc
        return self._collections[name]

    def upsert(self, doc: IndexedDocument) -> str:
        """Insert or update a document in the index.
        
        If a document with the same ID exists, it is overwritten.
        """
        collection = self._get_collection(doc.collection)
        metadata = {
            "doc_id": doc.id,
            "tags": json.dumps(doc.tags, ensure_ascii=False),
            "summary": doc.summary,
            "source_url": doc.source_url,
            "source_type": doc.source_type,
            "collection": doc.collection,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "chunk_count": doc.chunk_count,
        }
        if doc.metadata:
            metadata["user_metadata"] = json.dumps(doc.metadata, ensure_ascii=False)

        try:
            collection.upsert(
                ids=[doc.id],
                documents=[doc.summary],
                metadatas=[metadata],
            )
        except Exception as exc:
            raise StoreError(f"Failed to upsert document: {exc}") from exc
        return doc.id

    def get(self, doc_id: str, collection: str = "default") -> Optional[IndexedDocument]:
        try:
            col = self._get_collection(collection)
            results = col.get(ids=[doc_id])
        except Exception:
            return None
        if not results or not results["ids"]:
            return None
        return self._meta_to_doc(
            results["ids"][0],
            results["metadatas"][0] if results.get("metadatas") else {},
        )

    def delete(self, doc_id: str, collection: str = "default") -> bool:
        try:
            col = self._get_collection(collection)
            existing = col.get(ids=[doc_id])
            if not existing or not existing["ids"]:
                return False
            col.delete(ids=[doc_id])
            return True
        except Exception:
            return False

    def search(
        self,
        query: str,
        n_results: Optional[int] = None,
        collection_filter: Optional[str] = None,
        filters: Optional[dict] = None,
    ) -> list[IndexedDocument]:
        n_results = n_results or self.config.top_k
        collection_name = collection_filter or self.config.default_collection
        col = self._get_collection(collection_name)

        where_filter: Optional[WhereFilter] = None
        if filters:
            where_filter = {}
            for key, value in filters.items():
                if isinstance(value, str):
                    where_filter[key] = {"$eq": value}
                elif isinstance(value, dict):
                    where_filter[key] = value

        try:
            results = col.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter,
            )
        except Exception as exc:
            raise StoreError(f"Search failed: {exc}") from exc

        if not results or not results["ids"]:
            return []

        docs = []
        for i in range(len(results["ids"][0])):
            docs.append(self._meta_to_doc(
                results["ids"][0][i],
                results["metadatas"][0][i] if results.get("metadatas") else {},
            ))
        return docs

    def list_documents(self, collection: str = "default", limit: int = 100,
                       offset: int = 0) -> list[IndexedDocument]:
        col = self._get_collection(collection)
        try:
            results = col.get(limit=limit, offset=offset)
        except Exception as exc:
            raise StoreError(f"Failed to list documents: {exc}") from exc
        if not results or not results["ids"]:
            return []
        docs = []
        for i in range(len(results["ids"])):
            docs.append(self._meta_to_doc(
                results["ids"][i],
                results["metadatas"][i] if results.get("metadatas") else {},
            ))
        return docs

    def count(self, collection: str = "default") -> int:
        col = self._get_collection(collection)
        return col.count()

    def list_collections(self) -> list[str]:
        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]
        except Exception as exc:
            raise StoreError(f"Failed to list collections: {exc}") from exc

    def delete_collection(self, name: str) -> None:
        try:
            self.client.delete_collection(name)
            self._collections.pop(name, None)
        except Exception as exc:
            raise StoreError(f"Failed to delete collection '{name}': {exc}") from exc

    def get_stats(self) -> dict:
        """Return index statistics: doc count per collection + total."""
        cols = self.list_collections()
        stats = {"collections": {}, "total": 0}
        for c in cols:
            cnt = self.count(c)
            stats["collections"][c] = cnt
            stats["total"] += cnt
        return stats

    @staticmethod
    def _meta_to_doc(chroma_id: str, metadata: dict) -> IndexedDocument:
        tags_raw = metadata.get("tags", "[]")
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else (list(tags_raw) if tags_raw else [])

        return IndexedDocument(
            id=metadata.get("doc_id", chroma_id),
            summary=metadata.get("summary", ""),
            tags=tags,
            metadata={"source_url": metadata.get("source_url", ""), "source_type": metadata.get("source_type", "unknown")},
            collection=metadata.get("collection", "unclassified"),
            created_at=metadata.get("created_at", ""),
            updated_at=metadata.get("updated_at", ""),
            chunk_count=metadata.get("chunk_count", 0),
        )
