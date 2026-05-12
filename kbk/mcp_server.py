"""MCP Server for KBK — gives LLMs fast semantic access to indexed knowledge.

Implements the Model Context Protocol (stdio transport).
Tools: search_knowledge, get_document_summary, list_collections.
"""
from __future__ import annotations
import json
import sys
from typing import Any

from kbk.store import KnowledgeStore
from kbk.config import KBKConfig


class KBKMCPServer:
    """MCP server that exposes KBK index to LLMs via stdio transport.

    Protocol: JSON-RPC 2.0 over stdin/stdout.
    """

    def __init__(self, store: KnowledgeStore):
        self.store = store
        self.tools = {
            "search_knowledge": self._handle_search,
            "get_document_summary": self._handle_summary,
            "list_collections": self._handle_list_collections,
        }

    def _read_request(self) -> dict | None:
        line = sys.stdin.readline()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _send_response(self, req_id: Any, result: Any = None, error: Any = None):
        resp = {"jsonrpc": "2.0", "id": req_id}
        if error:
            resp["error"] = {"code": -32000, "message": str(error)}
        else:
            resp["result"] = result
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

    def _handle_search(self, params: dict) -> dict:
        query = params.get("query", "")
        collection = params.get("collection")
        limit = params.get("limit", 10)
        results = self.store.search(query, n_results=limit, collection_filter=collection)
        return {
            "results": [
                {
                    "id": c.id,
                    "source_url": c.source_url,
                    "content": c.content[:500],
                    "summary": c.summary,
                    "tags": c.tags,
                    "access_group": c.access_group,
                }
                for c in results
            ],
            "count": len(results),
        }

    def _handle_summary(self, params: dict) -> dict:
        collection = params.get("collection", "default")
        limit = params.get("limit", 20)
        chunks = self.store.list_chunks(collection=collection, limit=limit)
        return {
            "documents": [
                {
                    "id": c.id,
                    "source_url": c.source_url,
                    "summary": c.summary,
                    "tags": c.tags,
                }
                for c in chunks
            ],
            "count": len(chunks),
        }

    def _handle_list_collections(self, params: dict = None) -> dict:
        return {"collections": self.store.list_collections()}

    def run(self):
        """Main MCP event loop. Reads JSON-RPC from stdin, writes to stdout."""
        import sys
        # Send initialize response
        self._send_response(None, {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "tools": {
                    "search_knowledge": {
                        "description": "Search indexed enterprise knowledge semantically",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "collection": {"type": "string", "description": "Filter by collection"},
                                "limit": {"type": "integer", "description": "Max results"},
                            },
                            "required": ["query"],
                        },
                    },
                    "get_document_summary": {
                        "description": "Get summaries of indexed documents",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "collection": {"type": "string"},
                                "limit": {"type": "integer"},
                            },
                        },
                    },
                    "list_collections": {
                        "description": "List available collections",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                },
            },
        })

        while True:
            req = self._read_request()
            if req is None:
                break
            method = req.get("method", "")
            req_id = req.get("id", None)
            params = req.get("params", {})

            if method == "initialize":
                self._send_response(req_id, {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                })
            elif method == "ping":
                self._send_response(req_id, {})
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                handler = self.tools.get(tool_name)
                if handler:
                    try:
                        result = handler(tool_args)
                        self._send_response(req_id, {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]})
                    except Exception as e:
                        self._send_response(req_id, error=str(e))
                else:
                    self._send_response(req_id, error=f"Unknown tool: {tool_name}")
            else:
                self._send_response(req_id, {})
