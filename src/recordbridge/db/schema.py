"""Database schema and connection helpers.

SQLite is the default (zero-config, fully reproducible). The backend is kept
deliberately thin and pluggable: the schema is standard SQL, so adding a
SQL Server backend means swapping the connection factory, not the pipeline.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Schema implemented exactly as specified in the project blueprint.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS upload_batches (
    upload_id        TEXT PRIMARY KEY,
    file_name        TEXT NOT NULL,
    total_rows       INTEGER NOT NULL DEFAULT 0,
    passed           INTEGER NOT NULL DEFAULT 0,
    failed           INTEGER NOT NULL DEFAULT 0,
    duplicates_found INTEGER NOT NULL DEFAULT 0,
    run_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students_staging (
    stage_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id   TEXT NOT NULL,
    row_index   INTEGER NOT NULL,
    raw_row     TEXT NOT NULL,          -- JSON of the row exactly as it arrived
    source_file TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    FOREIGN KEY (upload_id) REFERENCES upload_batches(upload_id)
);

CREATE TABLE IF NOT EXISTS students_clean (
    student_id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name  TEXT,
    dob        TEXT,
    email      TEXT,
    phone      TEXT,
    program    TEXT,
    gpa        REAL,
    status     TEXT,                    -- clean | merged | held
    upload_id  TEXT,
    stage_id   INTEGER,                 -- link back to staging row (auditability)
    FOREIGN KEY (upload_id) REFERENCES upload_batches(upload_id),
    FOREIGN KEY (stage_id)  REFERENCES students_staging(stage_id)
);

CREATE TABLE IF NOT EXISTS validation_errors (
    error_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id     TEXT NOT NULL,
    student_ref   TEXT,                 -- staging row index / student id
    field         TEXT,
    rule_violated TEXT NOT NULL,
    severity      TEXT NOT NULL,        -- error | warning
    detail        TEXT,
    detected_at   TEXT NOT NULL,
    FOREIGN KEY (upload_id) REFERENCES upload_batches(upload_id)
);

CREATE TABLE IF NOT EXISTS duplicate_pairs (
    pair_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id        TEXT,
    record_a         TEXT NOT NULL,     -- staging row index of record A
    record_b         TEXT NOT NULL,     -- staging row index of record B
    match_type       TEXT NOT NULL,     -- exact | fuzzy
    similarity_score REAL,
    resolution       TEXT NOT NULL,     -- auto-merge | keep | hold
    FOREIGN KEY (upload_id) REFERENCES upload_batches(upload_id)
);

CREATE TABLE IF NOT EXISTS correction_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_id   TEXT,
    student_ref TEXT,
    field       TEXT,
    old_value   TEXT,
    new_value   TEXT,
    action      TEXT NOT NULL,          -- validate | normalize | merge | hold | load
    changed_by  TEXT NOT NULL,
    changed_at  TEXT NOT NULL,
    FOREIGN KEY (upload_id) REFERENCES upload_batches(upload_id)
);
"""


def connect(db_path: str | Path = "data/recordbridge.db") -> sqlite3.Connection:
    """Open (and create if needed) a SQLite connection with sensible defaults."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn: sqlite3.Connection, *, reset: bool = False) -> None:
    """Create all tables. When ``reset`` is True, drop existing tables first."""
    if reset:
        for table in (
            "correction_log",
            "duplicate_pairs",
            "validation_errors",
            "students_clean",
            "students_staging",
            "upload_batches",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table};")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
