import json
import logging
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from config import resolve_config

logger = logging.getLogger(__name__)

class LightRagHttpClient:
    """Tiny async client for the LightRAG HTTP API (per OpenAPI 0204)."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 150):
        # resolve (CLI/env/.env → defaults)
        self.base_url, self.api_key, _ = resolve_config()
        if base_url:
            self.base_url = base_url.rstrip("/")
        if api_key is not None:
            self.api_key = api_key
        self.timeout = timeout
        self.access_token: Optional[str] = None  # OAuth2 password flow bearer token
        self.client = httpx.AsyncClient(timeout=self.timeout)
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

    def _json_or_text(self, r: httpx.Response) -> str:
        try:
            return json.dumps(r.json(), indent=2, ensure_ascii=False)
        except Exception:
            return r.text

    async def _get(self, path: str, params: Optional[dict] = None, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        r = await self.client.get(url, headers=self._headers(), params=self._params(params))
        r.raise_for_status()
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    async def _post_json(self, path: str, payload: dict, params: Optional[dict] = None, stream: bool = False, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        if stream:
            chunks = []
            async with self.client.stream("POST", url, json=payload, headers=self._headers(), params=self._params(params)) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if line:
                        chunks.append(line)
            data = "\n".join(chunks)
            return data if not want_obj else {"raw_stream": data}

        r = await self.client.post(url, json=payload, headers=self._headers(), params=self._params(params))
        r.raise_for_status()
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    async def _post_multipart(self, path: str, files: List[tuple], params: Optional[dict] = None, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        r = await self.client.post(url, files=files, headers=self._headers(), params=self._params(params))
        r.raise_for_status()
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    async def _delete(self, path: str, json_body: Optional[dict] = None, params: Optional[dict] = None, want_obj: bool = False) -> Any:
        url = f"{self.base_url}{path}"
        r = await self.client.delete(url, headers=self._headers(), params=self._params(params), json=json_body)
        r.raise_for_status()
        if want_obj:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text}
        return self._json_or_text(r)

    # ---------------------- auth & health ---------------------------------

    async def health(self, want_obj: bool = False) -> Any:
        return await self._get("/health", want_obj=want_obj)

    async def auth_status(self, want_obj: bool = False) -> Any:
        return await self._get("/auth-status", want_obj=want_obj)

    async def login(self, username: str, password: str, scope: str = "", want_obj: bool = False) -> Any:
        url = f"{self.base_url}/login"
        data = {"username": username, "password": password, "scope": scope}
        headers = {k: v for k, v in self._headers().items() if k != "Accept"}
        r = await self.client.post(url, data=data, headers=headers)
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

    async def documents_scan(self, want_obj: bool = False) -> Any:
        return await self._post_json("/documents/scan", payload={}, want_obj=want_obj)

    async def upload_file(self, file_path: str, want_obj: bool = False) -> Any:
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            err = {"error": f"File not found: {file_path}"}
            return err if want_obj else json.dumps(err)
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        with open(p, "rb") as f:
            files = [("file", (p.name, f.read(), ctype))]
            return await self._post_multipart("/documents/upload", files=files, want_obj=want_obj)

    async def insert_text(self, text: str, file_source: Optional[str] = None, want_obj: bool = False) -> Any:
        payload = {"text": text}
        if file_source is not None:
            payload["file_source"] = file_source
        return await self._post_json("/documents/text", payload, want_obj=want_obj)

    async def insert_texts(self, texts: List[str], file_sources: Optional[List[str]] = None, want_obj: bool = False) -> Any:
        payload: Dict[str, Any] = {"texts": list(texts)}
        if file_sources is not None:
            payload["file_sources"] = list(file_sources)
        return await self._post_json("/documents/texts", payload, want_obj=want_obj)

    async def documents_clear(self, want_obj: bool = False) -> Any:
        return await self._delete("/documents", want_obj=want_obj)

    async def documents_statuses(self, want_obj: bool = False) -> Any:
        return await self._get("/documents", want_obj=want_obj)

    async def pipeline_status(self, want_obj: bool = False) -> Any:
        return await self._get("/documents/pipeline_status", want_obj=want_obj)

    async def delete_document(self, doc_ids: List[str], delete_file: bool = False, want_obj: bool = False) -> Any:
        payload = {"doc_ids": list(doc_ids), "delete_file": bool(delete_file)}
        return await self._delete("/documents/delete_document", json_body=payload, want_obj=want_obj)

    async def clear_cache(self, want_obj: bool = False) -> Any:
        return await self._post_json("/documents/clear_cache", payload={}, want_obj=want_obj)

    async def delete_entity(self, entity_name: str, want_obj: bool = False) -> Any:
        payload = {"entity_name": entity_name}
        return await self._delete("/documents/delete_entity", json_body=payload, want_obj=want_obj)

    async def delete_relation(self, source_entity: str, target_entity: str, want_obj: bool = False) -> Any:
        payload = {"source_entity": source_entity, "target_entity": target_entity}
        return await self._delete("/documents/delete_relation", json_body=payload, want_obj=want_obj)

    async def track_status(self, track_id: str, want_obj: bool = False) -> Any:
        return await self._get(f"/documents/track_status/{track_id}", want_obj=want_obj)

    async def documents_paginated(self, request: Dict[str, Any], want_obj: bool = False) -> Any:
        return await self._post_json("/documents/paginated", payload=request, want_obj=want_obj)

    async def status_counts(self, want_obj: bool = False) -> Any:
        return await self._get("/documents/status_counts", want_obj=want_obj)

    # ---------------------- query -----------------------------------------

    async def query(self, request: Dict[str, Any], want_obj: bool = True) -> Any:
        # want_obj=True to return structured {response: ...}
        return await self._post_json("/query", payload=request, want_obj=want_obj)

    async def query_stream(self, request: Dict[str, Any], want_obj: bool = True) -> Any:
        # Returns {raw_stream": "..."} when want_obj=True
        return await self._post_json("/query/stream", payload=request, stream=True, want_obj=want_obj)

    # ---------------------- graph -----------------------------------------

    async def graph_labels(self, want_obj: bool = False) -> Any:
        return await self._get("/graph/label/list", want_obj=want_obj)

    async def graphs(self, label: str, max_depth: int = 3, max_nodes: int = 1000, want_obj: bool = False) -> Any:
        params = {"label": label, "max_depth": int(max_depth), "max_nodes": int(max_nodes)}
        return await self._get("/graphs", params=params, want_obj=want_obj)

    async def entity_exists(self, name: str, want_obj: bool = False) -> Any:
        return await self._get("/graph/entity/exists", params={"name": name}, want_obj=want_obj)

    async def update_entity(self, entity_name: str, updated_data: Dict[str, Any], allow_rename: bool = False, want_obj: bool = False) -> Any:
        payload = {"entity_name": entity_name, "updated_data": updated_data, "allow_rename": bool(allow_rename)}
        return await self._post_json("/graph/entity/edit", payload, want_obj=want_obj)

    async def update_relation(self, source_id: str, target_id: str, updated_data: Dict[str, Any], want_obj: bool = False) -> Any:
        payload = {"source_id": source_id, "target_id": target_id, "updated_data": updated_data}
        return await self._post_json("/graph/relation/edit", payload, want_obj=want_obj)

    # ---------------------- ollama-compatible ------------------------------

    async def api_version(self, want_obj: bool = False) -> Any:
        return await self._get("/api/version", want_obj=want_obj)

    async def api_tags(self, want_obj: bool = False) -> Any:
        return await self._get("/api/tags", want_obj=want_obj)

    async def api_ps(self, want_obj: bool = False) -> Any:
        return await self._get("/api/ps", want_obj=want_obj)

    async def api_generate(self, payload: Dict[str, Any], want_obj: bool = False) -> Any:
        return await self._post_json("/api/generate", payload, want_obj=want_obj)

    async def api_chat(self, payload: Dict[str, Any], want_obj: bool = False) -> Any:
        return await self._post_json("/api/chat", payload, want_obj=want_obj)
