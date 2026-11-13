# ============================================================
# FILE VALIDATORS
# Excel and CSV validation, cleaning, and reading
# ============================================================

import pandas as pd

# Allowed upload extensions
ALLOWED_EXTENSIONS = {"xlsx", "xlsm", "csv"}

# Minimum number of valid columns required
MINIMUM_COLUMNS = 5

# Number of initial rows scanned for header detection
MAX_HEADER_SCAN_ROWS = 50


def get_file_extension(filename):
    """
    Return the lowercase extension without the dot.

    Example:
        "sales.xlsx" -> "xlsx"
    """
    if "." not in filename:
        return ""

    return filename.rsplit(".", 1)[1].lower()


def is_allowed_file(filename):
    """
    Check whether the uploaded file has an allowed extension.

    Supported:
        - .xlsx
        - .xlsm
        - .csv
    """
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


def get_file_type(filename):
    """
    Return a user-friendly file type label.
    """
    extension = get_file_extension(filename)

    if extension in ("xlsx", "xlsm"):
        return "Excel"

    if extension == "csv":
        return "CSV"

    return "Unknown"


def clean_column_names(columns):
    """
    Clean Excel or CSV column names.

    Handles:
    - Blank headers
    - NaN headers
    - Headers named None
    - Pandas-generated headers such as 'Unnamed: 0'
    - Duplicate column names
    - Newline characters in headers

    Args:
        columns: List of original column names.

    Returns:
        List of cleaned column names.
    """
    cleaned = []
    seen = {}

    for i, column in enumerate(columns):

        # Identify blank or invalid headers.
        if (
            pd.isna(column)
            or str(column).strip().lower() in ("", "nan", "none")
            or str(column).startswith("Unnamed:")
        ):
            name = f"Column_{i + 1}"

        else:
            # Remove extra spaces and newline characters.
            name = str(column).strip().replace("\n", " ")

        # Prevent duplicate column names.
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0

        cleaned.append(name)

    return cleaned


def detect_header_row(preview):
    """
    Detect the most likely header row from a DataFrame preview.

    A good header row usually has:
    - At least five non-empty values
    - Mostly text values
    - Mostly unique values
    - Short labels

    Args:
        preview: DataFrame read without assuming a header.

    Returns:
        Zero-based index of the detected header row.
    """
    best_row = 0
    best_score = -1

    for i, row in preview.iterrows():

        # Remove blank cells.
        values = (
            row.dropna()
            .astype(str)
            .str.strip()
        )

        values = values[values != ""]

        # Require at least five non-empty values.
        if len(values) < 5:
            continue

        # Count non-numeric values.
        non_numeric = sum(
            not is_numeric_like(value)
            for value in values
        )

        # Calculate how unique the values are.
        unique_ratio = values.nunique() / len(values)

        # Prefer short header-like labels.
        short_labels = sum(
            len(value) <= 40
            for value in values
        )

        # Higher score means more likely to be a header.
        score = (
            (non_numeric / len(values)) * 3
            + unique_ratio * 2
            + (short_labels / len(values))
        )

        if score > best_score:
            best_score = score
            best_row = i

    return best_row


def is_numeric_like(value):
    """
    Check whether a value looks numeric.
    """
    value = str(value).strip()

    if value == "":
        return False

    try:
        float(value)
        return True
    except ValueError:
        return False


# ============================================================
# EXCEL VALIDATION
# ============================================================

def is_excel_file(filename):
    """
    Check whether a file is an Excel file.
    """
    return get_file_extension(filename) in ("xlsx", "xlsm")


def validate_and_clean_excel(file_path):
    """
    Validate and clean an uploaded Excel file.

    Steps:
    1. Detect the header row.
    2. Read the Excel file using that header row.
    3. Clean column names.
    4. Remove completely empty rows and columns.
    5. Require at least five valid columns.
    6. Save the cleaned file as the active Excel dataset.

    Args:
        file_path: Path to the uploaded Excel file.

    Returns:
        Dictionary containing validation details.
    """
    # Detect the most likely header row.
    preview = pd.read_excel(
        file_path,
        sheet_name=0,
        header=None,
        nrows=MAX_HEADER_SCAN_ROWS,
        engine="openpyxl"
    )

    header_row = detect_header_row(preview)

    # Read the Excel file using the detected header.
    df = pd.read_excel(
        file_path,
        sheet_name=0,
        header=header_row,
        engine="openpyxl"
    )

    # Clean column names.
    df.columns = clean_column_names(df.columns.tolist())

    # Remove rows where every value is blank.
    df = df.dropna(how="all")

    # Remove columns where every value is blank.
    df = df.dropna(axis=1, how="all")

    valid_column_count = len(df.columns)

    # Require at least five valid columns.
    if valid_column_count < MINIMUM_COLUMNS:
        raise ValueError(
            f"The Excel file must contain at least "
            f"{MINIMUM_COLUMNS} valid columns. "
            f"Only {valid_column_count} valid columns were found."
        )

    # Save the cleaned Excel file.
    #
    # This cleaned file becomes the active dataset used by:
    #   - RAG MCP server
    #   - Pandas MCP server
    df.to_excel(
        file_path,
        sheet_name="Sheet1",
        index=False
    )

    return {
        "header_row": header_row,
        "columns": list(df.columns),
        "valid_column_count": valid_column_count,
        "row_count": len(df)
    }


# ============================================================
# CSV VALIDATION
# ============================================================

def is_csv_file(filename):
    """
    Check whether a file is a CSV file.
    """
    return get_file_extension(filename) == "csv"


def validate_and_clean_csv(file_path):
    """
    Validate and clean an uploaded CSV file.

    Steps:
    1. Detect the header row.
    2. Read the CSV file using that header row.
    3. Clean column names.
    4. Remove completely empty rows and columns.
    5. Require at least five valid columns.
    6. Save the cleaned file as the active CSV dataset.

    Args:
        file_path: Path to the uploaded CSV file.

    Returns:
        Dictionary containing validation details.
    """
    # Read a preview without assuming a header.
    preview = pd.read_csv(
        file_path,
        header=None,
        nrows=MAX_HEADER_SCAN_ROWS,
        encoding="utf-8-sig",
        skip_blank_lines=True
    )

    # Detect the most likely header row.
    header_row = detect_header_row(preview)

    # Read the CSV file using the detected header.
    df = pd.read_csv(
        file_path,
        header=header_row,
        encoding="utf-8-sig",
        skip_blank_lines=True
    )

    # Clean column names.
    df.columns = clean_column_names(df.columns.tolist())

    # Remove rows where every value is blank.
    df = df.dropna(how="all")

    # Remove columns where every value is blank.
    df = df.dropna(axis=1, how="all")

    valid_column_count = len(df.columns)

    # Require at least five valid columns.
    if valid_column_count < MINIMUM_COLUMNS:
        raise ValueError(
            f"The CSV file must contain at least "
            f"{MINIMUM_COLUMNS} valid columns. "
            f"Only {valid_column_count} valid columns were found."
        )

    # Save the cleaned CSV file.
    #
    # This cleaned file becomes the active dataset used by:
    #   - RAG MCP server
    #   - Pandas MCP server
    df.to_csv(
        file_path,
        index=False,
        encoding="utf-8-sig"
    )

    return {
        "header_row": header_row,
        "columns": list(df.columns),
        "valid_column_count": valid_column_count,
        "row_count": len(df)
    }