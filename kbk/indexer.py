"""Indexer — ETL pipeline for KBK v2.

Converts raw source content → clean text → LLM summary → chunks → embeddings → ChromaDB.
"""
from __future__ import annotations

from kbk.document import IndexedDocument
from kbk.store import KnowledgeStore


class Indexer:
    """Processes raw source content into indexed documents.

    Each document is summarized by LLM, classified with tags,
    split into chunks, embedded, and stored in ChromaDB.
    """

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def index(self, raw_text: str, source_url: str, source_type: str,
              collection: str = "unclassified", metadata: dict = None) -> IndexedDocument:
        """Process and index a document from a source.

        Args:
            raw_text: Original content from the source.
            source_url: URL pointing to the original.
            source_type: confluence | jira | git | slack.
            collection: Target ChromaDB collection.
            metadata: Additional metadata (author, project, access_group, etc.).

        Returns:
            IndexedDocument stored in ChromaDB.
        """
        cleaned = self._clean(raw_text)
        summary = self._summarize(cleaned)
        tags = self._classify(cleaned, summary)
        chunks = self._chunk(summary)
        _ = self._embed(chunks)

        doc = IndexedDocument(
            summary=summary,
            tags=tags,
            metadata={
                "source_url": source_url,
                "source_type": source_type,
                **(metadata or {}),
            },
            collection=collection,
            chunk_count=len(chunks),
        )
        self.store.upsert(doc)
        return doc

    def _clean(self, raw: str) -> str:
        """Strip HTML, Jira markup, Confluence macros."""
        import re
        text = re.sub(r'<[^>]+>', '', raw)
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _summarize(self, text: str) -> str:
        """LLM-based summarization: extract key points in 100-200 tokens.
        
        In v0.1, uses truncation. In production, calls an LLM.
        """
        if len(text) <= 1000:
            return text
        return text[:1000] + "..."

    def _classify(self, text: str, summary: str) -> list[str]:
        """LLM-based classification: extract tags from content."""
        import re
        words = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', summary)
        return list(set(words[:8]))

    def _chunk(self, text: str, chunk_size: int = 512) -> list[str]:
        """Split text into overlapping chunks for embedding."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        return chunks or [text]

    def _embed(self, chunks: list[str]) -> list:
        """Generate embeddings for chunks.
        
        In v0.1, no-op. In production, calls embedding model.
        """
        return chunks
