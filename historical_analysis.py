from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# USER SETTINGS
# ============================================================

# Select ONE parameter for the file being analyzed.
#
# Example for discharge:
# PARAMETER_NAME = "Discharge"
# UNITS = "cfs"
# MIN_VALID_VALUE = 0
#
# Example for stage:
# PARAMETER_NAME = "Stage"
# UNITS = "ft"
# MIN_VALID_VALUE = None
#
# Do not enter both parameter sets at the same time.
# Update these settings to match the current dataset.
# Change these for each station/data file.
STATION_NAME = "LCH"
SOURCE = "CDEC"          # Use "CDEC" or "WDL"
PARAMETER_NAME = "Stage"
UNITS = "ft"
MIN_VALID_VALUE = None         # Minimum valid measurement value.

# Water-year range.
# Set either one to None if you do not want a limit.
START_WY = 2006
END_WY = 2026


# ============================================================
# PROJECT FOLDERS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

RAW_FOLDER = BASE_DIR / "data" / "raw"
PROCESSED_FOLDER = BASE_DIR / "data" / "processed"
OUTPUT_FOLDER = BASE_DIR / "output"

RAW_FOLDER.mkdir(parents=True, exist_ok=True)
PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================
# COLUMN NAME OPTIONS
# ============================================================

DATE_ALIASES = [
    "date time",
    "datetime",
    "date",
    "measurement date",
    "sample date",
    "observation date",
    "obs date",
]

VALUE_ALIASES = [
    "value",
    "obs value",
    "result",
    "measurement",
    "measured value",
    "result value",
    "sensor value",
]

UNIT_ALIASES = [
    "units",
    "unit",
    "measurement units",
    "value units",
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_column_name(name):
    """
    Standardize a column name so different naming styles
    can be compared more easily.
    """
    return (
        str(name)
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
    )


def find_input_file():
    """
    Find a single CSV or Excel file in data/raw.
    """

    files = []

    for extension in ("*.csv", "*.xlsx", "*.xls"):
        files.extend(RAW_FOLDER.glob(extension))

    if len(files) == 0:
        raise FileNotFoundError(
            "\nNo CSV or Excel file was found in:\n"
            f"{RAW_FOLDER}\n\n"
            "Place one CDEC or WDL file in data/raw and run again."
        )

    if len(files) > 1:
        print("\nMore than one input file was found:")
        for file in files:
            print(f" - {file.name}")

        raise RuntimeError(
            "\nFor this first version, leave only ONE file in data/raw."
        )

    return files[0]


def read_file(file_path, skiprows=0):
    """
    Read CSV or Excel data.
    """

    extension = file_path.suffix.lower()

    if extension == ".csv":
        return pd.read_csv(
            file_path,
            skiprows=skiprows,
            low_memory=False
        )

    if extension in (".xlsx", ".xls"):
        return pd.read_excel(
            file_path,
            skiprows=skiprows
        )

    raise ValueError(
        f"Unsupported file type: {extension}"
    )


def unique_output_path(base_path):
    """
    Return a unique output path when a stale or locked output file exists.
    """
    if not base_path.exists():
        return base_path

    stem = base_path.stem
    suffix = base_path.suffix
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    candidate = base_path.with_name(f"{stem}_{timestamp}{suffix}")
    counter = 1

    while candidate.exists():
        candidate = base_path.with_name(f"{stem}_{timestamp}_{counter}{suffix}")
        counter += 1

    return candidate


def find_header_row(file_path):
    """
    Try different header locations for files containing
    metadata lines above the actual table.
    """

    if file_path.suffix.lower() in (".xlsx", ".xls"):
        return 0

    for skip in range(0, 20):

        try:
            test = pd.read_csv(
                file_path,
                skiprows=skip,
                nrows=10,
                low_memory=False
            )

            cleaned_columns = [
                clean_column_name(column)
                for column in test.columns
            ]

            # Look for a recognizable date column.
            for alias in DATE_ALIASES:
                if alias in cleaned_columns:
                    return skip

        except Exception:
            continue

    # If automatic detection fails,
    # start from the first row.
    return 0


def find_date_column(df):
    """
    First look for common date column names.
    If none are found, determine which column looks
    most like dates.
    """

    column_lookup = {
        clean_column_name(column): column
        for column in df.columns
    }

    for alias in DATE_ALIASES:
        if alias in column_lookup:
            return column_lookup[alias]

    best_column = None
    best_score = 0

    for column in df.columns:

        try:
            parsed = pd.to_datetime(
                df[column],
                errors="coerce"
            )

            score = parsed.notna().mean()

            if score > best_score:
                best_column = column
                best_score = score

        except Exception:
            continue

    if best_column is None or best_score < 0.50:
        raise ValueError(
            "Could not automatically identify the date column."
        )

    return best_column


def find_value_column(df, date_column):
    """
    First look for common measurement column names.
    If none are found, look for the strongest numeric column.
    """

    column_lookup = {
        clean_column_name(column): column
        for column in df.columns
    }

    for alias in VALUE_ALIASES:

        if alias in column_lookup:

            candidate = column_lookup[alias]

            if candidate != date_column:
                return candidate

    best_column = None
    best_score = 0

    for column in df.columns:

        if column == date_column:
            continue

        try:
            numeric = pd.to_numeric(
                df[column],
                errors="coerce"
            )

            score = numeric.notna().mean()

            if score > best_score:
                best_column = column
                best_score = score

        except Exception:
            continue

    if best_column is None or best_score < 0.50:
        raise ValueError(
            "Could not automatically identify the measurement column."
        )

    return best_column


def normalize_unit(raw_value):
    """
    Normalize common unit strings to a consistent canonical form.
    """
    if raw_value is None or pd.isna(raw_value):
        return None

    unit = str(raw_value).strip().lower()
    if not unit:
        return None

    mapping = {
        "cfs": "cfs",
        "ft": "ft",
        "feet": "ft",
        "foot": "ft",
        "ft3/s": "cfs",
        "cms": "cms",
        "m3/s": "cms",
        "m": "m",
        "meter": "m",
        "meters": "m",
        "metre": "m",
        "metres": "m",
        "in": "in",
        "inch": "in",
        "inches": "in",
        "mm": "mm",
        "millimeter": "mm",
        "millimeters": "mm",
        "millimetre": "mm",
        "millimetres": "mm",
        "ac-ft": "ac-ft",
        "acft": "ac-ft",
        "acre-ft": "ac-ft",
        "acre ft": "ac-ft",
    }

    return mapping.get(unit, unit)


def detect_units(df, fallback_units):
    """
    Prefer the units column in the source file when present,
    otherwise fall back to the configured default.
    """
    column_lookup = {
        clean_column_name(column): column
        for column in df.columns
    }

    for alias in UNIT_ALIASES:
        if alias in column_lookup:
            unit_column = column_lookup[alias]
            values = df[unit_column].dropna().astype(str).str.strip()
            values = values[values != ""]

            if values.empty:
                continue

            normalized = values.map(normalize_unit)
            normalized = normalized[normalized.notna()]

            if not normalized.empty:
                return normalized.mode().iloc[0]

    return fallback_units


# ============================================================
# FIND INPUT FILE
# ============================================================

def main():
    global UNITS

    input_file = find_input_file()

    print("\n========================================")
    print("HISTORICAL DATA ANALYSIS")
    print("========================================")

    print(f"\nInput file: {input_file.name}")
    print(f"Station: {STATION_NAME}")
    print(f"Source: {SOURCE}")
    print(f"Parameter: {PARAMETER_NAME}")

    # ============================================================
    # FIND HEADER
    # ============================================================

    header_row = find_header_row(input_file)

    print(f"\nDetected header offset: {header_row}")


    # ============================================================
    # READ ORIGINAL DATA
    # ============================================================

    df_original = read_file(
        input_file,
        skiprows=header_row
    )

    UNITS = detect_units(df_original, UNITS)

    print(f"Units: {UNITS}")
    print("\nColumns detected:")

    for column in df_original.columns:
        print(f" - {column}")


    # ============================================================
    # FIND DATE AND VALUE COLUMNS
    # ============================================================

    date_column = find_date_column(df_original)

    value_column = find_value_column(
        df_original,
        date_column
    )

    print("\nAutomatically selected:")
    print(f"Date column: {date_column}")
    print(f"Value column: {value_column}")


    # ============================================================
    # STANDARDIZE DATA
    # ============================================================

    df = df_original[
        [
            date_column,
            value_column
        ]
    ].copy()

    df.columns = [
        "Date",
        "Value"
    ]


    # ============================================================
    # CLEAN DATA
    # ============================================================

    rows_before = len(df)

    # Convert dates and values to usable numeric/datetime types.
    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    df["Value"] = pd.to_numeric(
        df["Value"],
        errors="coerce"
    )

    missing_dates = df["Date"].isna().sum()
    missing_values = df["Value"].isna().sum()
    invalid_low_count = 0

    if MIN_VALID_VALUE is not None:
        invalid_low_count = (df["Value"] < MIN_VALID_VALUE).sum()
        df.loc[df["Value"] < MIN_VALID_VALUE, "Value"] = np.nan

    # Drop rows with missing date/value after conversion.
    df = df.dropna(
        subset=[
            "Date",
            "Value"
        ]
    ).copy()

    rows_after = len(df)

    # ============================================================
    # QA/QC REPORT
    # ============================================================

    print("\nData cleaning summary:")
    print(f"Rows before cleaning: {rows_before}")
    print(f"Missing/non-numeric dates: {missing_dates}")
    print(f"Missing/non-numeric values: {missing_values}")
    if MIN_VALID_VALUE is not None:
        print(f"Values below {MIN_VALID_VALUE} {UNITS}: {invalid_low_count}")
    print(f"Rows after cleaning: {rows_after}")
    print(f"Rows removed: {rows_before - rows_after}")


    # ============================================================
    # ADD WATER YEAR
    # ============================================================

    df["Water Year"] = df["Date"].dt.year

    # October, November, and December belong
    # to the next water year.
    df.loc[
        df["Date"].dt.month >= 10,
        "Water Year"
    ] += 1


    # ============================================================
    # LIMIT WATER-YEAR RANGE
    # ============================================================

    if START_WY is not None:

        df = df[
            df["Water Year"] >= START_WY
        ].copy()


    if END_WY is not None:

        df = df[
            df["Water Year"] <= END_WY
        ].copy()


    if df.empty:
        raise RuntimeError(
            "\nNo valid data remain after applying "
            "the water-year limits."
        )


    # ============================================================
    # STATISTICAL FUNCTIONS
    # ============================================================

    def p25(series):
        return series.quantile(0.25)


    def p50(series):
        return series.quantile(0.50)


    def p95(series):
        return series.quantile(0.95)


    def p99(series):
        return series.quantile(0.99)


    # ============================================================
    # WATER-YEAR SUMMARY
    # ============================================================

    summary = (
        df.groupby("Water Year")["Value"]
        .agg(
            Count="count",
            Minimum="min",
            Maximum="max",
            Mean="mean",
            Median="median",
            P25=p25,
            P50=p50,
            P95=p95,
            P99=p99
        )
        .reset_index()
    )


    # ============================================================
    # ROUND STATISTICS
    # ============================================================

    stat_columns = [
        "Minimum",
        "Maximum",
        "Mean",
        "Median",
        "P25",
        "P50",
        "P95",
        "P99"
    ]

    summary[stat_columns] = (
        summary[stat_columns]
        .round(2)
    )


    # ============================================================
    # ADD STATION INFORMATION
    # ============================================================

    summary.insert(
        0,
        "Station",
        STATION_NAME
    )

    summary.insert(
        1,
        "Source",
        SOURCE
    )

    summary.insert(
        3,
        "Parameter",
        PARAMETER_NAME
    )

    summary.insert(
        4,
        "Units",
        UNITS
    )


    # ============================================================
    # PERIOD-OF-RECORD SUMMARY
    # ============================================================

    period_summary = pd.DataFrame(
        {
            "Station": [STATION_NAME],
            "Source": [SOURCE],
            "Parameter": [PARAMETER_NAME],
            "Units": [UNITS],

            "Start Date": [
                df["Date"].min()
            ],

            "End Date": [
                df["Date"].max()
            ],

            "Number of Measurements": [
                len(df)
            ],

            "Minimum": [
                df["Value"].min()
            ],

            "Maximum": [
                df["Value"].max()
            ],

            "Mean": [
                df["Value"].mean()
            ],

            "Median": [
                df["Value"].median()
            ],

            "P25": [
                df["Value"].quantile(0.25)
            ],

            "P50": [
                df["Value"].quantile(0.50)
            ],

            "P95": [
                df["Value"].quantile(0.95)
            ],

            "P99": [
                df["Value"].quantile(0.99)
            ]
        }
    )


    period_summary[stat_columns] = (
        period_summary[stat_columns]
        .round(2)
    )


    # ============================================================
    # SAVE CLEANED DATA
    # ============================================================

    processed_csv = unique_output_path(
        PROCESSED_FOLDER /
        f"{STATION_NAME}_{SOURCE}_cleaned.csv"
    )

    df.to_csv(
        processed_csv,
        index=False
    )


    # ============================================================
    # EXPORT EXCEL WORKBOOK
    # ============================================================

    output_file = unique_output_path(
        OUTPUT_FOLDER /
        f"{STATION_NAME}_{SOURCE}_Historical_Analysis.xlsx"
    )

    with pd.ExcelWriter(
        output_file,
        engine="openpyxl"
    ) as writer:

        df_original.to_excel(
            writer,
            sheet_name="Original Data",
            index=False
        )

        df.to_excel(
            writer,
            sheet_name="Cleaned Data",
            index=False
        )

        summary.to_excel(
            writer,
            sheet_name="Water Year Summary",
            index=False
        )

        period_summary.to_excel(
            writer,
            sheet_name="Period Summary",
            index=False
        )


    # ============================================================
    # FINISHED
    # ============================================================

    print("\n========================================")
    print("ANALYSIS COMPLETE")
    print("========================================")

    print(
        f"\nFirst water year: "
        f"{int(df['Water Year'].min())}"
    )

    print(
        f"Last water year: "
        f"{int(df['Water Year'].max())}"
    )

    print(
        f"Valid measurements: {len(df)}"
    )

    print(
        f"\nProcessed data:\n{processed_csv}"
    )

    print(
        f"\nExcel results:\n{output_file}"
    )


if __name__ == "__main__":
    main()
