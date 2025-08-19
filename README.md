# LightRAG MCP Server

This repository contains a Model Context Protocol (MCP) server that provides a tool-based interface to a locally running LightRAG HTTP API. It is designed for use with MCP-compatible clients, such as those found in IDEs like Visual Studio Code, allowing developers and models to interact with all of LightRAG's capabilities programmatically.

The server exposes the entire LightRAG API surface, including document management, RAG queries, knowledge graph interactions, and Ollama-compatible endpoints.

## Features

-   **Full API Coverage:** Exposes all endpoints from the LightRAG OpenAPI specification (version `0204`).
-   **Flexible Configuration:** Configure the server via command-line flags, environment variables, or a `.env` file.
-   **Authentication Support:** Works with both `X-API-Key` header and OAuth2 password-based (Bearer token) authentication.
-   **User-Friendly Tools:** Provides clear, English-only tool descriptions with example inputs.
-   **Structured Outputs:** Key tools like `query` and `query_stream` return structured JSON, making it easy for clients to parse the results.
-   **Modular and Asynchronous:** The codebase is modular and uses an asynchronous HTTP client for better performance and maintainability.

## Prerequisites

Before running the server, you need to have Python 3.12+ and `uv` installed, as well as a locally deployed LightRAG instance (see https://github.com/HKUDS/LightRAG).

## Installation

1.  **Clone the repository.**

    ```bash
    # Use gh cli to clone repository
    gh repo clone fvanevski/lightrag_mcp

    # Use git to clone repository
    git clone https://github.com/fvanevski/lightrag_mcp.git

    # Enter the repository directory
    cd lightrag_mcp
   ```

2.  **Create a virtual environment and install the required dependencies:**

    ```bash
    # Create a virtual environment
    uv venv

    # Activate the virtual environment
    source .venv/bin/activate

    # Install the dependencies
    uv pip install mcp httpx pydantic python-dotenv
    ```

## Running/Testing the Server

To start the MCP server, run the script from your terminal using the Python interpreter from the virtual environment:

```bash
python lightrag_mcp.py [OPTIONS]
```

By default, the server will attempt to connect to a LightRAG instance at `http://localhost:9621` with no authentication.

### Command-Line Options

You can override the default settings using the following command-line flags:

-   `--service-url URL`: Sets the base URL of the LightRAG API.
-   `--key KEY`: Provides the API key if the LightRAG server requires one.

**Example:**

```bash
python lightrag_mcp.py --service-url http://192.168.1.100:9621 --key "your-secret-api-key"
```

## Configuration

In addition to command-line flags, the server can be configured using environment variables or a `.env` file in your project's root directory. The order of precedence is: **Command-Line Flags > Environment Variables > `.env` File > Defaults**.

### Environment Variables

-   `LIGHTRAG_BASE_URL`: The base URL of the LightRAG API (e.g., `http://localhost:9621`).
-   `LIGHTRAG_API_KEY`: The API key for your LightRAG instance, if required.

**Example `.env` file:**

```
LIGHTRAG_BASE_URL=http://localhost:9621
LIGHTRAG_API_KEY=your-secret-api-key
```

## Usage with an MCP Client (VS Code Example)

You can connect to this server from any standard MCP client. Here’s how to do it in a VS Code environment that supports MCP:

1.  **Configure Your MCP Client:** In your IDE/Coder's MCP client settings (e.g., in `mcp.json` for VS Code or `settings.json` for CLI coding agents such as Gemini CLI), configure a new MCP server that points to the script.

    **Example `mcp.json` entry for VS Code:**

    ```json
    "servers": {
      "lightrag": {
        "command": "uv",
        "args": [
          "run",
          "--with",
          "httpx,python-dotenv,pydantic,mcp",
          "--",
          "python",
          "/path/to/your/project/lightrag_mcp.py"
        ]
      }
    }
    ```

    *Note: Replace `/path/to/your/project` with the actual path to the project directory.*

2.  **Use the Tools:** Once connected, you can use the exposed tools in your chat or agent interactions with natural language queries or structured calls. For example, to perform a RAG query, you could send the following structured tool call:

    ```json
    {
      "tool": "query",
      "arguments": {
        "query": "What did we ingest?",
        "mode": "hybrid",
        "top_k": 5
      }
    }
    ```

    The server will execute the query against your LightRAG instance and return a structured JSON response.