# ============================================================
# MCP AGGREGATOR WITH DEBUGGING
# ============================================================

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.client import StreamableHttpTransport
from fastmcp.server import create_proxy
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

TAVILY_MCP_URL = os.getenv("TAVILY_MCP_URL")

PANDAS_SERVER_PATH = BASE_DIR / "pandas_mcp_server.py"
RAG_SERVER_PATH = BASE_DIR / "rag_mcp_server.py"

# ------------------------------------------------------------
# Validate local MCP server files
# ------------------------------------------------------------
print("Aggregator folder:")
print(BASE_DIR)

print("\nChecking local MCP servers...")

print(f"Pandas server: {PANDAS_SERVER_PATH}")
print(f"Exists: {PANDAS_SERVER_PATH.exists()}")

print(f"RAG server: {RAG_SERVER_PATH}")
print(f"Exists: {RAG_SERVER_PATH.exists()}")

if not PANDAS_SERVER_PATH.exists():
    raise FileNotFoundError(
        f"pandas_mcp_server.py not found: {PANDAS_SERVER_PATH}"
    )

if not RAG_SERVER_PATH.exists():
    raise FileNotFoundError(
        f"rag_mcp_server.py not found: {RAG_SERVER_PATH}"
    )

print(f"\nWeb Search URL: {TAVILY_MCP_URL}")

if not TAVILY_MCP_URL:
    raise ValueError(
        "TAVILY_MCP_URL URL is missing in .env"
    )

# ------------------------------------------------------------
# Tavily keyless MCP configuration
# ------------------------------------------------------------



# Required header for keyless access
TAVILY_KEYLESS_HEADERS = {
    "X-Tavily-Access-Mode": "keyless"
}

# Create a Streamable HTTP transport for Tavily.
#
# This transport sends the keyless access header with every
# MCP request sent to Tavily.
tavily_transport = StreamableHttpTransport(
    url=TAVILY_MCP_URL,
    headers=TAVILY_KEYLESS_HEADERS
)

# Create a proxy for the remote Tavily MCP server.
tavily_proxy = create_proxy(
    tavily_transport,
    name="Tavily Web Search"
)

# ------------------------------------------------------------
# Create aggregator
# ------------------------------------------------------------
main_server = FastMCP(
    name="Excel AI Multi-Tool Aggregator",
    instructions=(
        "This server provides Excel retrieval, Excel analysis, "
        "and web search tools."
    )
)

# ------------------------------------------------------------
# Mount Pandas MCP server
# ------------------------------------------------------------
print("\nMounting Pandas MCP server...")

pandas_proxy = create_proxy(
    PANDAS_SERVER_PATH,
    name="Pandas Analytics MCP"
)

main_server.mount(
    pandas_proxy,
    namespace="pandas"
)

print("Pandas MCP server mounted.")

# ------------------------------------------------------------
# Mount RAG MCP server
# ------------------------------------------------------------
print("\nMounting RAG MCP server...")

rag_proxy = create_proxy(
    RAG_SERVER_PATH,
    name="RAG MCP"
)

main_server.mount(
    rag_proxy,
    namespace="rag"
)

print("RAG MCP server mounted.")

# ------------------------------------------------------------
# Mount Tavily MCP server
# ------------------------------------------------------------
print("\nMounting Tavily MCP server...")
main_server.mount(
    tavily_proxy,
    namespace="tavily"
)


print("Tavily MCP server mounted.")

# ------------------------------------------------------------
# Run aggregator using STDIO
# ------------------------------------------------------------
if __name__ == "__main__":
    print("\nStarting MCP aggregator using STDIO...")
    main_server.run(transport="stdio")