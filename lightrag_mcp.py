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
  pip install mcp httpx pydantic python-dotenv
  python lightrag_mcp.py --service-url http://localhost:9621

Test queries (from an MCP client):
  {"tool":"query","arguments":{"query":"What did we ingest?","mode":"hybrid","top_k":5}}

Note: streaming (/query/stream) is concatenated into one response string for MCP.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Optional

import httpx
from dotenv import load_dotenv, find_dotenv

from client import LightRagHttpClient
from config import resolve_config
from models import QueryRequest
from tools import list_tools

# Optional JSON content support (newer MCP runtimes). Fallback to text-only.
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, AnyUrl  # base types

except ImportError as e:
    print("Missing dependency:", e)
    sys.exit(1)

# .env support
_DOTENV_LOADED = load_dotenv(find_dotenv())

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
    JsonContent = globals().get('JsonContent')
    if JsonContent is not None:
        try:
            return JsonContent(type="json", json=obj)
        except Exception:
            pass
    return TextContent(type="text", text=json.dumps(obj, indent=2, ensure_ascii=False))


# --------------------------- MCP server ------------------------------------

app = Server("lightrag_mcp")


@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    # Not used in this server.
    return ""


@app.list_tools()
async def list_tools_mcp() -> list[Tool]:
    return list_tools()


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    client = LightRagHttpClient()
    try:
        # -------- system & auth --------
        if name == "health":
            return [_as_json_content({"result": await client.health(want_obj=True)})]
        if name == "auth_status":
            return [_as_json_content({"result": await client.auth_status(want_obj=True)})]
        if name == "auth_login":
            username = arguments.get("username")
            password = arguments.get("password")
            scope = arguments.get("scope", "")
            if not username or not password:
                raise ValueError("'username' and 'password' are required")
            payload = await client.login(username, password, scope, want_obj=True)
            return [_as_json_content({"result": payload})]

        # -------- documents --------
        if name == "documents_scan":
            return [_as_json_content({"result": await client.documents_scan(want_obj=True)})]
        if name == "documents_upload_file":
            fp = arguments.get("file_path")
            if not fp:
                raise ValueError("'file_path' is required")
            return [_as_json_content({"file": fp, "result": await client.upload_file(fp, want_obj=True)})]
        if name == "documents_upload_files":
            fps = arguments.get("file_paths")
            if not fps or not isinstance(fps, list):
                raise ValueError("'file_paths' must be a non-empty list")
            tasks = [asyncio.create_task(client.upload_file(p, want_obj=True)) for p in fps]
            results = await asyncio.gather(*tasks)
            return [_as_json_content({"results": results})]
        if name == "documents_insert_text":
            text = arguments.get("text")
            if not text:
                raise ValueError("'text' is required")
            file_source = arguments.get("file_source")
            return [_as_json_content({"result": await client.insert_text(text, file_source, want_obj=True)})]
        if name == "documents_insert_texts":
            texts = arguments.get("texts")
            if not texts or not isinstance(texts, list):
                raise ValueError("'texts' must be a non-empty list of strings")
            file_sources = arguments.get("file_sources")
            return [_as_json_content({"result": await client.insert_texts(texts, file_sources, want_obj=True)})]
        if name == "documents_clear_all":
            return [_as_json_content({"result": await client.documents_clear(want_obj=True)})]
        if name == "documents_list_statuses":
            return [_as_json_content({"result": await client.documents_statuses(want_obj=True)})]
        if name == "documents_pipeline_status":
            return [_as_json_content({"result": await client.pipeline_status(want_obj=True)})]
        if name == "documents_delete_by_ids":
            doc_ids = arguments.get("doc_ids")
            if not doc_ids or not isinstance(doc_ids, list):
                raise ValueError("'doc_ids' must be a non-empty list of strings")
            delete_file = bool(arguments.get("delete_file", False))
            return [_as_json_content({"result": await client.delete_document(doc_ids, delete_file, want_obj=True)})]
        if name == "documents_clear_cache":
            return [_as_json_content({"result": await client.clear_cache(want_obj=True)})]
        if name == "documents_delete_entity":
            en = arguments.get("entity_name")
            if not en:
                raise ValueError("'entity_name' is required")
            return [_as_json_content({"result": await client.delete_entity(en, want_obj=True)})]
        if name == "documents_delete_relation":
            se = arguments.get("source_entity")
            te = arguments.get("target_entity")
            if not se or not te:
                raise ValueError("'source_entity' and 'target_entity' are required")
            return [_as_json_content({"result": await client.delete_relation(se, te, want_obj=True)})]
        if name == "documents_track_status":
            track_id = arguments.get("track_id")
            if not track_id:
                raise ValueError("'track_id' is required")
            return [_as_json_content({"track_id": track_id, "result": await client.track_status(track_id, want_obj=True)})]
        if name == "documents_paginated":
            req = {k: v for k, v in arguments.items()}
            return [_as_json_content({"request": req, "result": await client.documents_paginated(req, want_obj=True)})]
        if name == "documents_status_counts":
            return [_as_json_content({"result": await client.status_counts(want_obj=True)})]

        # -------- query (structured outputs) --------
        if name == "query":
            try:
                req = QueryRequest(**arguments).model_dump(exclude_unset=True)
            except Exception as e:
                raise ValueError(f"Invalid query arguments: {e}")
            qres = await client.query(req, want_obj=True)
            # Expected schema: {"response": "..."}
            if isinstance(qres, dict) and "response" in qres:
                response_text = qres["response"]
            else:
                response_text = str(qres)
            return [TextContent(type="text", text=response_text)]

        if name == "query_stream":
            try:
                req = QueryRequest(**arguments).model_dump(exclude_unset=True)
            except Exception as e:
                raise ValueError(f"Invalid query arguments: {e}")
            sres = await client.query_stream(req, want_obj=True)
            # sres is {"raw_stream": "..."}
            stream_text = sres.get("raw_stream") if isinstance(sres, dict) else str(sres)
            out = {"request": req, "stream": stream_text}
            return [_as_json_content(out)]

        # -------- graph --------
        if name == "graph_labels":
            return [_as_json_content({"result": await client.graph_labels(want_obj=True)})]
        if name == "graphs_get":
            label = arguments.get("label")
            if not label:
                raise ValueError("'label' is required")
            md = int(arguments.get("max_depth", 3))
            mn = int(arguments.get("max_nodes", 1000))
            return [_as_json_content({"label": label, "result": await client.graphs(label, md, mn, want_obj=True)})]
        if name == "graph_entity_exists":
            name_ = arguments.get("name")
            if not name_:
                raise ValueError("'name' is required")
            return [_as_json_content({"name": name_, "result": await client.entity_exists(name_, want_obj=True)})]
        if name == "graph_update_entity":
            en = arguments.get("entity_name")
            data = arguments.get("updated_data")
            allow = bool(arguments.get("allow_rename", False))
            if not en or data is None:
                raise ValueError("'entity_name' and 'updated_data' are required")
            return [_as_json_content({"result": await client.update_entity(en, data, allow, want_obj=True)})]
        if name == "graph_update_relation":
            sid = arguments.get("source_id")
            tid = arguments.get("target_id")
            data = arguments.get("updated_data")
            if not sid or not tid or data is None:
                raise ValueError("'source_id', 'target_id', 'updated_data' are required")
            return [_as_json_content({"result": await client.update_relation(sid, tid, data, want_obj=True)})]

        # -------- ollama-compatible --------
        if name == "ollama_version":
            return [_as_json_content({"result": await client.api_version(want_obj=True)})]
        if name == "ollama_tags":
            return [_as_json_content({"result": await client.api_tags(want_obj=True)})]
        if name == "ollama_ps":
            return [_as_json_content({"result": await client.api_ps(want_obj=True)})]
        if name == "ollama_generate":
            payload = arguments.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("'payload' (object) is required")
            return [_as_json_content({"request": payload, "result": await client.api_generate(payload, want_obj=True)})]
        if name == "ollama_chat":
            payload = arguments.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("'payload' (object) is required")
            return [_as_json_content({"request": payload, "result": await client.api_chat(payload, want_obj=True)})]

        raise ValueError(f"Unknown tool: {name}")

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error in tool '%s': %s", name, e, exc_info=True)
        return [TextContent(type="text", text=f"HTTP error: {e.response.status_code} {e.response.reason_phrase}")]
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

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())