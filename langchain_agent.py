# ============================================================
# LANGCHAIN MULTI-TOOL AGENT
# CONNECTED TO STDIO MCP AGGREGATOR
# ============================================================
import asyncio
import threading

from contextlib import AsyncExitStack
import os
from pathlib import Path

from dotenv import load_dotenv

from langchain_openrouter import ChatOpenRouter
from langchain.mcp import MCPAdapter
from langchain.agents import create_agent


# ============================================================
# STEP 1: CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_NAME = os.getenv("MODEL")

MCP_AGGREGATOR_PATH = BASE_DIR / "mcp_aggregator.py"

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is missing in .env")

if not MODEL_NAME:
    raise ValueError("MODEL is missing in .env")

if not MCP_AGGREGATOR_PATH.exists():
    raise FileNotFoundError(
        f"MCP aggregator not found: {MCP_AGGREGATOR_PATH}"
    )

# Dedicated background event loop for MCP and agent operations.
agent_loop = None

# Keeps the MCP adapter and tool connections alive.
mcp_exit_stack = None

# Stores the discovered LangChain-compatible MCP tools.
mcp_tools = None
# ============================================================
# STEP 2: SYSTEM PROMPT
# ============================================================

def build_system_prompt(active_file_path: str | None = None) -> str:
    """
    Build the system prompt for the multi-tool agent.
    """
    prompt = """
You are an intelligent Excel and CSV data analytics assistant.

The user has already uploaded one active dataset.

Available tool types:

1. RAG tools
   - Process the active Excel or CSV file.
   - Search the active dataset.
   - Retrieve relevant rows.

2. Pandas tools
   - Calculate totals, averages, minimum, maximum, and counts.
   - Group records.
   - Filter and analyse structured data.

3. Web Search tools
   - Retrieve external, recent, or general information from the web.

Tool selection rules:

1. For descriptive questions, summaries, or content lookup,
   use the RAG search tool.

2. For questions requiring calculations, first retrieve relevant
   records using RAG, then use the Pandas analysis tool.

3. For external, recent, or general information not available in
   the dataset, use the web search tool.

4. Use multiple tools when necessary.

5. Never invent data.

6. Use only information returned by tools.

7. Explain the final answer clearly in natural language.

8. If the available tools do not contain enough information,
   say so clearly.
"""

    if active_file_path:
        prompt += f"""

The exact active dataset path is:
{active_file_path}

When calling process_excel_file, use exactly this value:
file_path="{active_file_path}"

Do not modify, shorten, or invent this path.
Do not ask the user for a filename or file path.
"""

    else:
        prompt += """

No active dataset path was provided.
Do not invent a filename or file path.
If dataset processing is required, explain that no active file is available.
"""

    return prompt


# ============================================================
# STEP 3: CREATE LLM
# ============================================================

def create_llm():
    """
    Create the LangChain chat model connected to OpenRouter.
    """
    llm = ChatOpenRouter(
        model=MODEL_NAME,
        api_key=OPENROUTER_API_KEY
    )

    return llm


# ============================================================
# STEP 4: RUN MULTI-TOOL AGENT
# ============================================================

async def run_multi_tool_agent(
    query: str,
    active_file_path: str | None = None
):
    """
    Run the LangChain multi-tool agent using a persistent MCP connection.
    """
    global mcp_tools

    if not mcp_tools:
        raise RuntimeError(
            "MCP connection is not started."
        )

    # Build the system prompt.
    system_prompt = build_system_prompt(active_file_path)

    # Create the LLM.
    llm = create_llm()

    # Create the agent using the already-discovered tools.
    agent = create_agent(
        model=llm,
        tools=mcp_tools,
        system_prompt=system_prompt
    )

    # Run the agent.
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

    for message in messages:

        if hasattr(message, "tool_calls") and message.tool_calls:

            for tool_call in message.tool_calls:
                tool_name = tool_call.get("name")

                if tool_name not in tools_used:
                    tools_used.append(tool_name)

    return {
        "answer": final_message.content,
        "tools_used": tools_used
    }

#Start MCP COnnection
async def start_mcp_connection():
    """
    Start the MCP aggregator once and discover its tools.
    """
    global mcp_exit_stack, mcp_tools

    # Create an exit stack to keep MCP connections open.
    mcp_exit_stack = AsyncExitStack()

    # Connect to the MCP aggregator.
    adapter = await mcp_exit_stack.enter_async_context(
        MCPAdapter(MCP_AGGREGATOR_PATH)
    )

    # Discover tools once.
    mcp_tools = await adapter.list_tools()

    print(f"Loaded {len(mcp_tools)} MCP tools.")


async def stop_mcp_connection():
    """
    Close the persistent MCP connection.
    """
    global mcp_exit_stack, mcp_tools

    if mcp_exit_stack:
        await mcp_exit_stack.aclose()

    mcp_exit_stack = None
    mcp_tools = None

# ============================================================
# STEP 5: OPTIONAL: RUN AS STANDALONE SCRIPT
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