"""Interactive data-quality dashboard (Plotly, license-free, single HTML file).

A Power BI path is documented in ``dashboard/README.md`` as the enterprise
option; this module is the default so the project runs with no license.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_BLUE, _GREEN, _AMBER, _RED, _GREY = "#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#94a3b8"


def build_dashboard(ctx: dict, out_path: str | Path = "dashboard/recordbridge_dashboard.html") -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig = make_subplots(
        rows=3, cols=2,
        specs=[
            [{"type": "indicator"}, {"type": "domain"}],
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "xy"}],
        ],
        subplot_titles=(
            "Data Quality Score", "Duplicate resolution",
            "Exceptions by field", "Before / after funnel",
            "Quality over batches", "Detection accuracy (injected vs caught)",
        ),
        vertical_spacing=0.12,
    )

    # KPI
    fig.add_trace(go.Indicator(
        mode="gauge+number", value=ctx["quality"],
        number={"suffix": "%"},
        gauge={"axis": {"range": [0, 100]}, "bar": {"color": _GREEN}},
    ), row=1, col=1)

    # Donut
    fig.add_trace(go.Pie(
        labels=["Auto-merge", "Hold", "Keep"],
        values=[ctx["auto"], ctx["hold"], ctx["keep"]],
        hole=0.45, marker_colors=[_GREEN, _AMBER, _GREY],
    ), row=1, col=2)

    # Errors by field
    errors = ctx["errors"]
    if not errors.empty:
        by_field = errors.groupby("field").size().sort_values()
        fig.add_trace(go.Bar(x=by_field.values, y=by_field.index, orientation="h",
                             marker_color=_RED), row=2, col=1)

    # Funnel
    fig.add_trace(go.Bar(
        x=["Uploaded", "Validated", "Clean", "Flagged"],
        y=[ctx["uploaded"], ctx["validated"], ctx["clean"], ctx["flagged"]],
        marker_color=[_GREY, _BLUE, _GREEN, _AMBER],
    ), row=2, col=2)

    # Quality over batches
    qs = ctx["quality_series"]
    fig.add_trace(go.Scatter(x=list(range(1, len(qs) + 1)), y=qs, mode="lines+markers",
                             line_color=_BLUE), row=3, col=1)

    # Detection accuracy
    pt = ctx["per_type"]
    types = list(pt.keys())
    fig.add_trace(go.Bar(name="Injected", x=types, y=[pt[t]["injected"] for t in types],
                         marker_color=_GREY), row=3, col=2)
    fig.add_trace(go.Bar(name="Caught", x=types, y=[pt[t]["caught"] for t in types],
                         marker_color=_GREEN), row=3, col=2)

    fig.update_layout(
        title_text="RecordBridge — Data Quality Dashboard",
        showlegend=False, height=1100, barmode="group",
        template="plotly_white",
    )
    fig.write_html(str(out_path), include_plotlyjs="cdn")
    return out_path
