"""Config-driven validation engine.

Rules are loaded from YAML (see :mod:`recordbridge.config`) and applied row by
row. Every failure is recorded with a severity -- nothing is ever silently
dropped. The engine is pure and side-effect free; persistence happens in the
pipeline so the validator stays unit-testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd

from ..config import Config

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y/%m/%d"]


@dataclass
class ValidationResult:
    """Outcome of validating a dataset."""

    errors: list[dict] = field(default_factory=list)  # one per failed check
    row_status: dict[int, str] = field(default_factory=dict)  # row_index -> clean|failed

    def errors_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            self.errors,
            columns=["row_index", "field", "rule_violated", "severity", "detail"],
        )

    @property
    def n_failed_rows(self) -> int:
        return sum(1 for s in self.row_status.values() if s == "failed")

    @property
    def n_passed_rows(self) -> int:
        return sum(1 for s in self.row_status.values() if s == "clean")


def _is_blank(value) -> bool:
    return value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == ""


def _parse_date(value: str) -> date | None:
    value = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


class Validator:
    """Applies the rules from a :class:`Config` to a DataFrame."""

    def __init__(self, config: Config):
        self.config = config
        self._checks = {
            "required": self._check_required,
            "email": self._check_email,
            "phone": self._check_phone,
            "date": self._check_date,
            "regex": self._check_regex,
            "range": self._check_range,
        }

    # -- individual checks: return an error-detail string, or None if OK -----
    def _check_required(self, value, params) -> str | None:
        return "value is blank" if _is_blank(value) else None

    def _check_email(self, value, params) -> str | None:
        if _is_blank(value):
            return None  # 'required' owns emptiness
        return None if _EMAIL_RE.match(str(value).strip()) else "malformed email"

    def _check_phone(self, value, params) -> str | None:
        if _is_blank(value):
            return None
        digits = re.sub(r"\D", "", str(value))
        min_digits = int((params or {}).get("min_digits", 10))
        return None if len(digits) >= min_digits else f"fewer than {min_digits} digits"

    def _check_date(self, value, params) -> str | None:
        if _is_blank(value):
            return None
        params = params or {}
        parsed = _parse_date(value)
        if parsed is None:
            return "unparseable date"
        if params.get("not_future") and parsed > date.today():
            return "date is in the future"
        min_year = params.get("min_year")
        if min_year and parsed.year < int(min_year):
            return f"year before {min_year}"
        return None

    def _check_regex(self, value, params) -> str | None:
        if _is_blank(value):
            return None
        pattern = (params or {}).get("pattern", ".*")
        return None if re.match(pattern, str(value).strip()) else f"does not match {pattern}"

    def _check_range(self, value, params) -> str | None:
        if _is_blank(value):
            return None
        params = params or {}
        try:
            num = float(value)
        except (TypeError, ValueError):
            return "not a number"
        lo, hi = params.get("min"), params.get("max")
        if lo is not None and num < float(lo):
            return f"below minimum {lo}"
        if hi is not None and num > float(hi):
            return f"above maximum {hi}"
        return None

    # -- driver --------------------------------------------------------------
    def validate(self, df: pd.DataFrame, *, index_col: str = "row_index") -> ValidationResult:
        result = ValidationResult()
        for _, row in df.iterrows():
            ref = row[index_col] if index_col in row else row.name
            row_has_error = False
            for rule in self.config.rules:
                field_name = rule["field"]
                check_name = rule["check"]
                if field_name not in df.columns:
                    continue
                check = self._checks.get(check_name)
                if check is None:
                    continue
                detail = check(row[field_name], rule.get("params"))
                if detail is not None:
                    severity = rule.get("severity", "error")
                    result.errors.append(
                        {
                            "row_index": ref,
                            "field": field_name,
                            "rule_violated": f"{check_name}: {detail}",
                            "severity": severity,
                            "detail": detail,
                        }
                    )
                    if severity == "error":
                        row_has_error = True
            result.row_status[ref] = "failed" if row_has_error else "clean"
        return result
