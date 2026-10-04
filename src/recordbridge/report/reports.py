"""Exception reports and audit-trail excerpts for records staff."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_exception_report(
    errors: pd.DataFrame,
    out_path: str | Path = "reports/exception_report.md",
    *,
    limit: int = 25,
) -> Path:
    """Render a human-readable exception report (what failed, why, which row)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# RecordBridge Exception Report", ""]
    if errors.empty:
        lines.append("No validation exceptions were detected. ✅")
    else:
        n_err = int((errors["severity"] == "error").sum())
        n_warn = int((errors["severity"] == "warning").sum())
        lines += [
            f"- **Total exceptions:** {len(errors)} "
            f"({n_err} errors, {n_warn} warnings)",
            f"- **Distinct rows affected:** {errors['row_index'].nunique()}",
            "",
            "## Breakdown by field",
            "",
        ]
        by_field = errors.groupby(["field", "severity"]).size().reset_index(name="count")
        lines.append(by_field.to_markdown(index=False))
        lines += ["", f"## Sample exceptions (first {limit})", ""]
        sample = errors.head(limit)[["row_index", "field", "severity", "rule_violated"]]
        lines.append(sample.to_markdown(index=False))

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def write_audit_excerpt(
    corrections: pd.DataFrame,
    out_path: str | Path = "reports/audit_excerpt.md",
    *,
    limit: int = 20,
) -> Path:
    """Render a few correction_log rows (field, old->new, action, who, when)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["# RecordBridge Audit-Trail Excerpt", ""]
    if corrections.empty:
        lines.append("No corrections were logged.")
    else:
        lines += [
            f"- **Total log entries:** {len(corrections)}",
            "",
            "## Actions summary",
            "",
            corrections.groupby("action").size().reset_index(name="count").to_markdown(index=False),
            "",
            f"## Sample entries (first {limit})",
            "",
        ]
        cols = ["student_ref", "field", "old_value", "new_value", "action", "changed_by", "changed_at"]
        cols = [c for c in cols if c in corrections.columns]
        lines.append(corrections.head(limit)[cols].to_markdown(index=False))

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path
