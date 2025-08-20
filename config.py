import os
import argparse
from typing import Optional, List
import yaml

# Tools we want to expose by default.
# A comma-separated string of these is the default for the --tools flag.
DEFAULT_TOOLS = [
    # query
    "query",
    # ingest
    "documents_upload_file",
    "documents_insert_text",
    "documents_scan",
    # graph
    "graphs_get",
]

def _load_tools_from_yaml(config_path: str) -> Optional[List[str]]:
    """Load the list of enabled tools from a YAML config file."""
    if not os.path.exists(config_path):
        return None
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        if isinstance(config_data, dict) and 'enabled_tools' in config_data:
            if isinstance(config_data['enabled_tools'], list):
                return config_data['enabled_tools']
    except Exception:
        pass
    return None

def resolve_config() -> tuple[str, Optional[str], List[str]]:
    """Resolve LightRAG config from CLI/env/.env/YAML.
    Order of precedence: CLI > environment > YAML > defaults.
    Returns:
        - base_url (str): e.g. http://localhost:9621
        - api_key (str|None): optional API key
        - enabled_tools (list[str]): tool names to expose
    """
    # env (already loaded from .env if present)
    env_base = os.getenv("LIGHTRAG_BASE_URL")
    env_key = os.getenv("LIGHTRAG_API_KEY")
    env_tools = os.getenv("LIGHTRAG_TOOLS")

    # Load from config.yaml
    yaml_tools = _load_tools_from_yaml('config.yaml')

    # Determine the source for tools
    if env_tools:
        tools_source = env_tools
    elif yaml_tools is not None:
        tools_source = ",".join(yaml_tools)
    else:
        tools_source = ",".join(DEFAULT_TOOLS)

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
    parser.add_argument(
        "--tools",
        type=str,
        default=tools_source,
        help=f"Comma-separated tools to enable (default: from config.yaml or built-in list)",
    )

    args, _ = parser.parse_known_args()
    base = (args.service_url or "http://localhost:9621").rstrip("/")
    key = args.key or None
    
    # Split tool string into a list of names
    enabled_tools = [t.strip() for t in (args.tools or "").split(",") if t.strip()]
    
    return base, key, enabled_tools