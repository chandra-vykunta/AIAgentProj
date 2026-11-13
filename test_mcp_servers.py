import asyncio
from pathlib import Path

from fastmcp import Client

BASE_DIR = Path(__file__).resolve().parent

PANDAS_SERVER_PATH = BASE_DIR / "pandas_mcp_server.py"
RAG_SERVER_PATH = BASE_DIR / "rag_mcp_server.py"


async def test_server(server_path, name):
    print(f"\nTesting {name}: {server_path}")

    try:
        async with Client(server_path) as client:
            tools = await client.list_tools()

            print(f"{name} connected successfully.")
            print("Available tools:")

            for tool in tools:
                print(f"- {tool.name}: {tool.description}")

    except Exception as error:
        print(f"{name} failed:")
        print(error)


async def main():
    await test_server(PANDAS_SERVER_PATH, "Pandas MCP")
    await test_server(RAG_SERVER_PATH, "RAG MCP")


if __name__ == "__main__":
    asyncio.run(main())