"""Code-generated figures for the README and dashboard (matplotlib, license-free).

All README visuals are produced here so none are hand-drawn and all are
regenerable from a seed.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless / CI-safe
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

_PALETTE = {
    "clean": "#2563eb",
    "warn": "#f59e0b",
    "error": "#dc2626",
    "merge": "#16a34a",
    "hold": "#f59e0b",
    "keep": "#94a3b8",
    "ink": "#1e293b",
}


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_quality_kpi(quality: float, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.axis("off")
    color = _PALETTE["merge"] if quality >= 80 else _PALETTE["warn"] if quality >= 60 else _PALETTE["error"]
    ax.text(0.5, 0.60, f"{quality:.1f}%", ha="center", va="center", fontsize=46,
            fontweight="bold", color=color)
    ax.text(0.5, 0.25, "Data Quality Score\n(rows clean on upload)", ha="center",
            va="center", fontsize=12, color=_PALETTE["ink"])
    return _save(fig, out)


def fig_errors_by_type(errors: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    if errors.empty:
        ax.text(0.5, 0.5, "No errors", ha="center")
    else:
        counts = errors.groupby("field").size().sort_values(ascending=True)
        ax.barh(counts.index, counts.values, color=_PALETTE["error"])
        ax.set_xlabel("Exceptions")
    ax.set_title("Validation exceptions by field")
    return _save(fig, out)


def fig_dup_resolution(auto: int, hold: int, keep: int, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(5, 5))
    vals = [auto, hold, keep]
    labels = [f"Auto-merge ({auto})", f"Hold for review ({hold})", f"Kept distinct ({keep})"]
    colors = [_PALETTE["merge"], _PALETTE["hold"], _PALETTE["keep"]]
    vals2, labels2, colors2 = zip(*[(v, l, c) for v, l, c in zip(vals, labels, colors) if v > 0]) \
        if any(vals) else ([1], ["none"], [_PALETTE["keep"]])
    ax.pie(vals2, labels=labels2, colors=colors2, autopct="%1.0f%%", startangle=90,
           wedgeprops=dict(width=0.42))
    ax.set_title("Duplicate resolution")
    return _save(fig, out)


def fig_funnel(uploaded: int, validated: int, clean: int, flagged: int, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    stages = ["Uploaded", "Passed\nvalidation", "Loaded\nclean", "Flagged /\nheld"]
    vals = [uploaded, validated, clean, flagged]
    colors = [_PALETTE["ink"], _PALETTE["clean"], _PALETTE["merge"], _PALETTE["warn"]]
    ax.bar(stages, vals, color=colors)
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=11)
    ax.set_title("Before / after record counts")
    ax.set_ylabel("Records")
    return _save(fig, out)


def fig_quality_over_batches(quality_series: list[float], out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7, 4))
    x = list(range(1, len(quality_series) + 1))
    ax.plot(x, quality_series, marker="o", color=_PALETTE["clean"], linewidth=2)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Batch")
    ax.set_ylabel("Quality score (%)")
    ax.set_title("Data quality over successive batches")
    ax.set_xticks(x)
    return _save(fig, out)


def fig_detection_accuracy(per_type: dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    types = list(per_type.keys())
    injected = [per_type[t]["injected"] for t in types]
    caught = [per_type[t]["caught"] for t in types]
    y = range(len(types))
    h = 0.38
    ax.barh([i + h / 2 for i in y], injected, height=h, label="Injected", color=_PALETTE["keep"])
    ax.barh([i - h / 2 for i in y], caught, height=h, label="Caught", color=_PALETTE["merge"])
    ax.set_yticks(list(y))
    ax.set_yticklabels(types)
    ax.set_xlabel("Rows")
    ax.set_title("Detection accuracy: injected vs caught, per error type")
    ax.legend()
    return _save(fig, out)


def fig_architecture(out: Path) -> Path:
    """Render the pipeline architecture diagram."""
    fig, ax = plt.subplots(figsize=(6, 9))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 22)
    steps = [
        ("CSV / Excel intake\n(multi-source, synthetic)", "#e2e8f0"),
        ("[1] Ingestion\nbulk load · encoding/header · stage RAW untouched", "#dbeafe"),
        ("[2] Validation engine\nrequired · format · range/logic · YAML rules", "#dbeafe"),
        ("[3] Duplicate resolver\nexact keys + fuzzy (name+DOB) · merge/keep/hold", "#dcfce7"),
        ("[4] Correction & audit log\nfield · old→new · action · who · when", "#fef9c3"),
        ("[5] Database (SQLite / SQL Server)\nstaging · clean · logs", "#dbeafe"),
        ("[6] Reporting\nexception reports · data-quality dashboard", "#ede9fe"),
    ]
    y = 20
    for i, (text, color) in enumerate(steps):
        box = plt.Rectangle((1, y - 1.3), 8, 2.1, facecolor=color,
                            edgecolor=_PALETTE["ink"], linewidth=1.2, zorder=2)
        ax.add_patch(box)
        ax.text(5, y - 0.25, text, ha="center", va="center", fontsize=9.5,
                color=_PALETTE["ink"], zorder=3)
        if i < len(steps) - 1:
            ax.annotate("", xy=(5, y - 1.6), xytext=(5, y - 1.3),
                        arrowprops=dict(arrowstyle="-|>", color=_PALETTE["ink"], lw=1.5))
        y -= 3
    ax.set_title("RecordBridge pipeline", fontsize=13, fontweight="bold")
    return _save(fig, out)


def generate_figures(ctx: dict, fig_dir: str | Path = "figures") -> dict[str, Path]:
    """Generate every README figure from a context dict produced by the CLI."""
    fig_dir = Path(fig_dir)
    out = {}
    out["architecture"] = fig_architecture(fig_dir / "architecture.png")
    out["quality_kpi"] = fig_quality_kpi(ctx["quality"], fig_dir / "quality_kpi.png")
    out["errors_by_type"] = fig_errors_by_type(ctx["errors"], fig_dir / "errors_by_type.png")
    out["dup_resolution"] = fig_dup_resolution(
        ctx["auto"], ctx["hold"], ctx["keep"], fig_dir / "dup_resolution.png")
    out["funnel"] = fig_funnel(
        ctx["uploaded"], ctx["validated"], ctx["clean"], ctx["flagged"], fig_dir / "funnel.png")
    out["quality_over_batches"] = fig_quality_over_batches(
        ctx["quality_series"], fig_dir / "quality_over_batches.png")
    out["detection_accuracy"] = fig_detection_accuracy(
        ctx["per_type"], fig_dir / "detection_accuracy.png")
    return out
