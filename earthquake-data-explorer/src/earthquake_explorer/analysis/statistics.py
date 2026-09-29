"""Transparent descriptive summaries; no forecasting or causal inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from earthquake_explorer.data.io import events_to_frame
from earthquake_explorer.data.models import EarthquakeEvent


@dataclass(frozen=True)
class CatalogSummary:
    event_count: int
    magnitude_count: int
    largest_magnitude: float | None
    mean_magnitude: float | None
    median_magnitude: float | None
    depth_count: int
    mean_depth_km: float | None
    median_depth_km: float | None
    shallow_count: int
    intermediate_count: int
    deep_count: int
    missing_magnitude_count: int
    missing_depth_count: int


def calculate_summary(events: Iterable[EarthquakeEvent]) -> CatalogSummary:
    """Summarize reported catalog values; depth groups are conventional ranges."""
    frame = events_to_frame(events)
    magnitudes = frame["magnitude"].dropna().astype(float) if not frame.empty else pd.Series(dtype=float)
    depths = frame["depth_km"].dropna().astype(float) if not frame.empty else pd.Series(dtype=float)
    return CatalogSummary(
        event_count=len(frame), magnitude_count=len(magnitudes),
        largest_magnitude=float(magnitudes.max()) if len(magnitudes) else None,
        mean_magnitude=float(magnitudes.mean()) if len(magnitudes) else None,
        median_magnitude=float(magnitudes.median()) if len(magnitudes) else None,
        depth_count=len(depths), mean_depth_km=float(depths.mean()) if len(depths) else None,
        median_depth_km=float(depths.median()) if len(depths) else None,
        shallow_count=int((depths < 70).sum()),
        intermediate_count=int(((depths >= 70) & (depths <= 300)).sum()),
        deep_count=int((depths > 300).sum()),
        missing_magnitude_count=len(frame) - len(magnitudes),
        missing_depth_count=len(frame) - len(depths),
    )


def count_over_time(events: Iterable[EarthquakeEvent], frequency: str = "W-MON") -> pd.DataFrame:
    """Count origins per calendar bin (D daily, W-MON weekly, MS monthly)."""
    allowed = {"D", "W-MON", "MS"}
    if frequency not in allowed:
        raise ValueError(f"Frequency must be one of {', '.join(sorted(allowed))}.")
    frame = events_to_frame(events)
    if frame.empty:
        return pd.DataFrame({"period_start": pd.Series(dtype="datetime64[ns, UTC]"), "event_count": pd.Series(dtype="int64")})
    counts = frame.set_index("time").resample(frequency, label="left", closed="left").size().rename("event_count").reset_index()
    return counts.rename(columns={"time": "period_start"})


def magnitude_histogram(events: Iterable[EarthquakeEvent], bin_width: float = 0.5) -> pd.DataFrame:
    """Return counts in equal-width bins of reported magnitudes."""
    if not np.isfinite(bin_width) or bin_width <= 0:
        raise ValueError("Magnitude bin width must be finite and positive.")
    frame = events_to_frame(events)
    values = frame["magnitude"].dropna().to_numpy(dtype=float) if not frame.empty else np.array([])
    if not len(values):
        return pd.DataFrame({"bin_start": [], "bin_end": [], "event_count": []})
    lower = np.floor(values.min() / bin_width) * bin_width
    upper = np.ceil(values.max() / bin_width) * bin_width
    if upper <= lower:
        upper = lower + bin_width
    edges = np.arange(lower, upper + bin_width * 1.001, bin_width)
    counts, edges = np.histogram(values, bins=edges)
    return pd.DataFrame({"bin_start": edges[:-1], "bin_end": edges[1:], "event_count": counts})
