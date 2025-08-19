from mcp.types import Tool
from models import QueryRequest

def list_tools() -> list[Tool]:
    return [
        # ---------------- system & auth ----------------
        Tool(
            name="health",
            description=(
                "Get current system status (GET /health).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="auth_status",
            description=(
                "Get authentication status and guest token if auth is not configured (GET /auth-status).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="auth_login",
            description=(
                "Login via OAuth2 password flow (POST /login). Stores Bearer token in-session.\n"
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
                "Trigger scanning the input directory (POST /documents/scan).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_upload_file",
            description=(
                "Upload **one** file to input dir and index it (POST /documents/upload).\n"
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
                "Upload multiple files (calls /documents/upload once per file).\n"
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
                "Insert a single text (POST /documents/text).\n"
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
                "Insert multiple texts (POST /documents/texts).\n"
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
                "Clear ALL documents and files (DELETE /documents). Irreversible.\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_list_statuses",
            description=(
                "List documents grouped by processing status (GET /documents).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_pipeline_status",
            description=(
                "Get pipeline status/progress (GET /documents/pipeline_status).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_delete_by_ids",
            description=(
                "Delete specific documents (DELETE /documents/delete_document).\n"
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
                "Clear LLM cache (POST /documents/clear_cache).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="documents_delete_entity",
            description=(
                "Delete an entity from the KG (DELETE /documents/delete_entity).\n"
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
                "Delete a relation from the KG (DELETE /documents/delete_relation).\n"
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
                "Track processing status by track_id (GET /documents/track_status/{track_id}).\n"
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
                "Paginated documents query (POST /documents/paginated).\n"
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
                "Counts of documents by status (GET /documents/status_counts).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        # ---------------- query ----------------------
        Tool(
            name="query",
            description=(
                "RAG query (POST /query). Returns **structured output**: {request, response}.\n"
                "Example input: {\"query\":\"Summarize recent docs\", \"mode\":\"hybrid\", \"top_k\":5, \"only_need_context\": false}"
            ),
            inputSchema=QueryRequest.model_json_schema(),
        ),
        Tool(
            name="query_stream",
            description=(
                "Streamed RAG query (POST /query/stream). Returns **structured output**: {request, stream}.\n"
                "Example input: {\"query\":\"Show citations\", \"mode\":\"hybrid\"}"
            ),
            inputSchema=QueryRequest.model_json_schema(),
        ),
        # ---------------- graph ----------------------
        Tool(
            name="graph_labels",
            description=(
                "List graph labels (GET /graph/label/list).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="graphs_get",
            description=(
                "Retrieve subgraph by label (GET /graphs).\n"
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
                "Check if an entity exists (GET /graph/entity/exists).\n"
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
                "Update entity properties (POST /graph/entity/edit).\n"
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
                "Update relation properties (POST /graph/relation/edit).\n"
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
                "Get Ollama version info (GET /api/version).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ollama_tags",
            description=(
                "List available models (GET /api/tags).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ollama_ps",
            description=(
                "List running models (GET /api/ps).\n"
                "Example input: {}"
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="ollama_generate",
            description=(
                "Direct completion to underlying LLM (POST /api/generate).\n"
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
                "Chat completion (POST /api/chat).\n"
                "Example input: {\"payload\": {\"model\":\"qwen\", \"messages\":[{\"role\":\"user\", \"content\":\"hi\"}]}}"
            ),
            inputSchema={
                "type": "object",
                "properties": {"payload": {"type": "object", "additionalProperties": True}},
                "required": ["payload"],
            },
        ),
    ]