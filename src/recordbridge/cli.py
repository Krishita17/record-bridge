"""RecordBridge command-line interface.

Subcommands mirror the pipeline stages so each is a copy-paste command:

    recordbridge data        generate synthetic clean + dirty data (+ ground truth)
    recordbridge run         ingest -> validate -> dedupe -> correct/audit -> load
    recordbridge evaluate    accuracy vs ground truth (precision/recall)
    recordbridge report      exception report + audit-trail excerpt
    recordbridge figures     regenerate all README figures
    recordbridge dashboard   build the interactive Plotly dashboard
    recordbridge all         run the whole flow end to end (used by `make all`)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

from .data.generate import write_dataset
from .evaluate import evaluate_dedupe, evaluate_validation
from .pipeline import run_pipeline
from .report.dashboard import build_dashboard
from .report.figures import generate_figures
from .report.reports import write_audit_excerpt, write_exception_report

DEFAULT_INTAKE = "data/students_raw_intake.csv"
DEFAULT_DB = "data/recordbridge.db"
DEFAULT_CONFIG = "config/rules.yaml"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _load_frames(db_path: str) -> dict[str, pd.DataFrame]:
    conn = sqlite3.connect(db_path)
    frames = {
        t: pd.read_sql_query(f"SELECT * FROM {t}", conn)
        for t in ("validation_errors", "duplicate_pairs", "students_clean",
                  "correction_log", "upload_batches")
    }
    conn.close()
    return frames


def _build_ctx(report, frames, data_dir="data") -> dict:
    """Assemble the context dict used by figures / dashboard / evaluation."""
    data_dir = Path(data_dir)
    errors = frames["validation_errors"].copy()
    if not errors.empty:
        ref_col = "student_ref" if "student_ref" in errors.columns else "row_index"
        errors["row_index"] = errors[ref_col].astype(int)

    gt_errors = pd.read_csv(data_dir / "ground_truth_errors.csv")
    gt_dupes = pd.read_csv(data_dir / "ground_truth_duplicates.csv")

    val_eval = evaluate_validation(errors if not errors.empty else
                                   pd.DataFrame(columns=["row_index", "severity"]), gt_errors)
    dup_eval = evaluate_dedupe(
        frames["duplicate_pairs"].rename(columns={})
        if not frames["duplicate_pairs"].empty
        else pd.DataFrame(columns=["record_a", "record_b"]),
        gt_dupes,
    )

    pairs = frames["duplicate_pairs"]
    auto = int((pairs["resolution"] == "auto-merge").sum()) if not pairs.empty else 0
    hold = int((pairs["resolution"] == "hold").sum()) if not pairs.empty else 0
    keep = max(0, report.total_rows - auto - hold)

    clean = frames["students_clean"]
    loaded_clean = int((clean["status"] == "clean").sum()) if not clean.empty else 0
    held = int((clean["status"] == "held").sum()) if not clean.empty else 0

    ctx = {
        "quality": report.quality_score,
        "errors": errors,
        "auto": auto, "hold": hold, "keep": keep,
        "uploaded": report.total_rows,
        "validated": report.passed,
        "clean": loaded_clean,
        "flagged": report.failed + held,
        "per_type": val_eval["per_type"],
        "quality_series": [report.quality_score],
        "val_eval": val_eval,
        "dup_eval": dup_eval,
    }
    return ctx


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #
def cmd_data(args) -> None:
    paths = write_dataset(out_dir=args.out, n=args.n, error_rate=args.error_rate, seed=args.seed)
    print(f"Generated {args.n} records (~{args.error_rate:.0%} injected errors), seed={args.seed}")
    for k, v in paths.items():
        print(f"  {k:10s} -> {v}")


def cmd_run(args) -> None:
    report, _frames = run_pipeline(
        args.input, config_path=args.config, db_path=args.db, reset=not args.append,
        drop_from_payload=["row_index"] if args.keep_index else None,
    )
    print(_format_report(report))


def cmd_evaluate(args) -> None:
    frames = _load_frames(args.db)
    # Rebuild a lightweight report-like object from batch summary.
    batch = frames["upload_batches"].iloc[-1]
    report = type("R", (), {})()
    report.total_rows = int(batch["total_rows"])
    report.passed = int(batch["passed"])
    report.failed = int(batch["failed"])
    report.quality_score = round(100 * report.passed / report.total_rows, 2) if report.total_rows else 0
    ctx = _build_ctx(report, frames, data_dir=args.data)

    Path(args.out).mkdir(parents=True, exist_ok=True)
    metrics = {"validation": ctx["val_eval"], "deduplication": ctx["dup_eval"],
               "quality_score": ctx["quality"]}
    (Path(args.out) / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print(f"\nWrote {Path(args.out) / 'metrics.json'}")


def cmd_report(args) -> None:
    frames = _load_frames(args.db)
    errors = frames["validation_errors"].copy()
    if not errors.empty:
        errors = errors.rename(columns={"student_ref": "row_index"})
    p1 = write_exception_report(errors, "reports/exception_report.md")
    p2 = write_audit_excerpt(frames["correction_log"], "reports/audit_excerpt.md")
    print(f"Wrote {p1}\nWrote {p2}")


def cmd_figures(args) -> None:
    frames = _load_frames(args.db)
    batch = frames["upload_batches"].iloc[-1]
    report = type("R", (), {})()
    report.total_rows = int(batch["total_rows"])
    report.passed = int(batch["passed"])
    report.failed = int(batch["failed"])
    report.quality_score = round(100 * report.passed / report.total_rows, 2) if report.total_rows else 0
    ctx = _build_ctx(report, frames, data_dir=args.data)
    ctx["quality_series"] = _batch_quality_series(frames)
    out = generate_figures(ctx, fig_dir=args.out)
    for k, v in out.items():
        print(f"  {k:22s} -> {v}")


def cmd_dashboard(args) -> None:
    frames = _load_frames(args.db)
    batch = frames["upload_batches"].iloc[-1]
    report = type("R", (), {})()
    report.total_rows = int(batch["total_rows"])
    report.passed = int(batch["passed"])
    report.failed = int(batch["failed"])
    report.quality_score = round(100 * report.passed / report.total_rows, 2) if report.total_rows else 0
    ctx = _build_ctx(report, frames, data_dir=args.data)
    ctx["quality_series"] = _batch_quality_series(frames)
    out = build_dashboard(ctx, args.out)
    print(f"Wrote {out}")


def _batch_quality_series(frames) -> list[float]:
    b = frames["upload_batches"]
    if b.empty:
        return [0.0]
    s = (100 * b["passed"] / b["total_rows"].clip(lower=1)).round(2).tolist()
    return s if len(s) > 1 else s


def cmd_all(args) -> None:
    """Full reproducible flow: data -> (multi-batch) run -> evaluate -> report -> figures -> dashboard."""
    # 1. data
    write_dataset(out_dir=args.data, n=args.n, error_rate=args.error_rate, seed=args.seed)

    # 2. Run several INDEPENDENT batches to populate the quality-over-time trend
    #    (Tier 3). Each batch is its own synthetic universe (IDs collide across
    #    batches by construction), so each resets the DB; we keep only the
    #    per-batch quality score for the trend. The final batch's DB and ground
    #    truth are what we evaluate and visualise.
    quality_series = []
    final_report = final_frames = None
    final_seed = args.seed
    for b in range(args.batches):
        seed = args.seed + b
        paths = write_dataset(out_dir=args.data, n=args.n, error_rate=args.error_rate, seed=seed)
        report, frames = run_pipeline(
            paths["dirty"], config_path=args.config, db_path=args.db, reset=True,
        )
        quality_series.append(report.quality_score)
        final_report, final_frames, final_seed = report, frames, seed

    # Ground truth on disk already matches the final batch (last write_dataset).
    first_report, first_frames = final_report, final_frames
    ctx = _build_ctx(first_report, first_frames, data_dir=args.data)
    ctx["quality_series"] = quality_series

    # 3. evaluate
    Path(args.results).mkdir(parents=True, exist_ok=True)
    metrics = {"validation": ctx["val_eval"], "deduplication": ctx["dup_eval"],
               "quality_score": ctx["quality"], "quality_over_batches": quality_series}
    (Path(args.results) / "metrics.json").write_text(json.dumps(metrics, indent=2))

    # 4. reports
    errors = first_frames["validation_errors"].copy()
    if not errors.empty:
        errors = errors.rename(columns={"student_ref": "row_index"})
    write_exception_report(errors, "reports/exception_report.md")
    write_audit_excerpt(first_frames["correction_log"], "reports/audit_excerpt.md")

    # 5. figures + dashboard
    generate_figures(ctx, fig_dir=args.figures)
    build_dashboard(ctx, "dashboard/recordbridge_dashboard.html")

    print(_format_report(first_report))
    print("\n=== Accuracy vs ground truth ===")
    print(json.dumps(metrics["validation"]["overall"], indent=2))
    print("Dedupe:", json.dumps(metrics["deduplication"]["overall"]))
    print(f"\nArtifacts: results/metrics.json, reports/, figures/, dashboard/")


def _format_report(r) -> str:
    return (
        "=== RecordBridge batch report ===\n"
        f"  upload_id        : {getattr(r, 'upload_id', 'n/a')}\n"
        f"  total rows       : {r.total_rows}\n"
        f"  passed / failed  : {r.passed} / {r.failed}\n"
        f"  quality score    : {r.quality_score}%\n"
        f"  duplicates found : {getattr(r, 'duplicates_found', 'n/a')} "
        f"(auto-merge {getattr(r, 'auto_merged', '?')}, hold {getattr(r, 'held', '?')})\n"
        f"  corrections      : {getattr(r, 'corrections', 'n/a')}\n"
        f"  loaded clean     : {getattr(r, 'loaded_clean', 'n/a')}"
    )


# --------------------------------------------------------------------------- #
# arg parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="recordbridge", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("data", help="generate synthetic data + ground truth")
    sp.add_argument("--n", type=int, default=5000)
    sp.add_argument("--error-rate", type=float, default=0.15)
    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--out", default="data")
    sp.set_defaults(func=cmd_data)

    sp = sub.add_parser("run", help="run the full pipeline on an intake file")
    sp.add_argument("--input", default=DEFAULT_INTAKE)
    sp.add_argument("--config", default=DEFAULT_CONFIG)
    sp.add_argument("--db", default=DEFAULT_DB)
    sp.add_argument("--append", action="store_true", help="append to DB instead of resetting")
    sp.add_argument("--keep-index", action="store_true")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("evaluate", help="accuracy vs ground truth")
    sp.add_argument("--db", default=DEFAULT_DB)
    sp.add_argument("--data", default="data")
    sp.add_argument("--out", default="results")
    sp.set_defaults(func=cmd_evaluate)

    sp = sub.add_parser("report", help="exception report + audit excerpt")
    sp.add_argument("--db", default=DEFAULT_DB)
    sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("figures", help="regenerate README figures")
    sp.add_argument("--db", default=DEFAULT_DB)
    sp.add_argument("--data", default="data")
    sp.add_argument("--out", default="figures")
    sp.set_defaults(func=cmd_figures)

    sp = sub.add_parser("dashboard", help="build the Plotly dashboard")
    sp.add_argument("--db", default=DEFAULT_DB)
    sp.add_argument("--data", default="data")
    sp.add_argument("--out", default="dashboard/recordbridge_dashboard.html")
    sp.set_defaults(func=cmd_dashboard)

    sp = sub.add_parser("all", help="full end-to-end reproducible flow")
    sp.add_argument("--n", type=int, default=5000)
    sp.add_argument("--error-rate", type=float, default=0.15)
    sp.add_argument("--seed", type=int, default=42)
    sp.add_argument("--batches", type=int, default=5)
    sp.add_argument("--config", default=DEFAULT_CONFIG)
    sp.add_argument("--db", default=DEFAULT_DB)
    sp.add_argument("--data", default="data")
    sp.add_argument("--results", default="results")
    sp.add_argument("--figures", default="figures")
    sp.set_defaults(func=cmd_all)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
