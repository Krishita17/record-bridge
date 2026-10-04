"""End-to-end pipeline: ingest -> validate -> correct/audit -> dedupe -> load.

This is the integrated design that is the project: one tool that takes messy
multi-source intake all the way to a clean, governed dataset with a complete
change history.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .audit import AuditLogger
from .config import Config
from .db import connect, init_schema
from .dedupe import DuplicateResolver
from .ingest import ingest_file
from .validate import Validator

_DATE_FORMATS = ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]


@dataclass
class PipelineReport:
    upload_id: str
    total_rows: int = 0
    passed: int = 0
    failed: int = 0
    duplicates_found: int = 0
    auto_merged: int = 0
    held: int = 0
    corrections: int = 0
    loaded_clean: int = 0
    quality_score: float = 0.0
    extras: dict = field(default_factory=dict)


def _normalize_dob(value: str) -> str | None:
    """Return an ISO date string if a non-ISO date can be parsed, else None."""
    value = str(value).strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return None  # already ISO
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def run_pipeline(
    intake_path: str | Path,
    *,
    config_path: str | Path = "config/rules.yaml",
    db_path: str | Path = "data/recordbridge.db",
    reset: bool = True,
    index_col: str = "row_index",
    drop_from_payload: list[str] | None = None,
) -> tuple[PipelineReport, dict[str, pd.DataFrame]]:
    """Run the full pipeline on ``intake_path`` and persist results to the DB.

    Returns a :class:`PipelineReport` and a dict of result DataFrames
    (validation_errors, duplicate_pairs, students_clean, correction_log).
    """
    cfg = Config.load(config_path)
    conn = connect(db_path)
    init_schema(conn, reset=reset)

    drop_from_payload = drop_from_payload or []
    upload_id, df = ingest_file(conn, intake_path, drop_columns=drop_from_payload)
    audit = AuditLogger(conn, upload_id)

    # Ensure a stable index column exists for joins/auditing.
    if index_col not in df.columns:
        df = df.reset_index().rename(columns={"index": index_col})

    # --- 1. auto-corrections (normalisation), each logged -------------------
    corrections = 0
    for i in df.index:
        ref = df.at[i, index_col]
        # trim + normalise email case
        if "email" in df.columns:
            old = df.at[i, "email"]
            new = str(old).strip().lower()
            if new != str(old):
                df.at[i, "email"] = new
                audit.log(student_ref=ref, field="email", old_value=old, new_value=new, action="normalize")
                corrections += 1
        # normalise parseable non-ISO dates
        if "dob" in df.columns:
            old = df.at[i, "dob"]
            iso = _normalize_dob(old)
            if iso:
                df.at[i, "dob"] = iso
                audit.log(student_ref=ref, field="dob", old_value=old, new_value=iso, action="normalize")
                corrections += 1
    audit.commit()

    # --- 2. validation ------------------------------------------------------
    validator = Validator(cfg)
    vres = validator.validate(df, index_col=index_col)
    detected_at = datetime.now(timezone.utc).isoformat()
    for err in vres.errors:
        conn.execute(
            "INSERT INTO validation_errors "
            "(upload_id, student_ref, field, rule_violated, severity, detail, detected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (upload_id, str(err["row_index"]), err["field"], err["rule_violated"],
             err["severity"], err["detail"], detected_at),
        )
        audit.log(student_ref=err["row_index"], field=err["field"],
                  old_value=err["rule_violated"], new_value=None, action="validate")
    conn.commit()

    # --- 3. dedupe ----------------------------------------------------------
    # Governance flow: validation failures are exceptions pulled OUT before
    # de-duplication. We de-duplicate records that are otherwise clean, not
    # broken ones -- this also stops invalid key values (e.g. a malformed
    # student_id shared by several rejected rows) from creating false matches.
    passing_refs = {ref for ref, st in vres.row_status.items() if st == "clean"}
    dedupe_df = df[df[index_col].isin(passing_refs)]
    resolver = DuplicateResolver(cfg.fuzzy, cfg.exact_keys)
    dres = resolver.resolve(dedupe_df, index_col=index_col)
    for p in dres.pairs:
        conn.execute(
            "INSERT INTO duplicate_pairs "
            "(upload_id, record_a, record_b, match_type, similarity_score, resolution) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (upload_id, str(p["record_a"]), str(p["record_b"]),
             p["match_type"], p["similarity_score"], p["resolution"]),
        )
        action = "merge" if p["resolution"] == "auto-merge" else "hold"
        audit.log(student_ref=p["record_b"], field=None,
                  old_value=f"pair with {p['record_a']} ({p['match_type']}, {p['similarity_score']})",
                  new_value=p["resolution"], action=action)
    conn.commit()

    # --- 4. load clean records ---------------------------------------------
    loaded = 0
    clean_cols = [c for c in cfg.schema if c in df.columns]
    for i in df.index:
        ref = df.at[i, index_col]
        status = vres.row_status.get(ref, "clean")
        disp = dres.row_disposition.get(ref)
        if status == "failed":
            continue  # exceptions handled via validation_errors, not loaded
        if disp == "auto-merge":
            continue  # duplicate 'loser' is merged away, not loaded
        row_status = "held" if disp == "hold" else "clean"
        values = {c: df.at[i, c] for c in clean_cols}
        try:
            gpa = float(values.get("gpa")) if values.get("gpa") not in ("", None) else None
        except (TypeError, ValueError):
            gpa = None
        conn.execute(
            "INSERT OR REPLACE INTO students_clean "
            "(student_id, first_name, last_name, dob, email, phone, program, gpa, status, upload_id, stage_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                values.get("student_id"), values.get("first_name"), values.get("last_name"),
                values.get("dob"), values.get("email"), values.get("phone"),
                values.get("program"), gpa, row_status, upload_id,
                int(df.at[i, "stage_ref"]) if "stage_ref" in df.columns else None,
            ),
        )
        audit.log(student_ref=ref, field=None, old_value=None,
                  new_value=row_status, action="load")
        loaded += 1
    audit.commit()

    # --- 5. batch summary ---------------------------------------------------
    total = len(df)
    passed = vres.n_passed_rows
    failed = vres.n_failed_rows
    dupes = dres.n_auto_merge + dres.n_hold
    quality = round(100.0 * passed / total, 2) if total else 0.0
    conn.execute(
        "UPDATE upload_batches SET total_rows=?, passed=?, failed=?, duplicates_found=? "
        "WHERE upload_id=?",
        (total, passed, failed, dupes, upload_id),
    )
    conn.commit()

    report = PipelineReport(
        upload_id=upload_id, total_rows=total, passed=passed, failed=failed,
        duplicates_found=dupes, auto_merged=dres.n_auto_merge, held=dres.n_hold,
        corrections=corrections, loaded_clean=loaded, quality_score=quality,
    )

    frames = {
        "validation_errors": vres.errors_df(),
        "duplicate_pairs": dres.pairs_df(),
        "students_clean": pd.read_sql_query("SELECT * FROM students_clean", conn),
        "correction_log": pd.read_sql_query("SELECT * FROM correction_log", conn),
    }
    conn.close()
    return report, frames
