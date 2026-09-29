"""Interactive world map using Plotly's geographic projection (no tile token)."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from earthquake_explorer.data.io import events_to_frame
from earthquake_explorer.data.models import EarthquakeEvent


@lru_cache(maxsize=1)
def _land_polygons() -> tuple[list[tuple[list[float], list[float]]], ...]:
    """Load bundled Natural Earth 1:110m land outlines for offline map drawing."""
    path = Path(__file__).resolve().parents[3] / "assets" / "ne_110m_land.geojson"
    with path.open(encoding="utf-8") as stream:
        collection = json.load(stream)
    polygons = []
    for feature in collection.get("features", []):
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates", [])
        groups = [coordinates] if geometry.get("type") == "Polygon" else coordinates if geometry.get("type") == "MultiPolygon" else []
        for rings in groups:
            if not rings or len(rings[0]) < 4:
                continue
            outer = rings[0]
            polygons.append(([point[0] for point in outer], [point[1] for point in outer]))
    return tuple(polygons)


def earthquake_map(events: list[EarthquakeEvent]) -> go.Figure:
    """Map epicenters with bundled land outlines; no tile or basemap request is made."""
    frame = events_to_frame(events)
    fig = go.Figure()
    # Plotly's built-in geo land/country layers fetch topology data at render
    # time. Local polygon traces keep this map available without that request.
    for longitude, latitude in _land_polygons():
        fig.add_trace(go.Scattergeo(
            lon=longitude, lat=latitude, mode="lines", fill="toself",
            fillcolor="#e8e9e2", line={"color": "#aeb8b1", "width": .45},
            hoverinfo="skip", showlegend=False,
        ))
    known_depth = frame[frame["depth_km"].notna()] if not frame.empty else frame
    unknown_depth = frame[frame["depth_km"].isna()] if not frame.empty else frame

    def add_points(data, color, colorscale=None, cmin=None, cmax=None, colorbar=None):
        magnitude = data["magnitude"].fillna(0).to_numpy(dtype=float)
        # Marker diameter is a bounded visual cue only; it is not energy-scaled.
        size = np.clip(5 + np.maximum(magnitude, 0) * 2.0, 5, 23)
        custom = data[["event_id", "place", "time", "depth_km", "magnitude", "magnitude_type", "event_type", "url"]].astype(object).where(data.notna(), None).to_numpy()
        fig.add_trace(go.Scattergeo(
            lon=data["longitude"], lat=data["latitude"], mode="markers", name="Earthquakes",
            customdata=custom,
            marker={
                "size": size, "color": color, "colorscale": colorscale,
                "cmin": cmin, "cmax": cmax, "colorbar": colorbar,
                "showscale": colorscale is not None, "opacity": 0.82,
                "line": {"width": 0.45, "color": "#f4f4ef"},
            },
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>Magnitude: %{customdata[4]:.1f} %{customdata[5]}"
                "<br>Depth: %{customdata[3]} km<br>Time: %{customdata[2]}"
                "<br>Type: %{customdata[6]}<br>ID: %{customdata[0]}<extra></extra>"
            ),
        ))

    if not known_depth.empty:
        add_points(
            known_depth, known_depth["depth_km"].clip(lower=0, upper=700),
            colorscale=[[0, "#d17a50"], [.35, "#d7ad68"], [.7, "#6e9b91"], [1, "#315b70"]],
            cmin=0, cmax=700, colorbar={"title": "Depth (km)", "thickness": 12, "len": .72},
        )
    if not unknown_depth.empty:
        add_points(unknown_depth, "#9a9f98")
    fig.update_layout(
        height=540, margin={"l": 0, "r": 0, "t": 6, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False, hoverlabel={"bgcolor": "#f9faf7", "font": {"color": "#203536"}},
        geo={
            "projection_type": "natural earth", "showland": False,
            "showocean": False, "showcoastlines": False,
            "showcountries": False, "showframe": False, "bgcolor": "#e4eceb",
            "lataxis": {"showgrid": True, "gridcolor": "#d7ded9", "dtick": 30},
            "lonaxis": {"showgrid": True, "gridcolor": "#d7ded9", "dtick": 45},
        },
    )
    return fig
