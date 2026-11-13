# ============================================================
# RAG MCP SERVER FOR EXCEL AND CSV FILES
# ============================================================
#
# Responsibilities:
#   1. Receive the exact path of the active uploaded file
#   2. Validate that the file is inside the uploads folder
#   3. Read the Excel or CSV file
#   4. Convert each row into searchable text
#   5. Create embeddings using SentenceTransformers
#   6. Store embeddings in FAISS
#   7. Search FAISS when the agent asks a question
#
# Flask saves uploads as:
#   uploads/active_excel.xlsx
#   uploads/active_data.csv
# ============================================================

from pathlib import Path

import pandas as pd
import numpy as np
import faiss

from fastmcp import FastMCP
from sentence_transformers import SentenceTransformer


# ============================================================
# STEP 1: CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

ACTIVE_DATASET_ID = "active_dataset"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

embedder = SentenceTransformer(EMBEDDING_MODEL)


# ============================================================
# STEP 2: CREATE MCP SERVER
# ============================================================

mcp = FastMCP(
    name="RAG MCP Server",
    instructions=(
        "This server processes the active Excel or CSV file into a "
        "searchable knowledge base. "
        "Call process_excel_file with the exact active_file_path "
        "provided in the system prompt. "
        "Then use search_excel_data with only the query argument."
    )
)


# ============================================================
# STEP 3: IN-MEMORY RAG STORE
# ============================================================

rag_store = {}


# ============================================================
# STEP 4: FILE PATH VALIDATION
# ============================================================

def get_valid_uploaded_file_path(file_path: str) -> Path:
    """
    Validate and return an uploaded file path.

    Prevents access to files outside the uploads folder.
    """
    requested_path = Path(file_path).resolve()
    upload_folder = UPLOAD_FOLDER.resolve()

    # Ensure the file is inside the uploads folder.
    if upload_folder not in requested_path.parents:
        raise ValueError(
            "Invalid file path. "
            "The file must be inside the uploads folder."
        )

    # Ensure the file exists.
    if not requested_path.exists():
        raise FileNotFoundError(
            f"Uploaded file not found: {requested_path.name}"
        )

    return requested_path


# ============================================================
# STEP 5: FILE READING HELPERS
# ============================================================

def clean_column_names(columns):
    """
    Clean Excel or CSV column names.
    """
    cleaned = []
    seen = {}

    for i, column in enumerate(columns):

        if (
            pd.isna(column)
            or str(column).strip().lower() in ("", "nan", "none")
            or str(column).startswith("Unnamed:")
        ):
            name = f"Column_{i + 1}"
        else:
            name = str(column).strip().replace("\n", " ")

        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0

        cleaned.append(name)

    return cleaned


def find_excel_header_row(
    path: Path,
    sheet_name=0,
    max_scan_rows: int = 50
):
    """
    Detect the most likely header row in an Excel sheet.
    """
    preview = pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=None,
        nrows=max_scan_rows,
        engine="openpyxl"
    )

    best_row = 0
    best_score = -1

    for i, row in preview.iterrows():

        values = row.dropna().astype(str).str.strip()
        values = values[values != ""]

        if len(values) < 5:
            continue

        non_numeric = sum(
            not str(value)
            .replace(".", "", 1)
            .replace("-", "", 1)
            .isdigit()
            for value in values
        )

        unique_ratio = values.nunique() / len(values)

        short_labels = sum(
            len(value) <= 40
            for value in values
        )

        score = (
            (non_numeric / len(values)) * 3
            + unique_ratio * 2
            + (short_labels / len(values))
        )

        if score > best_score:
            best_score = score
            best_row = i

    return best_row


def read_excel_auto_header(path: Path, sheet_name=0):
    """
    Read an Excel file using the automatically detected header row.
    """
    header_row = find_excel_header_row(path, sheet_name)

    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=header_row,
        engine="openpyxl"
    )

    df.columns = clean_column_names(df.columns.tolist())
    df = df.dropna(how="all").dropna(axis=1, how="all")

    return df, header_row


def read_csv_auto_header(path: Path):
    """
    Read a CSV file using the first suitable row as the header.
    """
    preview = pd.read_csv(
        path,
        header=None,
        nrows=50,
        encoding="utf-8-sig"
    )

    header_row = 0

    for i, row in preview.iterrows():

        values = row.dropna().astype(str).str.strip()
        values = values[values != ""]

        if len(values) >= 5:
            header_row = i
            break

    df = pd.read_csv(
        path,
        header=header_row,
        encoding="utf-8-sig"
    )

    df.columns = clean_column_names(df.columns.tolist())
    df = df.dropna(how="all").dropna(axis=1, how="all")

    return df, header_row


# ============================================================
# STEP 6: MCP TOOL: PROCESS ACTIVE FILE
# ============================================================

@mcp.tool
def process_excel_file(file_path: str) -> str:
    """
    Process the active uploaded Excel or CSV file.

    Args:
        file_path: Exact path of the active uploaded file.

    Returns:
        Confirmation that the dataset was processed.
    """
    try:
        # Validate the uploaded file path.
        path = get_valid_uploaded_file_path(file_path)

        # Read Excel files.
        if path.suffix.lower() in [".xlsx", ".xlsm"]:
            df, header_row = read_excel_auto_header(path)

        # Read CSV files.
        else:
            df, header_row = read_csv_auto_header(path)

        # Check whether the file contains usable data.
        if df.empty:
            return "Error: The active file contains no readable data rows."

        # Convert every row into searchable text.
        texts = []

        for _, row in df.iterrows():
            row_text = " | ".join(
                f"{column}: {row[column]}"
                for column in df.columns
            )

            texts.append(row_text)

        # Create embeddings.
        embeddings = embedder.encode(
            texts,
            show_progress_bar=False
        )

        # FAISS requires float32 vectors.
        embeddings = np.array(embeddings).astype("float32")

        # Create a FAISS index.
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)

        # Store the processed dataset using one fixed ID.
        rag_store[ACTIVE_DATASET_ID] = {
            "texts": texts,
            "index": index,
            "columns": list(df.columns),
            "row_count": len(df),
            "filename": path.name,
            "header_row": header_row
        }

        return (
            f"Successfully processed '{path.name}'. "
            f"Stored {len(texts)} rows in the RAG index. "
            f"Dataset ID: {ACTIVE_DATASET_ID}."
        )

    except Exception as e:
        return f"Error processing file: {str(e)}"


# ============================================================
# STEP 7: MCP TOOL: SEARCH ACTIVE DATASET
# ============================================================

@mcp.tool
def search_excel_data(query: str, top_k: int = 10) -> str:
    """
    Search the active Excel or CSV dataset.

    Args:
        query: User question or search phrase.
        top_k: Number of relevant rows to return.
    """
    # Ensure the active dataset has been processed.
    if ACTIVE_DATASET_ID not in rag_store:
        return (
            "Error: No processed dataset found. "
            "Call process_excel_file first."
        )

    stored_data = rag_store[ACTIVE_DATASET_ID]

    # Convert the question into an embedding.
    query_embedding = embedder.encode([query])
    query_embedding = np.array(query_embedding).astype("float32")

    # Search FAISS.
    distances, indexes = stored_data["index"].search(
        query_embedding,
        top_k
    )

    # Retrieve the closest rows.
    retrieved_chunks = []

    for position, distance in zip(indexes[0], distances[0]):

        if position == -1:
            continue

        retrieved_chunks.append(
            f"Distance: {distance:.4f}\n"
            f"{stored_data['texts'][position]}"
        )

    if not retrieved_chunks:
        return "No relevant dataset rows were found."

    return "\n\n".join(retrieved_chunks)


# ============================================================
# STEP 8: RUN RAG MCP SERVER
# ============================================================

if __name__ == "__main__":
    mcp.run()