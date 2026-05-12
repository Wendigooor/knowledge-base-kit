"""ChromaDB-backed store for KBK v0.2."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from kbk.config import KBKConfig
from kbk.models import IndexedChunk
from kbk.exceptions import StoreError

WhereFilter = dict


class KnowledgeStore:
    def __init__(self, config: Optional[KBKConfig] = None):
        self.config = config or KBKConfig()
        self._client: Optional[chromadb.PersistentClient] = None
        self._collections: dict[str, chromadb.Collection] = {}

    def _init_client(self):
        _ = self.client

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            db_path = Path(self.config.db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            try:
                self._client = chromadb.PersistentClient(
                    path=str(db_path),
                    settings=Settings(anonymized_telemetry=False),
                )
            except Exception as exc:
                raise StoreError(f"ChromaDB init failed: {exc}") from exc
        return self._client

    def _get_collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            try:
                self._collections[name] = self.client.get_or_create_collection(name)
            except Exception as exc:
                raise StoreError(f"Collection '{name}' error: {exc}") from exc
        return self._collections[name]

    def upsert_chunk(self, chunk: IndexedChunk) -> str:
        col = self._get_collection(chunk.collection)
        meta = {
            "chunk_id": chunk.id, "source_url": chunk.source_url,
            "summary": chunk.summary, "tags": json.dumps(chunk.tags),
            "access_group": chunk.access_group, "content_hash": chunk.content_hash,
        }
        try:
            col.upsert(ids=[chunk.id], documents=[chunk.content], metadatas=[meta])
        except Exception as exc:
            raise StoreError(f"Upsert failed: {exc}") from exc
        return chunk.id

    def delete_chunks(self, chunk_ids: list[str], collection: str = "default"):
        if not chunk_ids:
            return
        try:
            col = self._get_collection(collection)
            col.delete(ids=chunk_ids)
        except Exception:
            pass

    def search(self, query: str, n_results: Optional[int] = None,
               collection_filter: Optional[str] = None,
               filters: Optional[dict] = None) -> list[IndexedChunk]:
        n_results = n_results or self.config.top_k
        col_name = collection_filter or self.config.default_collection
        col = self._get_collection(col_name)
        where = None
        if filters:
            where = {k: {"$eq": v} if isinstance(v, str) else v for k, v in filters.items()}
        try:
            results = col.query(query_texts=[query], n_results=n_results, where=where)
        except Exception as exc:
            raise StoreError(f"Search failed: {exc}") from exc
        if not results or not results["ids"]:
            return []
        chunks = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            tags = json.loads(meta.get("tags", "[]")) if isinstance(meta.get("tags"), str) else []
            chunks.append(IndexedChunk(
                id=results["ids"][0][i],
                source_url=meta.get("source_url", ""),
                content=results["documents"][0][i] if results.get("documents") else "",
                summary=meta.get("summary", ""),
                tags=tags,
                access_group=meta.get("access_group", "public"),
                content_hash=meta.get("content_hash", ""),
                collection=col_name,
            ))
        return chunks

    def list_chunks(self, collection: str = "default", limit: int = 100) -> list[IndexedChunk]:
        col = self._get_collection(collection)
        try:
            results = col.get(limit=limit)
        except Exception as exc:
            raise StoreError(f"List failed: {exc}") from exc
        if not results or not results["ids"]:
            return []
        chunks = []
        for i in range(len(results["ids"])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            tags = json.loads(meta.get("tags", "[]")) if isinstance(meta.get("tags"), str) else []
            chunks.append(IndexedChunk(
                id=results["ids"][i], source_url=meta.get("source_url", ""),
                content=results["documents"][i] if results.get("documents") else "",
                summary=meta.get("summary", ""), tags=tags,
                access_group=meta.get("access_group", "public"),
                content_hash=meta.get("content_hash", ""), collection=collection,
            ))
        return chunks

    def count(self, collection: str = "default") -> int:
        return self._get_collection(collection).count()

    def list_collections(self) -> list[str]:
        return [c.name for c in self.client.list_collections()]

    def delete_collection(self, name: str):
        self.client.delete_collection(name)
        self._collections.pop(name, None)

    def get_stats(self) -> dict:
        cols = self.list_collections()
        stats = {"collections": {}, "total": 0}
        for c in cols:
            cnt = self.count(c)
            stats["collections"][c] = cnt
            stats["total"] += cnt
        return stats
