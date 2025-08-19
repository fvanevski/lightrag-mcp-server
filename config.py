import os
import argparse
from typing import Optional

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
