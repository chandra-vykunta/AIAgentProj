# ============================================================
# LANGCHAIN MULTI-TOOL AGENT
# CONNECTED TO STDIO MCP AGGREGATOR
# ============================================================

import os
from pathlib import Path

from dotenv import load_dotenv

from langchain_openrouter import ChatOpenRouter
from langchain.mcp import MCPAdapter
from langchain.agents import create_agent


# ============================================================
# STEP 1: CONFIGURATION
# ============================================================

# Folder containing langchain_agent.py
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# Read environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL")

# Path to the STDIO MCP aggregator.
#
# IMPORTANT:
# Keep this as a Path object.
# Do NOT convert it to a string with str().
#
# Correct:
#   MCPAdapter(MCP_AGGREGATOR_PATH)
#
# Incorrect:
#   MCPAdapter(str(MCP_AGGREGATOR_PATH))
MCP_AGGREGATOR_PATH = BASE_DIR / "mcp_aggregator.py"

# Validate required environment variables
if not OPENROUTER_API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY is missing in .env"
    )

if not MODEL_NAME:
    raise ValueError(
        "MODEL is missing in .env"
    )

# Ensure the aggregator file exists
if not MCP_AGGREGATOR_PATH.exists():
    raise FileNotFoundError(
        f"MCP aggregator not found: {MCP_AGGREGATOR_PATH}"
    )


# ============================================================
# STEP 2: SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an intelligent Excel data analytics assistant.

The user has already uploaded one Excel file.
The Excel data has already been loaded into the RAG MCP server.
Do not ask the user for a filename or file ID.

Available tool types:

1. RAG tools
   - Search the active Excel file.
   - Retrieve relevant Excel rows.
   - Return Excel records for further analysis.

2. Pandas tools
   - Calculate totals, averages, minimum, maximum, and counts.
   - Group Excel records.
   - Filter and analyse structured Excel data.

3. Web Search tools
   - Retrieve external, recent, or general information from the web.

Tool selection rules:

1. For descriptive questions, summaries, or content lookup,
   use the RAG search tool.

2. For questions requiring calculations, first retrieve relevant
   Excel records using RAG, then use the Pandas analysis tool.

3. For external, recent, or general information not available in
   the Excel file, use the web search tool.

4. Use multiple tools when necessary.

5. Never invent data.

6. Use only information returned by tools.

7. Explain the final answer clearly in natural language.

8. If the available tools do not contain enough information,
   say so clearly.
"""


# ============================================================
# STEP 3: CREATE LLM
# ============================================================

def create_llm():
    """
    Create the LangChain chat model connected to OpenRouter.

    Returns:
        ChatOpenRouter: LangChain-compatible LLM object.
    """
    llm = ChatOpenRouter(
        model=MODEL_NAME,
        api_key=OPENROUTER_API_KEY
    )

    return llm


# ============================================================
# STEP 4: CREATE MULTI-TOOL AGENT
# ============================================================

async def create_multi_tool_agent():
    """
    Connect to the STDIO MCP aggregator using MCPAdapter,
    discover LangChain-compatible tools, and create the agent.

    Returns:
        A LangChain agent that can select and call MCP tools.
    """
    # Create the LLM.
    llm = create_llm()

    # Connect to the MCP aggregator using STDIO.
    #
    # IMPORTANT:
    # Pass the Path object directly.
    #
    # Correct:
    #   MCPAdapter(MCP_AGGREGATOR_PATH)
    #
    # Incorrect:
    #   MCPAdapter(str(MCP_AGGREGATOR_PATH))
    async with MCPAdapter(
        MCP_AGGREGATOR_PATH
    ) as adapter:

        # Discover LangChain-compatible tools from the aggregator.
        #
        # The aggregator may expose tools from:
        #   - RAG MCP server
        #   - Pandas MCP server
        #   - Web Search MCP server
        tools = await adapter.list_tools()

        # Create the LangChain agent.
        #
        # The agent receives:
        #   1. The LLM
        #   2. All MCP tools
        #   3. The system prompt
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SYSTEM_PROMPT
        )

        return agent


# ============================================================
# STEP 5: RUN MULTI-TOOL AGENT WITH TOOL DETAILS
# ============================================================

async def run_multi_tool_agent(query: str):
    """
    Run the LangChain multi-tool agent and print tool usage.
    """
    agent = await create_multi_tool_agent()

    response = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": query
                }
            ]
        }
    )

    messages = response["messages"]

    final_message = messages[-1]

    tools_used = []

    print("\n==============================")
    print("AGENT TOOL EXECUTION TRACE")
    print("==============================")

    for message in messages:

        # Print tool calls requested by the model.
        if hasattr(message, "tool_calls") and message.tool_calls:

            for tool_call in message.tool_calls:

                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})

                if tool_name not in tools_used:
                    tools_used.append(tool_name)

                print("\nTOOL CALLED:")
                print(f"Tool Name: {tool_name}")
                print(f"Arguments: {tool_args}")

        # Print tool responses.
        elif type(message).__name__ == "ToolMessage":

            print("\nTOOL RESPONSE RECEIVED:")
            print(f"Tool Name: {getattr(message, 'name', 'Unknown')}")
            print(f"Response: {message.content}")

    print("\n==============================")
    print("TOOLS USED")
    print("==============================")

    if tools_used:
        for tool_name in tools_used:
            print(f"- {tool_name}")
    else:
        print("- No tools were used.")

    print("==============================\n")

    return {
        "answer": final_message.content,
        "tools_used": tools_used
    }


# ============================================================
# STEP 6: OPTIONAL: RUN AS STANDALONE SCRIPT
# ============================================================

if __name__ == "__main__":
    import asyncio

    user_question = input("Ask your Excel data: ")

    result = asyncio.run(
        run_multi_tool_agent(user_question)
    )

    print("\n========== FINAL ANSWER ==========")
    print(result["answer"])

    print("\n========== TOOLS USED ============")

    if result["tools_used"]:
        for tool_name in result["tools_used"]:
            print(f"- {tool_name}")
    else:
        print("- No tools were used.")