# ============================================================
# TEST TAVILY MCP DIRECTLY
# ============================================================
#
# This script tests whether your application can connect to
# Tavily's remote MCP server using keyless access.
# ============================================================

import asyncio

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# Tavily keyless MCP endpoint
TAVILY_MCP_URL = "https://mcp.tavily.com/mcp/"

# Required header for keyless Search and Extract
TAVILY_KEYLESS_HEADERS = {
    "X-Tavily-Access-Mode": "keyless"
}

# Create the HTTP transport
tavily_transport = StreamableHttpTransport(
    url=TAVILY_MCP_URL,
    headers=TAVILY_KEYLESS_HEADERS
)


async def test_tavily():
    """
    Connect to Tavily MCP, list tools, and perform a test search.
    """
    print("Testing Tavily MCP...")
    print(f"URL: {TAVILY_MCP_URL}")

    try:
        # Connect directly to Tavily MCP.
        async with Client(tavily_transport) as client:

            # Step 1: List available Tavily tools.
            tools = await client.list_tools()

            print("\nTavily MCP connected successfully.")
            print(f"Total tools discovered: {len(tools)}")

            print("\nAvailable Tavily Tools:")

            for tool in tools:
                print(f"\n- {tool.name}")
                print(f"  {tool.description}")

            # Step 2: Find the search tool.
            #
            # Tavily's search tool is commonly named:
            #   tavily-search
            # or
            #   tavily_search
            search_tool_name = None

            for tool in tools:
                if "search" in tool.name.lower():
                    search_tool_name = tool.name
                    break

            if not search_tool_name:
                print("\nNo Tavily search tool was found.")
                return

            print(f"\nTesting search tool: {search_tool_name}")

            # Step 3: Call Tavily search.
            result = await client.call_tool(
                search_tool_name,
                {
                    "query": "latest artificial intelligence news"
                }
            )

            print("\nTavily Search Result:")
            print(result.content[0].text)

    except Exception as error:
        print("\nTavily MCP test failed:")
        print(error)


if __name__ == "__main__":
    asyncio.run(test_tavily())