# ============================================================
# FLASK HOST SERVER
# EXCEL/CSV UPLOAD + LANGCHAIN MULTI-TOOL AGENT
# ============================================================

import asyncio
import threading
import time
from pathlib import Path

from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    session
)
from dotenv import load_dotenv

from langchain_agent import (
    run_multi_tool_agent,
    start_mcp_connection,
    stop_mcp_connection
)

from file_validators import (
    is_allowed_file,
    get_file_extension,
    get_file_type,
    validate_and_clean_excel,
    validate_and_clean_csv
)


# ============================================================
# STEP 1: CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

MAX_FILE_SIZE = 16 * 1000 * 1000

ACTIVE_EXCEL_FILENAME = "active_excel.xlsx"
ACTIVE_CSV_FILENAME = "active_data.csv"

ACTIVE_EXCEL_PATH = UPLOAD_FOLDER / ACTIVE_EXCEL_FILENAME
ACTIVE_CSV_PATH = UPLOAD_FOLDER / ACTIVE_CSV_FILENAME

# Marker file that stores the exact active dataset path.
ACTIVE_DATASET_MARKER = UPLOAD_FOLDER / "active_dataset.txt"

app = Flask(__name__)

# Required for Flask session support.
app.secret_key = "change-this-to-a-random-secret-key"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


# ============================================================
# STEP 2: DEDICATED MCP EVENT LOOP
# ============================================================

agent_loop = None


def start_agent_loop():
    """
    Start a dedicated asyncio event loop and MCP connection.

    The MCP aggregator, Pandas server, RAG server, and
    SentenceTransformer model are started only once.
    """
    global agent_loop

    # Create a dedicated event loop.
    agent_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(agent_loop)

    # Start the persistent MCP connection.
    agent_loop.run_until_complete(
        start_mcp_connection()
    )

    # Keep the event loop alive for future agent requests.
    agent_loop.run_forever()


def run_agent_coroutine(coroutine):
    """
    Run an agent coroutine on the dedicated MCP event loop.

    Do NOT use asyncio.run() here. The MCP connection is already
    running on the dedicated event loop.
    """
    future = asyncio.run_coroutine_threadsafe(
        coroutine,
        agent_loop
    )

    return future.result()


# ============================================================
# STEP 3: WEB PAGE
# ============================================================

@app.route("/")
def home():
    """
    Display the Excel/CSV upload and chat page.
    """
    return render_template("index.html")


# ============================================================
# STEP 4: UPLOAD EXCEL OR CSV FILE
# ============================================================

@app.route("/upload", methods=["POST"])
def upload_file():
    """
    Upload, validate, clean, and save the active Excel or CSV file.
    """
    file = request.files.get("file")

    if not file:
        return jsonify(
            {"error": "No file uploaded"}
        ), 400

    if not is_allowed_file(file.filename):
        return jsonify(
            {
                "error": (
                    "Only .xlsx, .xlsm, or .csv files are allowed"
                )
            }
        ), 400

    extension = get_file_extension(file.filename)

    if extension in ("xlsx", "xlsm"):
        active_file_path = ACTIVE_EXCEL_PATH
        other_file_path = ACTIVE_CSV_PATH

    elif extension == "csv":
        active_file_path = ACTIVE_CSV_PATH
        other_file_path = ACTIVE_EXCEL_PATH

    else:
        return jsonify(
            {"error": "Unsupported file type"}
        ), 400

    try:
        # Remove the previous active file of the other type.
        if other_file_path.exists():
            other_file_path.unlink()

        # Save the uploaded file as the active dataset.
        file.save(active_file_path)

        # Validate and clean Excel files.
        if extension in ("xlsx", "xlsm"):
            validation_result = validate_and_clean_excel(
                active_file_path
            )

        # Validate and clean CSV files.
        else:
            validation_result = validate_and_clean_csv(
                active_file_path
            )

    except ValueError as error:
        return jsonify(
            {"error": str(error)}
        ), 400

    except Exception:
        return jsonify(
            {"error": "Unable to read the uploaded file."}
        ), 400

    # Save the exact active file path.
    active_path = str(active_file_path.resolve())

    # Store it in the Flask session.
    session["active_file_path"] = active_path

    # Also store it in a marker file for MCP servers.
    ACTIVE_DATASET_MARKER.write_text(
        active_path,
        encoding="utf-8"
    )

    return jsonify(
        {
            "message": (
                "File uploaded and validated. "
                "You can now ask questions."
            ),
            "file_type": get_file_type(file.filename),
            "active_filename": active_file_path.name,
            "active_file_path": active_path,
            "validation": validation_result
        }
    )


# ============================================================
# STEP 5: ASK QUESTION USING LANGCHAIN AGENT
# ============================================================

@app.route("/ask", methods=["POST"])
def ask_question():
    """
    Send the user question to the LangChain multi-tool agent.
    """
    data = request.get_json(silent=True) or {}

    query = data.get("query", "").strip()

    if not query:
        return jsonify(
            {"error": "Question cannot be empty"}
        ), 400

    # Get the active file path saved during upload.
    active_file_path = session.get("active_file_path")

    if not active_file_path:
        return jsonify(
            {"error": "Upload an Excel or CSV file first."}
        ), 400

    # Convert the session string back into a Path object.
    active_file_path = Path(active_file_path)

    if not active_file_path.exists():
        return jsonify(
            {"error": "Upload an Excel or CSV file first."}
        ), 400

    try:
        # Run the agent on the persistent MCP event loop.
        agent_result = run_agent_coroutine(
            run_multi_tool_agent(
                query=query,
                active_file_path=str(active_file_path)
            )
        )

    except Exception as error:
        return jsonify(
            {
                "error": f"Agent failed to answer: {error}"
            }
        ), 500

    return jsonify(
        {
            "question": query,
            "answer": agent_result["answer"],
            "tools_used": agent_result["tools_used"]
        }
    )


# ============================================================
# STEP 6: FLASK SHUTDOWN
# ============================================================

def shutdown_mcp():
    """
    Close the persistent MCP connection when Flask stops.
    """
    if agent_loop and agent_loop.is_running():
        asyncio.run_coroutine_threadsafe(
            stop_mcp_connection(),
            agent_loop
        ).result(timeout=10)


# ============================================================
# STEP 7: RUN FLASK
# ============================================================

if __name__ == "__main__":

    # Start MCP once in a background thread.
    mcp_thread = threading.Thread(
        target=start_agent_loop,
        daemon=True
    )

    mcp_thread.start()

    # Wait for the MCP aggregator and servers to start.
    time.sleep(5)

    try:
        # Disable the reloader so Flask does not start twice.
        app.run(debug=False)

    finally:
        shutdown_mcp()