"""Reads an uploaded Excel or CSV file.

Two things are extracted:

* the raw header row, exactly as written in the file, and
* a DataFrame for counting rows.

The raw header row matters: pandas silently renames repeated headers
(``KUNNR`` and a second ``KUNNR`` become ``KUNNR`` and ``KUNNR.1``), which would
hide the duplicate-column condition FR-009 requires us to report.

Anything unreadable becomes a FileRejectedError so callers never have to reason
about pandas or openpyxl exceptions.
"""
import csv
import io
from dataclasses import dataclass

import pandas as pd
from openpyxl import load_workbook

from app.validation.errors import FileRejectedError

_CSV_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


@dataclass(frozen=True)
class ParsedFile:
    """The result of reading an uploaded tabular file."""

    headers: list[str]
    row_count: int

    @property
    def column_count(self) -> int:
        return len(self.headers)


def _decode_csv(content: bytes, file_name: str) -> str:
    for encoding in _CSV_ENCODINGS:
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FileRejectedError(
        "CORRUPTED_FILE", f"'{file_name}' uses an unsupported text encoding."
    )


def _read_csv(content: bytes, file_name: str) -> ParsedFile:
    text = _decode_csv(content, file_name)
    try:
        header_row = next(csv.reader(io.StringIO(text)), [])
    except csv.Error as exc:
        raise FileRejectedError(
            "CORRUPTED_FILE",
            f"'{file_name}' could not be read as a CSV file.",
            {"reason": str(exc)[:300]},
        ) from exc

    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str)
    except pd.errors.EmptyDataError as exc:
        raise FileRejectedError(
            "EMPTY_FILE", f"'{file_name}' contains no rows or columns."
        ) from exc
    except Exception as exc:
        raise FileRejectedError(
            "CORRUPTED_FILE",
            f"'{file_name}' could not be read as a CSV file.",
            {"reason": str(exc)[:300]},
        ) from exc

    return ParsedFile(headers=[str(h) for h in header_row], row_count=int(frame.shape[0]))


def _read_excel(content: bytes, file_name: str) -> ParsedFile:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook[workbook.sheetnames[0]]
        header_row = list(next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ()))
        # openpyxl over-reports the used range, so drop trailing empties only.
        while header_row and header_row[-1] is None:
            header_row.pop()
        # An interior gap is a real blank header; keep it so it can be reported.
        headers = ["" if cell is None else str(cell) for cell in header_row]
        workbook.close()
    except FileRejectedError:
        raise
    except Exception as exc:
        raise FileRejectedError(
            "CORRUPTED_FILE",
            f"'{file_name}' could not be read as an Excel workbook.",
            {"reason": str(exc)[:300]},
        ) from exc

    try:
        frame = pd.read_excel(io.BytesIO(content), dtype=str)
    except Exception as exc:
        raise FileRejectedError(
            "CORRUPTED_FILE",
            f"'{file_name}' could not be read as an Excel workbook.",
            {"reason": str(exc)[:300]},
        ) from exc

    return ParsedFile(headers=headers, row_count=int(frame.shape[0]))


def read_tabular_file(content: bytes, file_name: str, extension: str) -> ParsedFile:
    """Parse the upload and guarantee it holds at least one column and one data row."""
    parsed = _read_csv(content, file_name) if extension == ".csv" else _read_excel(content, file_name)

    if parsed.column_count == 0:
        raise FileRejectedError("EMPTY_FILE", f"'{file_name}' has no columns.")
    if parsed.row_count == 0:
        raise FileRejectedError(
            "NO_DATA_ROWS",
            f"'{file_name}' has column headers but no data rows.",
            {"column_count": parsed.column_count},
        )
    return parsed
