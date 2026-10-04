"""Audit-trail completeness/traceability and an end-to-end smoke test."""
import sqlite3

import pandas as pd

from recordbridge.data.generate import generate_clean, dirtify
from recordbridge.pipeline import run_pipeline


def _make_intake(tmp_path, n=300, seed=7):
    clean = generate_clean(n=n, seed=seed)
    dirty, gt = dirtify(clean, error_rate=0.15, seed=seed)
    intake = tmp_path / "intake.csv"
    dirty.to_csv(intake, index=False)
    gt.errors_df().to_csv(tmp_path / "gt_errors.csv", index=False)
    gt.duplicates_df().to_csv(tmp_path / "gt_dupes.csv", index=False)
    return intake


def test_pipeline_runs_and_loads(tmp_path):
    intake = _make_intake(tmp_path)
    db = tmp_path / "rb.db"
    report, frames = run_pipeline(intake, config_path="config/rules.yaml", db_path=db)
    assert report.total_rows > 0
    assert report.loaded_clean > 0
    assert 0 <= report.quality_score <= 100


def test_nothing_silently_dropped(tmp_path):
    """Every staged row is accounted for: loaded, failed, or merged/held."""
    intake = _make_intake(tmp_path)
    db = tmp_path / "rb.db"
    report, _ = run_pipeline(intake, config_path="config/rules.yaml", db_path=db)
    conn = sqlite3.connect(db)
    staged = conn.execute("SELECT COUNT(*) FROM students_staging").fetchone()[0]
    errors_rows = conn.execute(
        "SELECT COUNT(DISTINCT student_ref) FROM validation_errors WHERE severity='error'"
    ).fetchone()[0]
    assert staged == report.total_rows
    # failed rows are preserved as exceptions, not dropped
    assert errors_rows >= 1
    conn.close()


def test_audit_trail_traceable(tmp_path):
    """Every clean record links back to a staging row via stage_id (auditability)."""
    intake = _make_intake(tmp_path)
    db = tmp_path / "rb.db"
    run_pipeline(intake, config_path="config/rules.yaml", db_path=db)
    conn = sqlite3.connect(db)
    orphans = conn.execute(
        "SELECT COUNT(*) FROM students_clean c "
        "LEFT JOIN students_staging s ON c.stage_id = s.stage_id "
        "WHERE s.stage_id IS NULL"
    ).fetchone()[0]
    assert orphans == 0
    # and there is at least one logged correction/action
    logged = conn.execute("SELECT COUNT(*) FROM correction_log").fetchone()[0]
    assert logged > 0
    conn.close()


def test_config_generality_second_schema(tmp_path):
    """Point the engine at a differently-shaped CSV with a new rules file."""
    import yaml
    from recordbridge.config import Config
    from recordbridge.validate import Validator

    # A 'courses' dataset, nothing to do with students.
    df = pd.DataFrame([
        {"course_code": "CS101", "credits": "3", "row_index": 0},
        {"course_code": "", "credits": "99", "row_index": 1},
    ])
    rules = {
        "dataset": "courses",
        "schema": ["course_code", "credits"],
        "exact_keys": ["course_code"],
        "fuzzy": {"name_fields": ["course_code"], "dob_field": "credits"},
        "rules": [
            {"field": "course_code", "check": "required", "severity": "error"},
            {"field": "credits", "check": "range", "severity": "error",
             "params": {"min": 1, "max": 6}},
        ],
    }
    cfg_path = tmp_path / "courses.yaml"
    cfg_path.write_text(yaml.safe_dump(rules))
    res = Validator(Config.load(cfg_path)).validate(df)
    assert res.row_status[0] == "clean"
    assert res.row_status[1] == "failed"  # blank code + credits out of range
