# ============================================================
# LIST TOOLS FROM MCP AGGREGATOR
# ============================================================

import asyncio
from pathlib import Path

from fastmcp import Client

# Folder containing this test script
BASE_DIR = Path(__file__).resolve().parent

# Path to the MCP aggregator
AGGREGATOR_PATH = BASE_DIR / "mcp_aggregator.py"


async def list_aggregator_tools():
    """
    Connect to the MCP aggregator and list all tools.
    """
    print(f"Testing MCP Aggregator: {AGGREGATOR_PATH}")

    try:
        # Connect to the aggregator using STDIO.
        async with Client(AGGREGATOR_PATH) as client:

            # Ask the aggregator for all available tools.
            tools = await client.list_tools()

            print("\nAggregator connected successfully.")
            print(f"Total tools discovered: {len(tools)}")

            print("\nAvailable Tools:")

            for tool in tools:
                print("\n----------------------------------------")
                print(f"Tool Name: {tool.name}")
                print(f"Description: {tool.description}")

                if tool.inputSchema:
                    print("Input Schema:")
                    print(tool.inputSchema)

    except Exception as error:
        print("\nFailed to list tools from aggregator:")
        print(error)


if __name__ == "__main__":
    asyncio.run(list_aggregator_tools())