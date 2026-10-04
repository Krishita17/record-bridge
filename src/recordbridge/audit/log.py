"""Correction & audit logging.

Every change -- an auto-correction, a merge, a hold, or the final load -- is
recorded in ``correction_log`` with field, old->new, action, who, and when.
This is the governance backbone: no silent edits, full traceability.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


class AuditLogger:
    """Writes immutable correction-log entries for one upload batch."""

    def __init__(self, conn: sqlite3.Connection, upload_id: str, changed_by: str = "recordbridge"):
        self.conn = conn
        self.upload_id = upload_id
        self.changed_by = changed_by

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def log(
        self,
        *,
        student_ref,
        field: str | None,
        old_value,
        new_value,
        action: str,
    ) -> None:
        self.conn.execute(
            "INSERT INTO correction_log "
            "(upload_id, student_ref, field, old_value, new_value, action, changed_by, changed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.upload_id,
                str(student_ref),
                field,
                None if old_value is None else str(old_value),
                None if new_value is None else str(new_value),
                action,
                self.changed_by,
                self._now(),
            ),
        )

    def commit(self) -> None:
        self.conn.commit()
