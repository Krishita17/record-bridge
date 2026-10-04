"""Validation-rule correctness."""
import pandas as pd

from recordbridge.config import Config
from recordbridge.validate import Validator


def _cfg():
    return Config.load("config/rules.yaml")


def _validate_rows(rows):
    df = pd.DataFrame(rows)
    df["row_index"] = range(len(df))
    return Validator(_cfg()).validate(df)


def test_clean_row_passes():
    res = _validate_rows([{
        "student_id": "S0000001", "first_name": "Ada", "last_name": "Lovelace",
        "dob": "2000-01-01", "email": "ada@example.edu", "phone": "123-456-7890",
        "program": "Mathematics", "gpa": "3.9",
    }])
    assert res.n_failed_rows == 0
    assert res.row_status[0] == "clean"


def test_missing_required_field_is_error():
    res = _validate_rows([{
        "student_id": "S0000001", "first_name": "", "last_name": "Lovelace",
        "dob": "2000-01-01", "email": "ada@example.edu", "phone": "123-456-7890",
        "program": "Mathematics", "gpa": "3.9",
    }])
    assert res.row_status[0] == "failed"
    assert any(e["field"] == "first_name" for e in res.errors)


def test_malformed_email_flagged():
    res = _validate_rows([{
        "student_id": "S0000001", "first_name": "Ada", "last_name": "Lovelace",
        "dob": "2000-01-01", "email": "ada_at_example.edu", "phone": "123-456-7890",
        "program": "Mathematics", "gpa": "3.9",
    }])
    assert any(e["field"] == "email" for e in res.errors)


def test_gpa_out_of_range_flagged():
    res = _validate_rows([{
        "student_id": "S0000001", "first_name": "Ada", "last_name": "Lovelace",
        "dob": "2000-01-01", "email": "ada@example.edu", "phone": "123-456-7890",
        "program": "Mathematics", "gpa": "5.2",
    }])
    assert any(e["field"] == "gpa" and "above maximum" in e["detail"] for e in res.errors)


def test_future_dob_flagged():
    res = _validate_rows([{
        "student_id": "S0000001", "first_name": "Ada", "last_name": "Lovelace",
        "dob": "2999-01-01", "email": "ada@example.edu", "phone": "123-456-7890",
        "program": "Mathematics", "gpa": "3.9",
    }])
    assert any(e["field"] == "dob" and "future" in e["detail"] for e in res.errors)


def test_bad_student_id_pattern_flagged():
    res = _validate_rows([{
        "student_id": "XYZ", "first_name": "Ada", "last_name": "Lovelace",
        "dob": "2000-01-01", "email": "ada@example.edu", "phone": "123-456-7890",
        "program": "Mathematics", "gpa": "3.9",
    }])
    assert any(e["field"] == "student_id" for e in res.errors)


def test_warning_does_not_fail_row():
    # short phone is a warning, not an error -> row still clean
    res = _validate_rows([{
        "student_id": "S0000001", "first_name": "Ada", "last_name": "Lovelace",
        "dob": "2000-01-01", "email": "ada@example.edu", "phone": "12",
        "program": "Mathematics", "gpa": "3.9",
    }])
    assert res.row_status[0] == "clean"
    assert any(e["severity"] == "warning" for e in res.errors)
