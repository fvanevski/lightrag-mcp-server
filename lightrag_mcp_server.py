#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LightRAG MCP server (local, full API coverage)

A Model Context Protocol (MCP) server that talks to a locally running LightRAG
HTTP API and exposes tools for **all endpoints** in your OpenAPI spec
(version field "0204").

• Defaults to http://localhost:9621, no auth.
• Reads config from **environment variables or a .env file** (via python-dotenv),
  with CLI flags as highest priority.
• Supports either X-API-Key header or OAuth2 password login (Bearer token).
• Clear, English-only tool descriptions with **example inputs**.
• **Structured outputs** for key tools (e.g., query / query_stream) so clients
  can consume machine-readable results.

Environment variables (optional):
  LIGHTRAG_BASE_URL   → e.g. http://localhost:9621
  LIGHTRAG_API_KEY    → if you started the server with --key

CLI flags (override env):
  --service-url URL   → base URL of LightRAG API (default from env or localhost)
  --key KEY           → API key if the server requires it (default from env)

Quick start:
  pip install mcp requests pydantic python-dotenv
  python lightrag_mcp_server.py --service-url http://localhost:9621

Test queries (from an MCP client):
  {"tool":"query","arguments":{"query":"What did we ingest?","mode":"hybrid","top_k":5}}

Note: streaming (/query/stream) is concatenated into one response string for MCP.
"""

from __future__ import annotations

import os
import sys
import json
import logging
import asyncio
import argparse
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

# Optional JSON content support (newer MCP runtimes). Fallback to text-only.
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent  # base types
    try:
        from mcp.types import JsonContent  # type: ignore
    except Exception:  # older MCP versions may not have JsonContent
        JsonContent = None  # type: ignore
except ImportError as e:
    print("Missing dependency:", e)
    sys.exit(1)

# .env support
try:
    from dotenv import load_dotenv, find_dotenv
    _DOTENV_LOADED = load_dotenv(find_dotenv())
except Exception:
    _DOTENV_LOADED = False

# --------------------------- logging ---------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("LightRAG-MCP")
if _DOTENV_LOADED:
    logger.info("Loaded environment from .env")

# --------------------------- helpers ---------------------------------------

def _as_json_content(obj: Any) -> TextContent:
    """Return JSON content if supported by MCP; otherwise pretty JSON text."""
    if 'JsonContent' in globals() and JsonContent is not None:  # type: ignore
        try:
            return JsonContent(type="json", json=obj)  # type: ignore[arg-type]
        except Exception:
            pass
    return TextContent(type="text", text=json.dumps(obj, indent=2, ensure_ascii=False))

# --------------------------- config ----------------------------------------

def resolve_config() -> tuple[str, Optional[str]]:
    """Resolve LightRAG base URL and optional API key from CLI/env/.env.
    Order of precedence: CLI > environment/.env > defaults.
    Defaults: base_url=http://localhost:9621, api_key=None
    """
    # env (already loaded from .env if present)
    env_base = os.getenv("LIGHTRAG_BASE_URL")
    env_key = os.getenv("LIGHTRAG_API_KEY")

    parser = argparse.ArgumentParser(description="LightRAG MCP server")
    parser.add_argument(
        "--service-url",
        type=str,
        default=env_base or "http://localhost:9621",
        help="LightRAG HTTP base URL (default: env LIGHTRAG_BASE_URL or http://localhost:9621)",
    )
    parser.add_argument(
        "--key",
        type=str,
        default=env_key,
        help="LightRAG API key if enabled (default: env LIGHTRAG_API_KEY)",
    )

    args, _ = parser.parse_known_args()
    base = (args.service_url or "http://localhost:9621").rstrip("/")
    key = args.key or None
    return base, key

# ------------------------- HTTP client -------------------------------------

class LightRagHttpClient:
    """Tiny client for the LightRAG HTTP API (per OpenAPI 0204)."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 150):
        # resolve (CLI/env/.env → defaults)
        self.base_url, self.api_key = resolve_config()
        if base_url:
            self.base_url = base_url.rstrip("/")
        if api_key is not None:
            self.api_key = api_key
        self.timeout = timeout
        self.access_token: Optional[str] = None  # OAuth2 password flow bearer token
        logger.info(f"Using LightRAG at: {self.base_url}")
        if self.api_key:
            logger.info("API key is set via env/CLI")

    # ---------------------- low-level helpers -----------------------------

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.api_key:
            h["X-API-Key"] = self.api_key
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    def _params(self, extra: Optional[dict] = None) -> dict:
        params = dict(extra or {})
        # Some deployments accept API key via query parameter as per OpenAPI
        if self.api_key and "api_key_header_value" not in params:
            params["api_key_header_value"] = self.api_key
        return params

    def _json_or_text(self, r: requests.Response) -> str:
        try:
            return json.dumps(r.json(), indent=2, ensure_ascii=False)
        except Exception:
            return r.text

    def _get(self, path: str, params: Optional[dict] = None, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        r = requests.get(url, headers=self._headers(), params=self._params(params), timeout=self.timeout)
        r.raise_for_status()
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    def _post_json(self, path: str, payload: dict, params: Optional[dict] = None, stream: bool = False, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        r = requests.post(
            url,
            json=payload,
            headers=self._headers(),
            params=self._params(params),
            timeout=self.timeout,
            stream=stream,
        )
        r.raise_for_status()
        if stream:
            chunks = []
            for line in r.iter_lines(decode_unicode=True):
                if line:
                    chunks.append(line)
            data = "
".join(chunks)
            return data if not want_obj else {"raw_stream": data}
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    def _post_multipart(self, path: str, files: List[tuple], params: Optional[dict] = None, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        r = requests.post(url, files=files, headers=self._headers(), params=self._params(params), timeout=self.timeout)
        r.raise_for_status()
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    def _delete(self, path: str, json_body: Optional[dict] = None, params: Optional[dict] = None, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        r = requests.delete(url, headers=self._headers(), params=self._params(params), json=json_body, timeout=self.timeout)
        r.raise_for_status()
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    # ---------------------- auth & health ---------------------------------

    def health(self, want_obj: bool = False) -> Any:
        return self._get("/health", want_obj=want_obj)

    def auth_status(self, want_obj: bool = False) -> Any:
        return self._get("/auth-status", want_obj=want_obj)

    def login(self, username: str, password: str, scope: str = "", want_obj: bool = False) -> Any:
        url = f"{self.base_url}/login"
        data = {"username": username, "password": password, "scope": scope}
        r = requests.post(url, data=data, headers={k: v for k, v in self._headers().items() if k != "Accept"}, timeout=self.timeout)
        r.raise_for_status()
        try:
            payload = r.json()
        except Exception:
            payload = {"raw": r.text}
        # Try to extract bearer token
        token = None
        if isinstance(payload, dict):
            for k in ("access_token", "token", "accessToken"):
                if k in payload:
                    token = payload[k]
                    break
        if token:
            self.access_token = token
        return payload if want_obj else json.dumps(payload, indent=2, ensure_ascii=False)

    # ---------------------- documents -------------------------------------

    def documents_scan(self, want_obj: bool = False) -> Any:
        return self._post_json("/documents/scan", payload={}, want_obj=want_obj)

    def upload_file(self, file_path: str, want_obj: bool = False) -> Any:
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            err = {"error": f"File not found: {file_path}"}
            return err if want_obj else json.dumps(err)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        files = [("file", (p.name, open(p, "rb"), ctype))]
        try:
            return self._post_multipart("/documents/upload", files=files, want_obj=want_obj)
        finally:
            for _, (name, fh, _ct) in files:
                try:
                    fh.close()
                except Exception:
                    pass

    def insert_text(self, text: str, file_source: Optional[str] = None, want_obj: bool = False) -> Any:
        payload = {"text": text}
        if file_source is not None:
            payload["file_source"] = file_source
        return self._post_json("/documents/text", payload, want_obj=want_obj)

    def insert_texts(self, texts: List[str], file_sources: Optional[List[str]] = None, want_obj: bool = False) -> Any:
        payload: Dict[str, Any] = {"texts": list(texts)}
        if file_sources is not None:
            payload["file_sources"] = list(file_sources)
        return self._post_json("/documents/texts", payload, want_obj=want_obj)

    def documents_clear(self, want_obj: bool = False) -> Any:
        return self._delete("/documents", want_obj=want_obj)

    def documents_statuses(self, want_obj: bool = False) -> Any:
        return self._get("/documents", want_obj=want_obj)

    def pipeline_status(self, want_obj: bool = False) -> Any:
        return self._get("/documents/pipeline_status", want_obj=want_obj)

    def delete_document(self, doc_ids: List[str], delete_file: bool = False, want_obj: bool = False) -> Any:
        payload = {"doc_ids": list(doc_ids), "delete_file": bool(delete_file)}
        return self._delete("/documents/delete_document", json_body=payload, want_obj=want_obj)

    def clear_cache(self, want_obj: bool = False) -> Any:
        return self._post_json("/documents/clear_cache", payload={}, want_obj=want_obj)

    def delete_entity(self, entity_name: str, want_obj: bool = False) -> Any:
        payload = {"entity_name": entity_name}
        return self._delete("/documents/delete_entity", json_body=payload, want_obj=want_obj)

    def delete_relation(self, source_entity: str, target_entity: str, want_obj: bool = False) -> Any:
        payload = {"source_entity": source_entity, "target_entity": target_entity}
        return self._delete("/documents/delete_relation", json_body=payload, want_obj=want_obj)

    def track_status(self, track_id: str, want_obj: bool = False) -> Any:
        return self._get(f"/documents/track_status/{track_id}", want_obj=want_obj)

    def documents_paginated(self, request: Dict[str, Any], want_obj: bool = False) -> Any:
        return self._post_json("/documents/paginated", payload=request, want_obj=want_obj)

    def status_counts(self, want_obj: bool = False) -> Any:
        return self._get("/documents/status_counts", want_obj=want_obj)

    # ---------------------- query -----------------------------------------

    def query(self, request: Dict[str, Any], want_obj: bool = True) -> Any:
        # want_obj=True to return structured {response: ...}
        return self._post_json("/query", payload=request, want_obj=want_obj)

    def query_stream(self, request: Dict[str, Any], want_obj: bool = True) -> Any:
        # Returns {raw_stream: "..."} when want_obj=True
        return self._post_json("/query/stream", payload=request, stream=True, want_obj=want_obj)

    # ---------------------- graph -----------------------------------------

    def graph_labels(self, want_obj: bool = False) -> Any:
        return self._get("/graph/label/list", want_obj=want_obj)

    def graphs(self, label: str, max_depth: int = 3, max_nodes: int = 1000, want_obj: bool = False) -> Any:
        params = {"label": label, "max_depth": int(max_depth), "max_nodes": int(max_nodes)}
        return self._get("/graphs", params=params, want_obj=want_obj)

    def entity_exists(self, name: str, want_obj: bool = False) -> Any:
        return self._get("/graph/entity/exists", params={"name": name}, want_obj=want_obj)

    def update_entity(self, entity_name: str, updated_data: Dict[str, Any], allow_rename: bool = False, want_obj: bool = False) -> Any:
        payload = {"entity_name": entity_name, "updated_data": updated_data, "allow_rename": bool(allow_rename)}
        return self._post_json("/graph/entity/edit", payload, want_obj=want_obj)

    def update_relation(self, source_id: str, target_id: str, updated_data: Dict[str, Any], want_obj: bool = False) -> Any:
        payload = {"source_id": source_id, "target_id": target_id, "updated_data": updated_data}
        return self._post_json("/graph/relation/edit", payload, want_obj=want_obj)

    # ---------------------- ollama-compatible ------------------------------

    def api_version(self, want_obj: bool = False) -> Any:
        return self._get("/api/version", want_obj=want_obj)

    def api_tags(self, want_obj: bool = False) -> Any:
        return self._get("/api/tags", want_obj=want_obj)

    def api_ps(self, want_obj: bool = False) -> Any:
        return self._get("/api/ps", want_obj=want_obj)

    def api_generate(self, payload: Dict[str, Any], want_obj: bool = False) -> Any:
        return self._post_json("/api/generate", payload, want_obj=want_obj)

    def api_chat(self, payload: Dict[str, Any], want_obj: bool = False) -> Any:
        return self._post_json("/api/chat", payload, want_obj=want_obj)

# --------------------------- MCP server ------------------------------------

app = Server("lightrag_mcp")
_client: Optional[LightRagHttpClient] = None

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    # Not used in this server.
    return ""

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ---------------- system & auth ----------------
        Tool(
            name="health",
            description=(
                "Get current system status (GET /health).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="auth_status",
            description=(
                "Get authentication status and guest token if auth is not configured (GET /auth-status).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="auth_login",
            description=(
                "Login via OAuth2 password flow (POST /login). Stores Bearer token in-session.
"
                "Example input: {\"username\":\"admin\", \"password\":\"secret\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {"type": "string"},
                    "password": {"type": "string"},
                    "scope": {"type": "string", "default": ""},
                },
                "required": ["username", "password"],
            },
        ),
        # ---------------- documents -------------------
        Tool(
            name="documents_scan",
            description=(
                "Trigger scanning the input directory (POST /documents/scan).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_upload_file",
            description=(
                "Upload **one** file to input dir and index it (POST /documents/upload).
"
                "Example input: {\"file_path\": \"/path/to/file.pdf\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            },
        ),
        Tool(
            name="documents_upload_files",
            description=(
                "Upload multiple files (calls /documents/upload once per file).
"
                "Example input: {\"file_paths\":[\"/a.pdf\", \"/b.md\"]}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_paths": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["file_paths"],
            },
        ),
        Tool(
            name="documents_insert_text",
            description=(
                "Insert a single text (POST /documents/text).
"
                "Example input: {\"text\":\"hello\", \"file_source\":\"notes.txt\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "file_source": {"type": "string"},
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="documents_insert_texts",
            description=(
                "Insert multiple texts (POST /documents/texts).
"
                "Example input: {\"texts\":[\"a\",\"b\"], \"file_sources\":[\"a.txt\",\"b.txt\"]}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "texts": {"type": "array", "items": {"type": "string"}},
                    "file_sources": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["texts"],
            },
        ),
        Tool(
            name="documents_clear_all",
            description=(
                "Clear ALL documents and files (DELETE /documents). Irreversible.
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_list_statuses",
            description=(
                "List documents grouped by processing status (GET /documents).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_pipeline_status",
            description=(
                "Get pipeline status/progress (GET /documents/pipeline_status).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_delete_by_ids",
            description=(
                "Delete specific documents (DELETE /documents/delete_document).
"
                "Example input: {\"doc_ids\":[\"doc_123\"], \"delete_file\": false}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_ids": {"type": "array", "items": {"type": "string"}},
                    "delete_file": {"type": "boolean", "default": False},
                },
                "required": ["doc_ids"],
            },
        ),
        Tool(
            name="documents_clear_cache",
            description=(
                "Clear LLM cache (POST /documents/clear_cache).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_delete_entity",
            description=(
                "Delete an entity from the KG (DELETE /documents/delete_entity).
"
                "Example input: {\"entity_name\":\"Apple Inc.\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {"entity_name": {"type": "string"}},
                "required": ["entity_name"],
            },
        ),
        Tool(
            name="documents_delete_relation",
            description=(
                "Delete a relation from the KG (DELETE /documents/delete_relation).
"
                "Example input: {\"source_entity\":\"A\", \"target_entity\":\"B\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source_entity": {"type": "string"},
                    "target_entity": {"type": "string"},
                },
                "required": ["source_entity", "target_entity"],
            },
        ),
        Tool(
            name="documents_track_status",
            description=(
                "Track processing status by track_id (GET /documents/track_status/{track_id}).
"
                "Example input: {\"track_id\":\"upload_20250729_170612_abc123\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {"track_id": {"type": "string"}},
                "required": ["track_id"],
            },
        ),
        Tool(
            name="documents_paginated",
            description=(
                "Paginated documents query (POST /documents/paginated).
"
                "Example input: {\"page\":1,\"page_size\":50,\"sort_field\":\"updated_at\",\"sort_direction\":\"desc\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status_filter": {"type": "string", "enum": ["pending","processing","processed","failed"]},
                    "page": {"type": "integer", "minimum": 1, "default": 1},
                    "page_size": {"type": "integer", "minimum": 10, "maximum": 200, "default": 50},
                    "sort_field": {"type": "string", "enum": ["created_at","updated_at","id","file_path"], "default": "updated_at"},
                    "sort_direction": {"type": "string", "enum": ["asc","desc"], "default": "desc"},
                },
            },
        ),
        Tool(
            name="documents_status_counts",
            description=(
                "Counts of documents by status (GET /documents/status_counts).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        # ---------------- query ----------------------
        Tool(
            name="query",
            description=(
                "RAG query (POST /query). Returns **structured output**: {request, response}.
"
                "Example input: {\"query\":\"Summarize recent docs\", \"mode\":\"hybrid\", \"top_k\":5, \"only_need_context\": false}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "mode": {"type": "string", "enum": ["local","global","hybrid","naive","mix","bypass"], "default": "mix"},
                    "only_need_context": {"type": "boolean"},
                    "only_need_prompt": {"type": "boolean"},
                    "response_type": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1},
                    "chunk_top_k": {"type": "integer", "minimum": 1},
                    "max_entity_tokens": {"type": "integer", "minimum": 1},
                    "max_relation_tokens": {"type": "integer", "minimum": 1},
                    "max_total_tokens": {"type": "integer", "minimum": 1},
                    "conversation_history": {"type": "array", "items": {"type": "object"}},
                    "history_turns": {"type": "integer", "minimum": 0},
                    "ids": {"type": "array", "items": {"type": "string"}},
                    "user_prompt": {"type": "string"},
                    "enable_rerank": {"type": "boolean"}
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="query_stream",
            description=(
                "Streamed RAG query (POST /query/stream). Returns **structured output**: {request, stream}.
"
                "Example input: {\"query\":\"Show citations\", \"mode\":\"hybrid\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "mode": {"type": "string", "enum": ["local","global","hybrid","naive","mix","bypass"], "default": "mix"}
                },
                "required": ["query"],
            },
        ),
        # ---------------- graph ----------------------
        Tool(
            name="graph_labels",
            description=(
                "List graph labels (GET /graph/label/list).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="graphs_get",
            description=(
                "Retrieve subgraph by label (GET /graphs).
"
                "Example input: {\"label\":\"OpenAI\", \"max_depth\":3, \"max_nodes\":100}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "max_depth": {"type": "integer", "minimum": 1, "default": 3},
                    "max_nodes": {"type": "integer", "minimum": 1, "default": 1000},
                },
                "required": ["label"],
            },
        ),
        Tool(
            name="graph_entity_exists",
            description=(
                "Check if an entity exists (GET /graph/entity/exists).
"
                "Example input: {\"name\":\"Apple Inc.\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        ),
        Tool(
            name="graph_update_entity",
            description=(
                "Update entity properties (POST /graph/entity/edit).
"
                "Example input: {\"entity_name\":\"Apple\", \"updated_data\":{\"aliases\":[\"Apple Inc\"]}, \"allow_rename\": false}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string"},
                    "updated_data": {"type": "object", "additionalProperties": True},
                    "allow_rename": {"type": "boolean", "default": False},
                },
                "required": ["entity_name", "updated_data"],
            },
        ),
        Tool(
            name="graph_update_relation",
            description=(
                "Update relation properties (POST /graph/relation/edit).
"
                "Example input: {\"source_id\":\"e1\", \"target_id\":\"e2\", \"updated_data\":{\"weight\":0.9}}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "updated_data": {"type": "object", "additionalProperties": True},
                },
                "required": ["source_id", "target_id", "updated_data"],
            },
        ),
        # --------------- ollama-compatible -----------
        Tool(
            name="ollama_version",
            description=(
                "Get Ollama version info (GET /api/version).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ollama_tags",
            description=(
                "List available models (GET /api/tags).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ollama_ps",
            description=(
                "List running models (GET /api/ps).
"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ollama_generate",
            description=(
                "Direct completion to underlying LLM (POST /api/generate).
"
                "Example input: {\"model\":\"qwen\", \"prompt\":\"Hello\"}"
            ),
            inputSchema={
                "type": "object",
                "properties": {"payload": {"type": "object", "additionalProperties": True}},
                "required": ["payload"],
            },
        ),
        Tool(
            name="ollama_chat",
            description=(
                "Chat completion (POST /api/chat).
"
                "Example input: {\"payload\": {\"model\":\"qwen\", \"messages\":[{\"role\":\"user\", \"content\":\"hi\"}]}}"
            ),
            inputSchema={
                "type": "object",
                "properties": {"payload": {"type": "object", "additionalProperties": True}},
                "required": ["payload"],
            },
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    global _client
    if _client is None:
        _client = LightRagHttpClient()

    try:
        # -------- system & auth --------
        if name == "health":
            return [_as_json_content({"result": _client.health(want_obj=True)})]
        if name == "auth_status":
            return [_as_json_content({"result": _client.auth_status(want_obj=True)})]
        if name == "auth_login":
            username = arguments.get("username")
            password = arguments.get("password")
            scope = arguments.get("scope", "")
            if not username or not password:
                raise ValueError("'username' and 'password' are required")
            payload = _client.login(username, password, scope, want_obj=True)
            return [_as_json_content({"result": payload})]

        # -------- documents --------
        if name == "documents_scan":
            return [_as_json_content({"result": _client.documents_scan(want_obj=True)})]
        if name == "documents_upload_file":
            fp = arguments.get("file_path")
            if not fp:
                raise ValueError("'file_path' is required")
            return [_as_json_content({"file": fp, "result": _client.upload_file(fp, want_obj=True)})]
        if name == "documents_upload_files":
            fps = arguments.get("file_paths")
            if not fps or not isinstance(fps, list):
                raise ValueError("'file_paths' must be a non-empty list")
            results = []
            for p in fps:
                results.append({"file": p, "result": _client.upload_file(p, want_obj=True)})
            return [_as_json_content({"results": results})]
        if name == "documents_insert_text":
            text = arguments.get("text")
            if not text:
                raise ValueError("'text' is required")
            file_source = arguments.get("file_source")
            return [_as_json_content({"result": _client.insert_text(text, file_source, want_obj=True)})]
        if name == "documents_insert_texts":
            texts = arguments.get("texts")
            if not texts or not isinstance(texts, list):
                raise ValueError("'texts' must be a non-empty list of strings")
            file_sources = arguments.get("file_sources")
            return [_as_json_content({"result": _client.insert_texts(texts, file_sources, want_obj=True)})]
        if name == "documents_clear_all":
            return [_as_json_content({"result": _client.documents_clear(want_obj=True)})]
        if name == "documents_list_statuses":
            return [_as_json_content({"result": _client.documents_statuses(want_obj=True)})]
        if name == "documents_pipeline_status":
            return [_as_json_content({"result": _client.pipeline_status(want_obj=True)})]
        if name == "documents_delete_by_ids":
            doc_ids = arguments.get("doc_ids")
            if not doc_ids or not isinstance(doc_ids, list):
                raise ValueError("'doc_ids' must be a non-empty list of strings")
            delete_file = bool(arguments.get("delete_file", False))
            return [_as_json_content({"result": _client.delete_document(doc_ids, delete_file, want_obj=True)})]
        if name == "documents_clear_cache":
            return [_as_json_content({"result": _client.clear_cache(want_obj=True)})]
        if name == "documents_delete_entity":
            en = arguments.get("entity_name")
            if not en:
                raise ValueError("'entity_name' is required")
            return [_as_json_content({"result": _client.delete_entity(en, want_obj=True)})]
        if name == "documents_delete_relation":
            se = arguments.get("source_entity")
            te = arguments.get("target_entity")
            if not se or not te:
                raise ValueError("'source_entity' and 'target_entity' are required")
            return [_as_json_content({"result": _client.delete_relation(se, te, want_obj=True)})]
        if name == "documents_track_status":
            track_id = arguments.get("track_id")
            if not track_id:
                raise ValueError("'track_id' is required")
            return [_as_json_content({"track_id": track_id, "result": _client.track_status(track_id, want_obj=True)})]
        if name == "documents_paginated":
            req = {k: v for k, v in arguments.items()}
            return [_as_json_content({"request": req, "result": _client.documents_paginated(req, want_obj=True)})]
        if name == "documents_status_counts":
            return [_as_json_content({"result": _client.status_counts(want_obj=True)})]

        # -------- query (structured outputs) --------
        if name == "query":
            req = {k: v for k, v in arguments.items()}
            if "query" not in req:
                raise ValueError("'query' is required")
            qres = _client.query(req, want_obj=True)
            # Expected schema: {"response": "..."}
            if isinstance(qres, dict) and "response" in qres:
                out = {"request": req, "response": qres["response"]}
            else:
                out = {"request": req, "response": qres}
            return [_as_json_content(out)]

        if name == "query_stream":
            req = {k: v for k, v in arguments.items()}
            if "query" not in req:
                raise ValueError("'query' is required")
            sres = _client.query_stream(req, want_obj=True)
            # sres is {"raw_stream": "..."}
            stream_text = sres.get("raw_stream") if isinstance(sres, dict) else str(sres)
            out = {"request": req, "stream": stream_text}
            return [_as_json_content(out)]

        # -------- graph --------
        if name == "graph_labels":
            return [_as_json_content({"result": _client.graph_labels(want_obj=True)})]
        if name == "graphs_get":
            label = arguments.get("label")
            if not label:
                raise ValueError("'label' is required")
            md = int(arguments.get("max_depth", 3))
            mn = int(arguments.get("max_nodes", 1000))
            return [_as_json_content({"label": label, "result": _client.graphs(label, md, mn, want_obj=True)})]
        if name == "graph_entity_exists":
            name_ = arguments.get("name")
            if not name_:
                raise ValueError("'name' is required")
            return [_as_json_content({"name": name_, "result": _client.entity_exists(name_, want_obj=True)})]
        if name == "graph_update_entity":
            en = arguments.get("entity_name")
            data = arguments.get("updated_data")
            allow = bool(arguments.get("allow_rename", False))
            if not en or data is None:
                raise ValueError("'entity_name' and 'updated_data' are required")
            return [_as_json_content({"result": _client.update_entity(en, data, allow, want_obj=True)})]
        if name == "graph_update_relation":
            sid = arguments.get("source_id")
            tid = arguments.get("target_id")
            data = arguments.get("updated_data")
            if not sid or not tid or data is None:
                raise ValueError("'source_id', 'target_id', 'updated_data' are required")
            return [_as_json_content({"result": _client.update_relation(sid, tid, data, want_obj=True)})]

        # -------- ollama-compatible --------
        if name == "ollama_version":
            return [_as_json_content({"result": _client.api_version(want_obj=True)})]
        if name == "ollama_tags":
            return [_as_json_content({"result": _client.api_tags(want_obj=True)})]
        if name == "ollama_ps":
            return [_as_json_content({"result": _client.api_ps(want_obj=True)})]
        if name == "ollama_generate":
            payload = arguments.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("'payload' (object) is required")
            return [_as_json_content({"request": payload, "result": _client.api_generate(payload, want_obj=True)})]
        if name == "ollama_chat":
            payload = arguments.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("'payload' (object) is required")
            return [_as_json_content({"request": payload, "result": _client.api_chat(payload, want_obj=True)})]

        raise ValueError(f"Unknown tool: {name}")

    except requests.HTTPError as e:
        logger.error("HTTP error in tool '%s': %s", name, e, exc_info=True)
        return [TextContent(type="text", text=f"HTTP error: {e}")]
    except Exception as e:
        logger.error("Tool '%s' failed: %s", name, e, exc_info=True)
        return [TextContent(type="text", text=f"Error: {e}")]

# --------------------------- entrypoint ------------------------------------

async def main():
    from mcp.server.stdio import stdio_server

    base, key = resolve_config()
    logger.info("Starting LightRAG MCP server …")
    logger.info("Base URL: %s", base)
    logger.info("API Key: %s", "<set>" if key else "<none>")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )

if __name__ == "__main__":
    asyncio.run(main())
