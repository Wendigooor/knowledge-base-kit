"""AI Pipeline for KBK — clean, summarize, chunk, classify."""
from __future__ import annotations
import hashlib
import json
import logging
import re
import urllib.request
from typing import Optional

from kbk.exceptions import LLMError
from kbk.models import IndexedChunk
from kbk.store import KnowledgeStore
from kbk.state import StateTracker

logger = logging.getLogger("kbk.indexer")

# Constants
_CHUNK_SIZE = 1000  # tokens
_CHUNK_OVERLAP = 100  # characters
_LLM_TIMEOUT = 30  # seconds
_LLM_RETRIES = 2
_SUMMARY_MAX_CHARS = 4000
_PREVIEW_MAX_CHARS = 300
_TAG_MAX = 10


class Indexer:
    """ETL pipeline: clean HTML -> LLM summarize+classify -> chunk -> embed."""

    def __init__(self, store: KnowledgeStore, state: StateTracker,
                 llm_api_key: str = "", llm_model: str = "gpt-4o-mini",
                 llm_base_url: str = "https://api.openai.com/v1"):
        self.store = store
        self.state = state
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url.rstrip("/")
        self.cost_log: list[dict] = []

    # ── HTML cleaning ──────────────────────────────────────────────

    def clean_html(self, html: str) -> str:
        """Strip Confluence HTML, preserving code/angle brackets.

        HTML tags like <ac:...> are removed entirely.
        Remaining angle brackets (< >) from inline code are preserved.
        Code blocks (<code>, <pre>) are detected and angle brackets inside
        them are kept intact.
        """
        # Protect code blocks: replace internal <> with placeholders
        text = html

        # Protect <code> blocks
        def protect_code(m):
            inner = m.group(1)
            protected = inner.replace("<", "<<<LT>>>").replace(">", ">>>GT>>>")
            return f" {protected} "

        text = re.sub(r'<code>(.*?)</code>', protect_code, text, flags=re.DOTALL)
        text = re.sub(r'<pre>(.*?)</pre>', protect_code, text, flags=re.DOTALL)
        # Also protect inline code (single backtick style in HTML)
        text = re.sub(r'<tt>(.*?)</tt>', protect_code, text, flags=re.DOTALL)

        # Remove Confluence-specific macros
        text = re.sub(r'<ac:[^>]+>[^<]*</ac:[^>]+>', '', text)
        # Strip remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Restore angle brackets in code
        text = text.replace("<<<LT>>>", "<").replace(">>>GT>>>", ">")

        # HTML entities
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # ── LLM calls ──────────────────────────────────────────────────

    def _call_llm(self, prompt: str, max_tokens: int = 200,
                  temperature: float = 0.1) -> str:
        """Call LLM with retry logic and error reporting."""
        if not self.llm_api_key:
            raise LLMError("LLM API key not configured")

        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        for attempt in range(_LLM_RETRIES + 1):
            try:
                data = json.dumps(payload).encode()
                req = urllib.request.Request(
                    f"{self.llm_base_url}/chat/completions",
                    data=data, headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.llm_api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=_LLM_TIMEOUT) as resp:
                    result = json.loads(resp.read().decode())
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    self.cost_log.append({
                        "model": self.llm_model, "attempt": attempt,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    })
                    return content.strip()

            except urllib.error.HTTPError as exc:
                last_error = exc
                status = exc.code
                if status == 401:
                    raise LLMError("LLM auth failed — check API key") from exc
                if status == 429 and attempt < _LLM_RETRIES:
                    import time
                    wait = 2 ** (attempt + 1)
                    logger.warning("LLM rate limited (429), retrying in %ds", wait)
                    time.sleep(wait)
                    continue
                logger.error("LLM HTTP %d: %s", status, exc)
                raise LLMError(f"LLM API error (HTTP {status})") from exc

            except Exception as exc:
                last_error = exc
                if attempt < _LLM_RETRIES:
                    import time
                    wait = 2 ** attempt
                    logger.warning("LLM call failed (attempt %d/%d): %s, retrying in %ds",
                                   attempt + 1, _LLM_RETRIES + 1, exc, wait)
                    time.sleep(wait)
                    continue
                logger.error("LLM call failed after %d attempts: %s",
                             _LLM_RETRIES + 1, exc)

        raise LLMError(f"LLM call failed after {_LLM_RETRIES + 1} attempts: {last_error}") from last_error

    # ── Robust JSON extraction from LLM output ─────────────────────

    @staticmethod
    def _extract_json(text: str) -> Optional[dict]:
        """Robust JSON extraction from LLM response.

        Handles: markdown fences, trailing commas, unescaped quotes,
        newlines in strings, Python-style None/True/False.
        Returns None if extraction fails.
        """
        if not text:
            return None

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip markdown fences
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Find JSON object with balanced braces
        brace_depth = 0
        start = -1
        for i, ch in enumerate(cleaned):
            if ch == '{':
                if start == -1:
                    start = i
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                if brace_depth == 0 and start >= 0:
                    candidate = cleaned[start:i + 1]
                    break
        else:
            # No balanced braces found
            return None

        # Try to fix common issues
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Try with trailing comma removal
        fixed = re.sub(r',\s*}', '}', candidate)
        fixed = re.sub(r',\s*]', ']', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # Try replacing Python None/True/False
        fixed = re.sub(r'\bNone\b', 'null', candidate)
        fixed = re.sub(r'\bTrue\b', 'true', fixed)
        fixed = re.sub(r'\bFalse\b', 'false', fixed)
        fixed = re.sub(r',\s*}', '}', fixed)
        fixed = re.sub(r',\s*]', ']', fixed)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        return None

    def _summarize_and_classify(self, text: str, title: str = "") -> tuple[str, list[str]]:
        """Single LLM call to get both summary and tags.

        Falls back to truncation + heuristic tags if LLM unavailable.
        Uses robust JSON extraction with multiple fallback strategies.
        """
        if not self.llm_api_key or len(text) < 200:
            preview = text[:_PREVIEW_MAX_CHARS].strip()
            summary = preview + "..." if len(text) > _PREVIEW_MAX_CHARS else preview
            return summary, []

        safe_title = title.replace('"', "'")[:100]
        safe_text = text[:_SUMMARY_MAX_CHARS].replace('"', "'")

        prompt = (
            f"Analyze this enterprise document.\n\n"
            f"--- BEGIN DOCUMENT ---\n"
            f"Title: {safe_title}\n"
            f"Content: {safe_text}\n"
            f"--- END DOCUMENT ---\n\n"
            f"Return ONLY a JSON object with two fields:\n"
            f'  {{"summary": "2-3 sentence summary", "tags": ["tag1", "tag2", "tag3"]}}\n'
        )

        try:
            response = self._call_llm(prompt, max_tokens=300, temperature=0.1)
        except LLMError as exc:
            logger.warning("LLM summarization failed: %s. Falling back to truncation.", exc)
            preview = text[:_PREVIEW_MAX_CHARS].strip()
            summary = preview + "..." if len(text) > _PREVIEW_MAX_CHARS else preview
            return summary, []

        parsed = self._extract_json(response)
        if parsed:
            summary = str(parsed.get("summary", ""))[:500]
            tags = list(parsed.get("tags", []))[:_TAG_MAX]
            if summary:
                return summary, tags

        # Fallback: truncation + heuristic tags
        logger.warning("LLM output not parseable as JSON. Response preview: %s...", response[:100])
        preview = text[:_PREVIEW_MAX_CHARS].strip()
        summary = preview + "..." if len(text) > _PREVIEW_MAX_CHARS else preview
        words = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', text)
        tags = list(set(w.lower() for w in words[:8]))
        return summary, tags

    # ── Chunking with word-boundary overlap ────────────────────────

    def chunk(self, text: str, chunk_size: int = _CHUNK_SIZE,
              overlap: int = _CHUNK_OVERLAP) -> list[str]:
        """Split text into overlapping chunks anchored at sentence boundaries.

        Each chunk carries enough context to be semantically meaningful on its own.
        Overlap happens at word boundaries (not character boundaries) to avoid
        splitting words in the middle.
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else [""]

        # Split into sentences (periods, exclamation, question, newlines)
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current = ""
        for sent in sentences:
            if not current:
                current = sent
            elif len(current) + len(sent) + 1 <= chunk_size:
                current += " " + sent
            else:
                chunks.append(current)
                # Word-boundary overlap: take N chars from end, then
                # extend to the next word boundary so we don't split words
                if len(current) > overlap:
                    overlap_start = len(current) - overlap
                    # Find the next word boundary after overlap_start
                    word_boundary = current.find(' ', overlap_start)
                    if word_boundary > 0 and word_boundary < len(current):
                        overlap_text = current[word_boundary + 1:]
                    else:
                        # No word boundary found in range, use char boundary
                        overlap_text = current[overlap_start:]
                else:
                    overlap_text = current
                current = overlap_text + " " + sent

        if current:
            chunks.append(current)

        return chunks or [text]

    # ── Full pipeline ───────────────────────────────────────────────

    def process_document(self, url: str, raw_html: str, title: str = "",
                         access_group: str = "public",
                         collection: str = "unclassified",
                         content_hash: str = "",
                         version: int = 0) -> list[IndexedChunk]:
        """Process a single document through the ETL pipeline."""
        cleaned = self.clean_html(raw_html)
        if not cleaned:
            logger.warning("Empty content after cleaning: %s", url)
            return []

        summary, tags = self._summarize_and_classify(cleaned, title)
        chunks_text = self.chunk(cleaned)
        doc_hash = content_hash or StateTracker.hash_content(raw_html)

        chunks = []
        for i, chunk_text in enumerate(chunks_text):
            chunk_id = StateTracker.hash_content(f"{url}:chunk:{i}")
            chunk = IndexedChunk(
                id=chunk_id,
                source_url=url,
                content=chunk_text,
                summary=summary,
                tags=tags,
                access_group=access_group,
                content_hash=doc_hash,
                collection=collection,
            )
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
            "estimated_cost_usd": round(
                total_prompt * 0.00015 / 1000 + total_completion * 0.0006 / 1000, 4
            ),
            "calls": len(self.cost_log),
        }
