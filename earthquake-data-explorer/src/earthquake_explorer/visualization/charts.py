"""Compact statistical plots with explicit event-count and coordinate units."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go

from earthquake_explorer.analysis.statistics import count_over_time, magnitude_histogram
from earthquake_explorer.data.io import events_to_frame
from earthquake_explorer.data.models import EarthquakeEvent


COLORS = {"ink": "#244344", "rust": "#bc6848", "teal": "#608d83", "grid": "#e7ebe6"}


def _layout(fig: go.Figure, height: int = 290) -> go.Figure:
    fig.update_layout(
        height=height, margin={"l": 18, "r": 14, "t": 18, "b": 14},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
        font={"family": "Arial, sans-serif", "size": 11, "color": "#647370"},
        xaxis={"showgrid": True, "gridcolor": COLORS["grid"], "zeroline": False},
        yaxis={"showgrid": True, "gridcolor": COLORS["grid"], "zeroline": False},
    )
    return fig


def timeline_figure(events: list[EarthquakeEvent], frequency: str = "W-MON") -> go.Figure:
    counts = count_over_time(events, frequency)
    if counts.empty:
        fig = go.Figure()
    else:
        fig = px.bar(counts, x="period_start", y="event_count", color_discrete_sequence=[COLORS["teal"]])
    labels = {"D": "Day (UTC)", "W-MON": "Week starting Monday (UTC)", "MS": "Month (UTC)"}
    fig.update_layout(xaxis_title=labels[frequency], yaxis_title="Catalog events", showlegend=False)
    return _layout(fig)


def magnitude_histogram_figure(events: list[EarthquakeEvent]) -> go.Figure:
    counts = magnitude_histogram(events)
    fig = go.Figure()
    if not counts.empty:
        fig.add_trace(go.Bar(
            x=(counts["bin_start"] + counts["bin_end"]) / 2,
            y=counts["event_count"], width=(counts["bin_end"] - counts["bin_start"]) * .92,
            marker_color=COLORS["rust"],
            customdata=counts[["bin_start", "bin_end"]],
            hovertemplate="Magnitude %{customdata[0]:.1f} to %{customdata[1]:.1f}<br>%{y} events<extra></extra>",
        ))
    fig.update_layout(xaxis_title="Reported magnitude (0.5-unit bins)", yaxis_title="Catalog events", showlegend=False)
    return _layout(fig)


def depth_magnitude_figure(events: list[EarthquakeEvent]) -> go.Figure:
    frame = events_to_frame(events).dropna(subset=["magnitude", "depth_km"])
    fig = go.Figure()
    if not frame.empty:
        fig.add_trace(go.Scatter(
            x=frame["magnitude"], y=frame["depth_km"], mode="markers",
            marker={"size": 8, "color": COLORS["ink"], "opacity": .62},
            customdata=frame[["place", "magnitude_type", "time"]],
            hovertemplate="M %{x:.1f} %{customdata[1]}<br>Depth %{y:.1f} km<br>%{customdata[0]}<br>%{customdata[2]}<extra></extra>",
        ))
    fig.update_layout(xaxis_title="Reported magnitude", yaxis_title="Depth (km; positive downward)", showlegend=False)
    fig = _layout(fig)
    fig.update_yaxes(autorange="reversed")
    return fig
