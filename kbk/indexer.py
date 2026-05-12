"""AI Pipeline for KBK — clean, summarize, chunk, classify."""
from __future__ import annotations
import json
import re
import urllib.request
from typing import Optional

from kbk.models import IndexedChunk
from kbk.store import KnowledgeStore
from kbk.state import StateTracker


class Indexer:
    """ETL pipeline: clean HTML → LLM summarize → classify → chunk → embed."""

    def __init__(self, store: KnowledgeStore, state: StateTracker,
                 llm_api_key: str = "", llm_model: str = "gpt-4o-mini",
                 llm_base_url: str = "https://api.openai.com/v1"):
        self.store = store
        self.state = state
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url.rstrip("/")
        self.cost_log: list[dict] = []

    def clean_html(self, html: str) -> str:
        """Strip Confluence HTML to clean text."""
        text = re.sub(r'<ac:[^>]+>[^<]*</ac:[^>]+>', '', html)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def summarize(self, text: str, title: str = "") -> str:
        """Call LLM to extract a concise summary. Falls back to truncation."""
        if not self.llm_api_key or len(text) < 200:
            preview = text[:300].strip()
            return preview + "..." if len(text) > 300 else preview

        prompt = f"Summarize this document in 2-3 sentences. Title: {title}\n\n{text[:4000]}"
        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200, "temperature": 0.3,
        }
        try:
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self.llm_base_url}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.llm_api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode())
                content = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                self.cost_log.append({
                    "model": self.llm_model,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                })
                return content.strip()
        except Exception:
            return text[:300] + "..." if len(text) > 300 else text

    def classify(self, text: str, summary: str) -> list[str]:
        """Extract tags from text. Uses LLM if available, else heuristics."""
        if self.llm_api_key:
            prompt = f"Extract 3-5 tags from this document. Return ONLY a JSON array of strings.\n\n{summary}"
            payload = {
                "model": self.llm_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100, "temperature": 0.1,
            }
            try:
                data = json.dumps(payload).encode()
                req = urllib.request.Request(
                    f"{self.llm_base_url}/chat/completions",
                    data=data, headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.llm_api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode())
                    content = result["choices"][0]["message"]["content"].strip()
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        return re.findall(r'\w+', content)[:5]
            except Exception:
                pass
        words = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', summary)
        return list(set(w.lower() for w in words[:8]))

    def chunk(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
        """Split text into overlapping chunks anchored to headings."""
        try:
            import nltk
            try:
                sentences = nltk.sent_tokenize(text)
            except LookupError:
                sentences = text.replace('\n', ' ').split('. ')
        except ImportError:
            sentences = text.replace('\n', ' ').split('. ')
        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) > chunk_size and current:
                chunks.append(current.strip())
                current = current[-overlap:] + " " + s
            else:
                current += " " + s
        if current.strip():
            chunks.append(current.strip())
        return chunks or [text]

    def process_document(self, url: str, raw_html: str, title: str = "",
                         access_group: str = "public",
                         collection: str = "unclassified",
                         content_hash: str = "") -> list[IndexedChunk]:
        """Process a single document through the ETL pipeline."""
        cleaned = self.clean_html(raw_html)
        summary = self.summarize(cleaned, title)
        tags = self.classify(cleaned, summary)
        chunks_text = self.chunk(cleaned)

        chunks = []
        for i, chunk_text in enumerate(chunks_text):
            chunk = IndexedChunk(
                source_url=url,
                content=chunk_text,
                summary=summary,
                tags=tags,
                access_group=access_group,
                content_hash=content_hash or StateTracker.hash_content(raw_html),
                collection=collection,
            )
            chunk.id = StateTracker.hash_content(f"{url}:chunk:{i}")
            self.store.upsert_chunk(chunk)
            chunks.append(chunk)
        return chunks

    @property
    def total_cost_estimate(self) -> dict:
        total_prompt = sum(c.get("prompt_tokens", 0) for c in self.cost_log)
        total_completion = sum(c.get("completion_tokens", 0) for c in self.cost_log)
        return {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "estimated_cost_usd": round(total_prompt * 0.00015 / 1000 + total_completion * 0.0006 / 1000, 4),
        }
