import pandas as pd
from pathlib import Path


SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def read_table(file_path: str) -> list[dict]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    if suffix == ".csv":
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)

    df = df.fillna("")
    return df.to_dict(orient="records")
