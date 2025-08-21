# LightRAG MCP Server

This repository contains a Model Context Protocol (MCP) server that provides a tool-based interface to a locally running LightRAG HTTP API. It is designed for use with MCP-compatible clients, such as those found in IDEs like Visual Studio Code, allowing developers and models to interact with LightRAG's capabilities programmatically.

The server exposes a curated set of tools by default, with the option to enable more as needed through a configuration file.

## Features

- **Configurable Tool Exposure:** Exposes a default set of tools for common use cases, with the ability to enable any other tool from the LightRAG API via a simple configuration file.
- **Flexible Configuration:** Configure the server via a `config.yaml` file, command-line flags, environment variables, or a `.env` file.
- **Authentication Support:** Works with both `X-API-Key` header and OAuth2 password-based (Bearer token) authentication.
- **User-Friendly Tools:** Provides clear, English-only tool descriptions with example inputs.
- **Conversational Outputs:** Key tools like `query` return conversational responses, making it easy for clients to use the results.
- **Modular and Asynchronous:** The codebase is modular and uses an asynchronous HTTP client for better performance and maintainability.

## Prerequisites

Before running the server, you need to have Python 3.12+ and `uv` installed, as well as a locally deployed LightRAG instance (see <https://github.com/HKUDS/LightRAG>). You will also need Node.js and `npx` to run the MCP Inspector tool for testing.

## Installation

1. **Clone the repository.**

```bash
# Use gh cli to clone repository
gh repo clone fvanevski/lightrag_mcp

# Use git to clone repository
git clone https://github.com/fvanevski/lightrag_mcp.git

# Enter the repository directory
cd lightrag_mcp
```

2. **Create a virtual environment and install the required dependencies:**

```bash
# Create a virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install the dependencies
uv sync
```

## Running and Testing the Server

The MCP server is a command-line application that communicates over standard I/O. To use it, a client (like an IDE, a coding agent, or an inspector tool) must launch the server process.

### Running for Diagnostics

You can try to run the script directly from your terminal to see if it starts without errors. This is a quick way to validate your Python environment and the script's basic syntax.

```bash
python lightrag_mcp.py
```

However, the server will simply start and wait for input, so you won't be able to interact with it directly from your terminal.

### Testing with MCP Inspector

The recommended way to test the server interactively is with **MCP Inspector**. It runs as a command-line tool and provides an interactive shell for sending requests to your server.

1. **Launch the Inspector:**
    You can run the inspector without a permanent installation using `npx`. The inspector will launch your MCP server script for you. From your project directory, run:

```bash
# Run the inspector with `uv run --with <dependencies> -- python3 <script>`
npx @modelcontextprotocol/inspector uv run --with httpx,python-dotenv,pydantic,mcp,pyyaml -- python3 lightrag_mcp.py
```

Even if you have your virtual environment active, the `python` command as executed by the inspector will not correctly point to the interpreter with the necessary dependencies, thus we use uv instead with the `--with` flag.

2. **Interact with the Server:**
    Once the inspector starts, you can click the "Connect" button to establish a session with your server. You can then use commands like `list_tools` and `call_tool` to interact with it.

**Example session:**

```bash
# List all available tools
> list_tools

# Call the 'health' tool to check the connection to the LightRAG API
> call_tool health

# Call the 'query' tool with arguments
> call_tool query '''{"query": "What is LightRAG?", "mode": "hybrid"}'''
```

This provides a reliable way to test all the tools and verify that the server is working as expected.

## Configuration

The server can be configured using a `config.yaml` file, command-line flags, environment variables, or a `.env` file. The order of precedence is: **Command-Line Flags > Environment Variables > `config.yaml` > `.env` File > Defaults**.

### `config.yaml`

The easiest way to manage your tools is with the `config.yaml` file. It allows you to enable or disable tools by adding or removing them from a list. Each tool is commented with a description of its function.

By default, the the following tools are enabled:

- `query`
- `documents_upload_file`
- `documents_upload_files`
- `documents_insert_text`
- `documents_scan`
- `graphs_get`
- `graph_labels`
- `graph_entity_exists`
- `graph_update_entity`
- `graph_update_relation`
- `documents_pipeline_status`
- `documents_delete_entity`
- `documents_delete_relation`

To enable other tools, simply uncomment them in the `enabled_tools` list in your `config.yaml` file.

### Environment Variables

- `LIGHTRAG_BASE_URL`: The base URL of the LightRAG API (e.g., `http://localhost:9621`).
- `LIGHTRAG_API_KEY`: The API key for your LightRAG instance, if required.
- `LIGHTRAG_TOOLS`: A comma-separated list of tools to enable (e.g., `query,documents_scan`).

**Example `.env` file:**

```bash
LIGHTRAG_BASE_URL=http://localhost:9621
LIGHTRAG_API_KEY=your-secret-api-key
LIGHTRAG_TOOLS=query,documents_scan,graphs_get
```

## Usage with an MCP Client (VS Code Example)

You can connect to this server from any standard MCP client. Here’s how to do it in a VS Code environment that supports MCP:

1. **Configure Your MCP Client:** In your IDE's MCP client settings (e.g., in `mcp.json` for VS Code), configure a new MCP server that points to the script.

    **Example `mcp.json` entry for VS Code:**

    ```json
    {
      "servers": {
        "lightrag": {
          "command": "uv",
          "args": [
            "run",
            "python",
            "lightrag_mcp.py"
          ],
          "cwd": "/path/to/your/project"
        }
      }
    }
    ```

    *Note: Replace `/path/to/your/project` with the actual path to the project directory.*

2. **Use the Tools:** Once connected, you can use the exposed tools in your chat or agent interactions with natural language queries or structured calls. For example, to perform a RAG query, you could send the following structured tool call:

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

    The server will execute the query against your LightRAG instance and return a conversational response.
