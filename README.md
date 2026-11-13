# AI Multi-Tool Agent

A local AI-powered analytics assistant that lets you upload an Excel or CSV file and ask questions in natural language.

It uses a LangChain agent connected to multiple MCP servers for Excel/CSV retrieval, Pandas analysis, and Tavily web search.

## Features

- Upload `.xlsx`, `.xlsm`, or `.csv` files
- Automatic Excel/CSV header-row detection
- Cleans blank, unnamed, and duplicate columns
- Requires at least five valid columns
- Supports one active dataset at a time
- Semantic search using SentenceTransformers and FAISS
- Pandas-based summaries, grouping, filtering, sorting, and correlation
- Tavily web search for external or recent information
- Persistent MCP connection for faster repeated questions
- Shows which MCP tools the agent used

## Architecture

```text
Browser
   ↓
Flask app.py
   ↓
LangChain Multi-Tool Agent
   ↓
Persistent MCP Aggregator Connection
   ├── RAG MCP Server
   │    ├── process_excel_file
   │    └── search_excel_data
   │
   ├── Pandas MCP Server
   │    ├── get_excel_summary
   │    ├── calculate_column_statistic
   │    ├── group_and_aggregate
   │    ├── filter_excel_data
   │    ├── sort_excel_data
   │    └── calculate_correlation
   │
   └── Tavily Web Search MCP Server
        ├── tavily-search
        └── tavily-extract
```

Flask handles uploads and user requests. The MCP servers handle retrieval, analysis, and web search.

## Project Structure

```text
AIAgentProj/
├── app.py                       # Flask web server and API
├── langchain_agent.py           # LangChain multi-tool agent
├── mcp_aggregator.py            # Aggregates all MCP servers
├── rag_mcp_server.py            # Excel/CSV semantic search
├── pandas_mcp_server.py         # Pandas structured analysis
├── file_validators.py           # Upload validation helpers
├── requirements.txt             # Python dependencies
├── .env                         # API keys and model settings
├── templates/
│   └── index.html               # Web interface
└── uploads/
    ├── active_excel.xlsx        # Active Excel dataset
    ├── active_data.csv          # Active CSV dataset
    └── active_dataset.txt       # Active dataset path marker
```

## How the Active Dataset Works

Flask saves only one active dataset at a time.

| Uploaded file type | Saved as |
|---|---|
| `.xlsx` | `uploads/active_excel.xlsx` |
| `.xlsm` | `uploads/active_excel.xlsx` |
| `.csv` | `uploads/active_data.csv` |

When a new file is uploaded:

1. Flask deletes the previous active file of the other type.
2. Flask saves the new file using the fixed active filename.
3. Flask writes the exact active file path to `uploads/active_dataset.txt`.
4. The RAG MCP server processes that exact file.
5. The Pandas MCP server loads the active file automatically.

This prevents the agent from inventing filenames such as `data.xlsx`, `uploaded_file.csv`, or `current`.

## Setup

### 1. Open the project

```bash
cd AIAgentProj
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows PowerShell
.venv\Scripts\Activate
```

```bash
# Windows Command Prompt
.venv\Scripts\activate.bat
```

```bash
# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install flask python-dotenv pandas numpy faiss-cpu sentence-transformers openpyxl xlrd fastmcp langchain langchain-openrouter langchain-core langgraph
```

### 4. Create `.env`

Create a `.env` file in the project root:

```env
OPENROUTER_API_KEY=your-openrouter-api-key
MODEL=your-openrouter-model-id
```

Example:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key
MODEL=openai/gpt-4o-mini
```

Do not commit `.env` to GitHub.

## Run the Application

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

Upload an Excel or CSV file, then ask a question.

## Example Questions

```text
What columns are in this dataset?
```

```

## API Endpoints

### `GET /`

Displays the web interface.

### `POST /upload`

Uploads, validates, cleans, and saves the active Excel or CSV file.

Request:

```text
Content-Type: multipart/form-data
Field: file
```

Example response:

```json
{
  "message": "File uploaded and validated. You can now ask questions.",
  "file_type": "CSV",
  "active_filename": "active_data.csv",
  "active_file_path": "C:\\path\\to\\uploads\\active_data.csv",
  "validation": {
    "header_row": 0,
    "columns": ["Region", "Product", "Sales"],
    "valid_column_count": 3,
    "row_count": 100
  }
}
```

### `POST /ask`

Sends a question to the LangChain multi-tool agent.

Request:

```json
{
  "query": "What is the total sales by region?"
}
```

Response:

```json
{
  "question": "What is the total sales by region?",
  "answer": "The total sales by region are...",
  "tools_used": [
    "process_excel_file",
    "search_excel_data",
    "group_and_aggregate"
  ]
}
```

## MCP Tools

### RAG MCP Server

| Tool | Arguments | Purpose |
|---|---|---|
| `process_excel_file` | `file_path` | Processes the active Excel/CSV file and creates a FAISS index |
| `search_excel_data` | `query`, `top_k=10` | Searches the active dataset semantically |

### Pandas MCP Server

| Tool | Purpose |
|---|---|
| `get_excel_summary` | Returns dataset structure and numeric statistics |
| `calculate_column_statistic` | Calculates sum, mean, min, max, median, or count |
| `group_and_aggregate` | Groups data and aggregates a numeric column |
| `filter_excel_data` | Filters rows using equals, comparison, or contains |
| `sort_excel_data` | Sorts rows by a column |
| `calculate_correlation` | Calculates correlation between two numeric columns |

### Tavily MCP Server

| Tool | Purpose |
|---|---|
| `tavily-search` | Searches the web |
| `tavily-extract` | Extracts content from a webpage |

## Performance Design

The application starts the MCP connection once when Flask starts.

```text
Flask starts
   ↓
MCP aggregator starts once
   ↓
Pandas MCP server starts once
   ↓
RAG MCP server starts once
   ↓
SentenceTransformer loads once
   ↓
MCP tools discovered once
   ↓
Flask accepts requests
```

Each `/ask` request reuses the same MCP connection instead of restarting the MCP servers.

The RAG server also avoids reprocessing the same active file if it has already been embedded.

## Agent Behavior

The LangChain agent follows these rules:

- Use `process_excel_file` before searching a newly uploaded dataset.
- Use `search_excel_data` for descriptive questions and content lookup.
- Use Pandas tools for calculations, grouping, filtering, and statistics.
- Use Tavily for external, recent, or general information.
- Use multiple tools when needed.
- Never invent data, filenames, file paths, or file IDs.

## Tavily Keyless Mode

This project uses Tavily keyless access.

The MCP aggregator must send this header:

```text
X-Tavily-Access-Mode: keyless
```

Keyless access supports:

- Search
- Extract

Keyless access does not support:

- Crawl
- Map
- Research

No Tavily API key is required for Search and Extract.

## Common Issues

### `No active Excel or CSV file found`

Upload an Excel or CSV file first.

Check that one of these exists:

```text
uploads/active_excel.xlsx
uploads/active_data.csv
```

Also check:

```text
uploads/active_dataset.txt
```

### `Invalid file path`

The RAG MCP server only allows files inside:

```text
uploads/
```

Do not pass paths outside the upload folder.

### `nesting counter should be 0 when starting new session`

This happens when `asyncio.run()` is used for every request while a persistent MCP connection is already running.

Use the dedicated event loop and:

```python
run_agent_coroutine(
    run_multi_tool_agent(...)
)
```

Do not use:

```python
asyncio.run(
    run_multi_tool_agent(...)
)
```

### MCP startup is slow

The first startup loads:

- MCP aggregator
- Pandas MCP server
- RAG MCP server
- SentenceTransformer model
- MCP tool definitions

This happens once. Later questions reuse the same connection.

### Tavily keyless access fails

Ensure the aggregator uses:

```python
headers={
    "X-Tavily-Access-Mode": "keyless"
}
```

## Security Notes

- Never commit `.env`, API keys, or uploaded datasets.
- Change `app.secret_key` before deploying.
- Use `debug=False` when running the persistent MCP setup.
- The RAG MCP server validates that file paths remain inside `uploads/`.

## Future Improvements

- Support multiple active datasets
- Add user login
- Add chart generation
- Add Excel/PDF export
- Add conversation memory
- Add streaming responses
- Deploy MCP servers over HTTP
- Add Docker support

## License

This project is for educational and personal use.