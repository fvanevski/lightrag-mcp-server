# LightRAG MCP Server

This repository contains a Model Context Protocol (MCP) server that provides a tool-based interface to a locally running LightRAG HTTP API. It is designed for use with MCP-compatible clients, such as those found in IDEs like Visual Studio Code, allowing developers and models to interact with all of LightRAG's capabilities programmatically.

The server exposes the entire LightRAG API surface, including document management, RAG queries, knowledge graph interactions, and Ollama-compatible endpoints.

## Features

-   **Full API Coverage:** Exposes all endpoints from the LightRAG OpenAPI specification (version `0204`).
-   **Flexible Configuration:** Configure the server via command-line flags, environment variables, or a `.env` file.
-   **Authentication Support:** Works with both `X-API-Key` header and OAuth2 password-based (Bearer token) authentication.
-   **User-Friendly Tools:** Provides clear, English-only tool descriptions with example inputs.
-   **Structured Outputs:** Key tools like `query` and `query_stream` return structured JSON, making it easy for clients to parse the results.

## Prerequisites

Before running the server, you need to have Python 3 installed.

## Installation

1.  **Clone the repository or download the `lightrag_mcp_server.py` script.**

2.  **Install the required Python dependencies:**

    ```bash
    pip install "mcp-server>=0.2.0" requests pydantic python-dotenv
    ```

## Running the Server

To start the MCP server, run the script from your terminal:

```bash
python lightrag_mcp_server.py [OPTIONS]
```

By default, the server will attempt to connect to a LightRAG instance at `http://localhost:9621` with no authentication.

### Command-Line Options

You can override the default settings using the following command-line flags:

-   `--service-url URL`: Sets the base URL of the LightRAG API.
-   `--key KEY`: Provides the API key if the LightRAG server requires one.

**Example:**

```bash
python lightrag_mcp_server.py --service-url http://192.168.1.100:9621 --key "your-secret-api-key"
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

1.  **Start the Server:** Run `python lightrag_mcp_server.py` in a terminal. The server will start and listen for input on `stdin`.

2.  **Configure Your MCP Client:** In your IDE's MCP client settings (e.g., in `settings.json` for VS Code), configure a new model provider that points to the script.

    **Example `settings.json` for a VS Code extension:**

    ```json
    "mcp.languageModels": [
      {
        "modelId": "lightrag-local",
        "displayName": "LightRAG (Local)",
        "type": "process",
        "command": [
          "python",
          "/path/to/your/lightrag_mcp_server.py"
        ],
        "api": "mcp",
        "version": "0.2"
      }
    ]
    ```

    *Note: Replace `/path/to/your/lightrag_mcp_server.py` with the actual path to the script.*

3.  **Use the Tools:** Once connected, you can use the exposed tools in your chat or agent interactions. For example, to perform a RAG query, you could send the following tool call:

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
