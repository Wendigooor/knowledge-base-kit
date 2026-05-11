"""Storage backend for Knowledge Base Kit.

Uses ChromaDB as the persistent vector store for documents.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.api.types import WhereFilter

from kbk.config import KBKConfig
from kbk.document import Document
from kbk.exceptions import DocumentError, StoreError


class KnowledgeStore:
    """ChromaDB-backed document store.

    Manages document CRUD with automatic metadata indexing.
    Each collection in ChromaDB corresponds to a logical document group.
    """

    def __init__(self, config: Optional[KBKConfig] = None):
        """Initialise store with optional config.

        Args:
            config: KBKConfig instance. Falls back to defaults if omitted.
        """
        self.config = config or KBKConfig()
        self._client: Optional[chromadb.PersistentClient] = None
        self._collections: dict[str, chromadb.Collection] = {}

    @property
    def client(self) -> chromadb.PersistentClient:
        """Lazy-initialised ChromaDB persistent client."""
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
                    path=str(db_path),
                    settings=settings,
                )
            except Exception as exc:
                raise StoreError(f"Failed to initialise ChromaDB: {exc}") from exc
        return self._client

    def _get_collection(self, name: str) -> chromadb.Collection:
        """Get or create a ChromaDB collection by name."""
        if name not in self._collections:
            try:
                self._collections[name] = self.client.get_or_create_collection(name)
            except Exception as exc:
                raise StoreError(
                    f"Failed to get/create collection '{name}': {exc}"
                ) from exc
        return self._collections[name]

    @staticmethod
    def _doc_to_chroma_data(doc: Document) -> tuple[str, str, dict]:
        """Convert a Document to ChromaDB add/update format."""
        metadata = {
            "doc_id": doc.id,
            "version": doc.version,
            "tags": json.dumps(doc.tags, ensure_ascii=False),
            "collection": doc.collection,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }
        # Store user metadata under a special key
        if doc.metadata:
            metadata["user_metadata"] = json.dumps(doc.metadata, ensure_ascii=False)
        return doc.id, doc.content, metadata

    @staticmethod
    def _chroma_to_doc(
        chroma_id: str,
        content: str,
        metadata: dict,
    ) -> Document:
        """Reconstruct a Document from ChromaDB query results."""
        tags_raw = metadata.get("tags", "[]")
        if isinstance(tags_raw, str):
            tags = json.loads(tags_raw)
        else:
            tags = list(tags_raw) if tags_raw else []

        user_meta_raw = metadata.get("user_metadata", "{}")
        if isinstance(user_meta_raw, str):
            user_meta = json.loads(user_meta_raw)
        else:
            user_meta = dict(user_meta_raw) if user_meta_raw else {}

        return Document(
            id=metadata.get("doc_id", chroma_id),
            version=metadata.get("version", 1),
            tags=tags,
            metadata=user_meta,
            content=content or "",
            collection=metadata.get("collection", "default"),
            created_at=metadata.get("created_at", ""),
            updated_at=metadata.get("updated_at", ""),
        )

    def add(self, document: Document) -> str:
        """Add a document to the store.

        Args:
            document: Document instance to store.

        Returns:
            The document ID.

        Raises:
            DocumentError: If document content is empty.
            StoreError: On ChromaDB failure.
        """
        if not document.content.strip():
            raise DocumentError("Document content cannot be empty")

        collection = self._get_collection(document.collection)
        doc_id, content, metadata = self._doc_to_chroma_data(document)

        try:
            collection.add(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
            )
        except Exception as exc:
            raise StoreError(f"Failed to add document: {exc}") from exc

        return doc_id

    def get(self, doc_id: str, collection: str = "default") -> Optional[Document]:
        """Retrieve a single document by ID.

        Args:
            doc_id: UUID of the document.
            collection: Collection name.

        Returns:
            Document if found, None otherwise.
        """
        try:
            col = self._get_collection(collection)
            results = col.get(ids=[doc_id])
        except Exception:
            return None

        if not results or not results["ids"]:
            return None

        return self._chroma_to_doc(
            chroma_id=results["ids"][0],
            content=results["documents"][0] if results.get("documents") else "",
            metadata=results["metadatas"][0] if results.get("metadatas") else {},
        )

    def update(self, document: Document) -> None:
        """Update an existing document in the store.

        Args:
            document: Document with updated fields.
        """
        collection = self._get_collection(document.collection)
        doc_id, content, metadata = self._doc_to_chroma_data(document)

        try:
            collection.update(
                ids=[doc_id],
                documents=[content],
                metadatas=[metadata],
            )
        except Exception as exc:
            raise StoreError(f"Failed to update document: {exc}") from exc

    def delete(self, doc_id: str, collection: str = "default") -> bool:
        """Delete a document by ID.

        Args:
            doc_id: UUID of the document.
            collection: Collection name.

        Returns:
            True if deleted, False if not found.
        """
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
        collection: str = "default",
        top_k: Optional[int] = None,
        filters: Optional[dict] = None,
    ) -> list[tuple[Document, float]]:
        """Semantic search over documents.

        Args:
            query: Natural language query string.
            collection: Collection to search in.
            top_k: Number of results (default from config).
            filters: Optional metadata filters (e.g. {"tags": "[\"python\"]"}).

        Returns:
            List of (Document, similarity_score) tuples, sorted by relevance.
        """
        top_k = top_k or self.config.top_k
        col = self._get_collection(collection)

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
                n_results=top_k,
                where=where_filter,
            )
        except Exception as exc:
            raise StoreError(f"Search failed: {exc}") from exc

        if not results or not results["ids"]:
            return []

        documents = []
        for i in range(len(results["ids"][0])):
            doc = self._chroma_to_doc(
                chroma_id=results["ids"][0][i],
                content=results["documents"][0][i] if results.get("documents") else "",
                metadata=results["metadatas"][0][i] if results.get("metadatas") else {},
            )
            distance = results["distances"][0][i] if results.get("distances") else 0.0
            # Convert distance to similarity (1 / (1 + distance))
            similarity = 1.0 / (1.0 + distance)
            documents.append((doc, similarity))

        return documents

    def list_documents(
        self,
        collection: str = "default",
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """List documents in a collection with pagination.

        Args:
            collection: Collection name.
            limit: Max number of documents.
            offset: Number of documents to skip.

        Returns:
            List of Document instances.
        """
        col = self._get_collection(collection)
        try:
            results = col.get(limit=limit, offset=offset)
        except Exception as exc:
            raise StoreError(f"Failed to list documents: {exc}") from exc

        if not results or not results["ids"]:
            return []

        docs = []
        for i in range(len(results["ids"])):
            docs.append(
                self._chroma_to_doc(
                    chroma_id=results["ids"][i],
                    content=results["documents"][i] if results.get("documents") else "",
                    metadata=results["metadatas"][i] if results.get("metadatas") else {},
                )
            )
        return docs

    def count(self, collection: str = "default") -> int:
        """Get the number of documents in a collection."""
        col = self._get_collection(collection)
        return col.count()

    def list_collections(self) -> list[str]:
        """List all collection names in the store."""
        try:
            collections = self.client.list_collections()
            return [c.name for c in collections]
        except Exception as exc:
            raise StoreError(f"Failed to list collections: {exc}") from exc

    def delete_collection(self, name: str) -> None:
        """Delete an entire collection and all its documents."""
        try:
            self.client.delete_collection(name)
            self._collections.pop(name, None)
        except Exception as exc:
            raise StoreError(f"Failed to delete collection '{name}': {exc}") from exc
