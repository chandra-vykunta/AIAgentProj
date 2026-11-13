# ============================================================
# FLASK HOST SERVER
# EXCEL/CSV UPLOAD + LANGCHAIN MULTI-TOOL AGENT
# ============================================================
#
# Responsibilities:
#   1. Receive an uploaded Excel or CSV file from the browser
#   2. Validate the uploaded file type
#   3. Detect the file header row
#   4. Clean blank, unnamed, and duplicate columns
#   5. Require at least five valid columns
#   6. Save the cleaned file as the active dataset
#   7. Send user questions to the LangChain multi-tool agent
#
# The LangChain agent connects to the MCP aggregator using STDIO.
# The aggregator exposes tools from:
#   - RAG MCP server
#   - Pandas MCP server
#   - Tavily Web Search MCP server
#
# Flask does NOT:
#   - Create embeddings
#   - Store FAISS indexes
#   - Search Excel content directly
#   - Perform Pandas calculations
#   - Perform web searches
# ============================================================

import asyncio
from pathlib import Path

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Import the LangChain multi-tool agent function
from langchain_agent import run_multi_tool_agent

# Import Excel and CSV validation helpers
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

# Folder containing app.py
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")

# Folder where the active dataset is stored
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

# Maximum upload size: 16 MB
MAX_FILE_SIZE = 16 * 1000 * 1000

# Always use the same filename for the active Excel file.
#
# This supports the rule:
#   "Work on one Excel file at a time."
#
# When a new Excel file is uploaded, it replaces the previous one.
ACTIVE_EXCEL_FILENAME = "active_excel.xlsx"

# Always use the same filename for the active CSV file.
ACTIVE_CSV_FILENAME = "active_data.csv"

# Create the Flask application
app = Flask(__name__)

# Configure Flask upload settings
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


# ============================================================
# STEP 2: WEB PAGE
# ============================================================

@app.route("/")
def home():
    """
    Display the Excel/CSV upload and chat page.

    Flask looks for index.html inside the templates folder.
    """
    return render_template("index.html")


# ============================================================
# STEP 3: UPLOAD EXCEL OR CSV FILE
# ============================================================

@app.route("/upload", methods=["POST"])
def upload_file():
    """
    Upload, validate, clean, and save the active Excel or CSV file.
    """
    # Get the uploaded file from the browser.
    file = request.files.get("file")

    # Validate that a file was uploaded.
    if not file:
        return jsonify(
            {"error": "No file uploaded"}
        ), 400

    # Validate the file extension.
    if not is_allowed_file(file.filename):
        return jsonify(
            {
                "error": (
                    "Only .xlsx, .xlsm, or .csv files are allowed"
                )
            }
        ), 400

    # Get the lowercase file extension.
    extension = get_file_extension(file.filename)

    # Choose the active dataset filename.
    if extension in ("xlsx", "xlsm"):
        active_file_path = UPLOAD_FOLDER / ACTIVE_EXCEL_FILENAME

    elif extension == "csv":
        active_file_path = UPLOAD_FOLDER / ACTIVE_CSV_FILENAME

    else:
        return jsonify(
            {"error": "Unsupported file type"}
        ), 400

    try:
        # Save the uploaded file as the active dataset.
        #
        # Excel files become:
        #   uploads/active_excel.xlsx
        #
        # CSV files become:
        #   uploads/active_data.csv
        file.save(active_file_path)

        # Validate and clean Excel files.
        if extension in ("xlsx", "xlsm"):
            validation_result = validate_and_clean_excel(
                active_file_path
            )

        # Validate and clean CSV files.
        elif extension == "csv":
            validation_result = validate_and_clean_csv(
                active_file_path
            )

        else:
            return jsonify(
                {"error": "Unsupported file type"}
            ), 400

    except ValueError as error:
        # Validation errors, such as too few columns.
        return jsonify(
            {"error": str(error)}
        ), 400

    except Exception:
        # Reading or saving errors.
        return jsonify(
            {"error": "Unable to read the uploaded file."}
        ), 400

    # Return a successful upload response.
    return jsonify(
        {
            "message": (
                "File uploaded and validated. "
                "You can now ask questions."
            ),
            "file_type": get_file_type(file.filename),
            "active_filename": active_file_path.name,
            "validation": validation_result
        }
    )


# ============================================================
# STEP 4: ASK QUESTION USING LANGCHAIN AGENT
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

    active_excel_path = UPLOAD_FOLDER / ACTIVE_EXCEL_FILENAME
    active_csv_path = UPLOAD_FOLDER / ACTIVE_CSV_FILENAME

    if not active_excel_path.exists() and not active_csv_path.exists():
        return jsonify(
            {"error": "Upload an Excel or CSV file first."}
        ), 400

    try:
        # Run the agent and receive answer + tools used.
        agent_result = asyncio.run(
            run_multi_tool_agent(query)
        )

    except Exception as error:
        return jsonify(
            {
                "error": f"Agent failed to answer: {error}"
            }
        ), 500

    # Return the final answer and tools used.
    return jsonify(
        {
            "question": query,
            "answer": agent_result["answer"],
            "tools_used": agent_result["tools_used"]
        }
    )

# ============================================================
# STEP 5: RUN FLASK
# ============================================================

if __name__ == "__main__":
    # Run the Flask development server.
    app.run(debug=True)