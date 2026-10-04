"""Ingestion layer.

Bulk-loads CSV/Excel, auto-detects encoding and headers, and stages every raw
row *untouched* in ``students_staging``. The untouched raw copy is what makes
the whole pipeline auditable -- you can always reconstruct what arrived.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_ENCODINGS = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]


def detect_encoding(path: str | Path) -> str:
    """Best-effort encoding detection by trial decode (no external deps)."""
    path = Path(path)
    raw = path.read_bytes()
    for enc in _ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"  # last resort: never fails


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_any(path: str | Path) -> tuple[pd.DataFrame, str]:
    """Read a CSV or Excel file into a DataFrame (all columns as strings).

    Returns the DataFrame and the detected encoding ('n/a' for Excel).
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(path, dtype=str)
        return df.fillna(""), "n/a"
    enc = detect_encoding(path)
    df = pd.read_csv(path, dtype=str, encoding=enc, keep_default_na=False)
    return df, enc


def ingest_file(
    conn: sqlite3.Connection,
    path: str | Path,
    *,
    drop_columns: list[str] | None = None,
) -> tuple[str, pd.DataFrame]:
    """Load a file and stage its raw rows untouched.

    ``drop_columns`` lets callers exclude bookkeeping columns (e.g. the
    ground-truth ``row_index``) from the staged payload while still preserving
    them for evaluation. The staged ``raw_row`` JSON always reflects exactly
    what was read.

    Returns the ``upload_id`` and the ingested DataFrame (with a ``stage_ref``
    column giving each row's staging reference).
    """
    path = Path(path)
    df, _enc = read_any(path)
    upload_id = uuid.uuid4().hex[:12]
    uploaded_at = _now()

    conn.execute(
        "INSERT INTO upload_batches (upload_id, file_name, total_rows, run_at) "
        "VALUES (?, ?, ?, ?)",
        (upload_id, path.name, len(df), uploaded_at),
    )

    stage_refs = []
    for i, (_, row) in enumerate(df.iterrows()):
        raw_row = json.dumps(row.to_dict(), ensure_ascii=False)
        cur = conn.execute(
            "INSERT INTO students_staging "
            "(upload_id, row_index, raw_row, source_file, uploaded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (upload_id, i, raw_row, path.name, uploaded_at),
        )
        stage_refs.append(cur.lastrowid)
    conn.commit()

    out = df.copy()
    out["stage_ref"] = stage_refs
    if drop_columns:
        keep = [c for c in out.columns if c not in set(drop_columns)]
        # retain dropped columns separately for evaluation convenience
        out = out[keep + [c for c in drop_columns if c in out.columns]]
    return upload_id, out
