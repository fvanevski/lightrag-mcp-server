from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class QueryRequest(BaseModel):
    query: str
    mode: str = Field("mix", enum=["local", "global", "hybrid", "naive", "mix", "bypass"])
    only_need_context: Optional[bool] = None
    only_need_prompt: Optional[bool] = None
    response_type: Optional[str] = None
    top_k: Optional[int] = Field(None, ge=1)
    chunk_top_k: Optional[int] = Field(None, ge=1)
    max_entity_tokens: Optional[int] = Field(None, ge=1)
    max_relation_tokens: Optional[int] = Field(None, ge=1)
    max_total_tokens: Optional[int] = Field(None, ge=1)
    conversation_history: Optional[List[Dict[str, Any]]] = None
    history_turns: Optional[int] = Field(None, ge=0)
    ids: Optional[List[str]] = None
    user_prompt: Optional[str] = None
    enable_rerank: Optional[bool] = None
