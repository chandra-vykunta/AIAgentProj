# ============================================================
# PANDAS MCP SERVER
# EXCEL/CSV STRUCTURED DATA ANALYSIS
# ============================================================
#
# This MCP server performs structured analysis on the active
# Excel or CSV file using Pandas.
#
# It works with:
#   uploads/active_excel.xlsx
#   uploads/active_data.csv
#
# If both files exist, it uses the most recently modified file.
#
# This server is best for questions such as:
#   - What is the total sales by region?
#   - What is the average profit?
#   - Which product has the highest sales?
#   - Filter rows where sales are greater than RM10,000.
#   - Show a summary of the dataset.
#
# It does NOT perform RAG retrieval.
# RAG retrieval is handled by rag_mcp_server.py.
# ============================================================

from pathlib import Path

import pandas as pd
from fastmcp import FastMCP


# ============================================================
# STEP 1: CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

ACTIVE_EXCEL_PATH = UPLOAD_FOLDER / "active_excel.xlsx"
ACTIVE_CSV_PATH = UPLOAD_FOLDER / "active_data.csv"


# ============================================================
# STEP 2: CREATE PANDAS MCP SERVER
# ============================================================

mcp = FastMCP(
    name="Pandas Analytics MCP Server",
    instructions=(
        "This server performs structured analysis on the active "
        "Excel or CSV file using Pandas. Use these tools for dataset "
        "summaries, column statistics, grouping, aggregation, "
        "sorting, filtering, and correlations."
    )
)


# ============================================================
# STEP 3: ACTIVE DATASET HELPERS
# ============================================================

def get_active_dataset_path() -> Path:
    """
    Return the path of the most recently uploaded Excel or CSV file.

    Priority:
        1. The most recently modified active file
        2. Excel if only Excel exists
        3. CSV if only CSV exists
    """
    active_files = []

    if ACTIVE_EXCEL_PATH.exists():
        active_files.append(ACTIVE_EXCEL_PATH)

    if ACTIVE_CSV_PATH.exists():
        active_files.append(ACTIVE_CSV_PATH)

    if not active_files:
        raise FileNotFoundError(
            "No active Excel or CSV file found. "
            "Upload an Excel or CSV file first."
        )

    return max(
        active_files,
        key=lambda path: path.stat().st_mtime
    )


def load_active_dataset() -> pd.DataFrame:
    """
    Load the currently active Excel or CSV file.
    """
    active_path = get_active_dataset_path()

    # Read Excel files.
    if active_path.suffix.lower() in [".xlsx", ".xlsm"]:
        df = pd.read_excel(
            active_path,
            sheet_name=0,
            engine="openpyxl"
        )

    # Read CSV files.
    else:
        df = pd.read_csv(
            active_path,
            encoding="utf-8-sig"
        )

    if df.empty:
        raise ValueError(
            "The active dataset contains no data."
        )

    return df


def validate_column(df: pd.DataFrame, column: str) -> None:
    """
    Check whether a column exists in the active dataset.
    """
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found. "
            f"Available columns: {list(df.columns)}"
        )


def get_numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    """
    Convert a column to numeric values and remove invalid values.
    """
    validate_column(df, column)

    numeric_series = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    numeric_series = numeric_series.dropna()

    if numeric_series.empty:
        raise ValueError(
            f"Column '{column}' contains no numeric data."
        )

    return numeric_series


# ============================================================
# STEP 4: TOOL 1: DATASET SUMMARY
# ============================================================

@mcp.tool
def get_excel_summary() -> str:
    """
    Return a summary of the active Excel or CSV file.

    Includes:
    - Row count
    - Column names
    - Data types
    - Missing values
    - Numeric statistics
    """
    df = load_active_dataset()

    numeric_summary = df.describe(include="number").to_string()

    return (
        f"Rows: {len(df)}\n"
        f"Columns: {list(df.columns)}\n\n"
        f"Data Types:\n"
        f"{df.dtypes.to_string()}\n\n"
        f"Missing Values:\n"
        f"{df.isna().sum().to_string()}\n\n"
        f"Numeric Summary:\n"
        f"{numeric_summary}"
    )


# ============================================================
# STEP 5: TOOL 2: COLUMN STATISTIC
# ============================================================

@mcp.tool
def calculate_column_statistic(
    column: str,
    operation: str
) -> float:
    """
    Calculate a statistic for a numeric column.

    Args:
        column: Numeric column name.
        operation: sum, mean, min, max, median, or count.
    """
    df = load_active_dataset()

    numeric_series = get_numeric_column(df, column)

    operation = operation.lower().strip()

    if operation == "sum":
        result = numeric_series.sum()

    elif operation == "mean":
        result = numeric_series.mean()

    elif operation == "min":
        result = numeric_series.min()

    elif operation == "max":
        result = numeric_series.max()

    elif operation == "median":
        result = numeric_series.median()

    elif operation == "count":
        result = numeric_series.count()

    else:
        raise ValueError(
            "Unsupported operation. "
            "Use sum, mean, min, max, median, or count."
        )

    return float(result)


# ============================================================
# STEP 6: TOOL 3: GROUP AND AGGREGATE
# ============================================================

@mcp.tool
def group_and_aggregate(
    group_by: str,
    column: str,
    operation: str
) -> str:
    """
    Group the active dataset by one column and aggregate
    another numeric column.

    Args:
        group_by: Column used to group rows.
        column: Numeric column to aggregate.
        operation: sum, mean, count, min, or max.
    """
    df = load_active_dataset()

    validate_column(df, group_by)
    validate_column(df, column)

    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    )

    df = df.dropna(subset=[column])

    operation = operation.lower().strip()

    if operation == "sum":
        result = df.groupby(group_by)[column].sum()

    elif operation == "mean":
        result = df.groupby(group_by)[column].mean()

    elif operation == "count":
        result = df.groupby(group_by)[column].count()

    elif operation == "min":
        result = df.groupby(group_by)[column].min()

    elif operation == "max":
        result = df.groupby(group_by)[column].max()

    else:
        raise ValueError(
            "Unsupported operation. "
            "Use sum, mean, count, min, or max."
        )

    return result.to_string()


# ============================================================
# STEP 7: TOOL 4: FILTER ROWS
# ============================================================

@mcp.tool
def filter_excel_data(
    column: str,
    operator: str,
    value: str,
    limit: int = 20
) -> str:
    """
    Filter rows from the active Excel or CSV file.

    Args:
        column: Column to filter.
        operator: equals, not_equals, greater_than,
                  less_than, or contains.
        value: Value to compare against.
        limit: Maximum number of rows to return.
    """
    df = load_active_dataset()

    validate_column(df, column)

    operator = operator.lower().strip()

    if operator == "equals":
        filtered_df = df[
            df[column].astype(str) == value
        ]

    elif operator == "not_equals":
        filtered_df = df[
            df[column].astype(str) != value
        ]

    elif operator == "greater_than":
        numeric_value = pd.to_numeric(value, errors="coerce")

        numeric_column = pd.to_numeric(
            df[column],
            errors="coerce"
        )

        filtered_df = df[
            numeric_column > numeric_value
        ]

    elif operator == "less_than":
        numeric_value = pd.to_numeric(value, errors="coerce")

        numeric_column = pd.to_numeric(
            df[column],
            errors="coerce"
        )

        filtered_df = df[
            numeric_column < numeric_value
        ]

    elif operator == "contains":
        filtered_df = df[
            df[column]
            .astype(str)
            .str.contains(
                value,
                case=False,
                na=False
            )
        ]

    else:
        raise ValueError(
            "Unsupported operator. "
            "Use equals, not_equals, greater_than, "
            "less_than, or contains."
        )

    if filtered_df.empty:
        return "No rows matched the filter condition."

    return filtered_df.head(limit).to_string(index=False)


# ============================================================
# STEP 8: TOOL 5: SORT ROWS
# ============================================================

@mcp.tool
def sort_excel_data(
    column: str,
    order: str = "descending",
    limit: int = 20
) -> str:
    """
    Sort the active Excel or CSV data by one column.

    Args:
        column: Column used for sorting.
        order: ascending or descending.
        limit: Maximum number of rows to return.
    """
    df = load_active_dataset()

    validate_column(df, column)

    order = order.lower().strip()

    if order == "ascending":
        ascending = True

    elif order == "descending":
        ascending = False

    else:
        raise ValueError(
            "Unsupported order. Use ascending or descending."
        )

    sorted_df = df.sort_values(
        by=column,
        ascending=ascending
    )

    return sorted_df.head(limit).to_string(index=False)


# ============================================================
# STEP 9: TOOL 6: CORRELATION BETWEEN TWO COLUMNS
# ============================================================

@mcp.tool
def calculate_correlation(
    column_a: str,
    column_b: str
) -> float:
    """
    Calculate the Pearson correlation between two numeric columns.

    Args:
        column_a: First numeric column.
        column_b: Second numeric column.
    """
    df = load_active_dataset()

    validate_column(df, column_a)
    validate_column(df, column_b)

    series_a = pd.to_numeric(
        df[column_a],
        errors="coerce"
    )

    series_b = pd.to_numeric(
        df[column_b],
        errors="coerce"
    )

    cleaned_df = pd.concat(
        [series_a, series_b],
        axis=1
    ).dropna()

    if cleaned_df.empty:
        raise ValueError(
            "Not enough numeric data to calculate correlation."
        )

    correlation = cleaned_df[column_a].corr(
        cleaned_df[column_b]
    )

    return float(correlation)


# ============================================================
# STEP 10: RUN PANDAS MCP SERVER USING STDIO
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")