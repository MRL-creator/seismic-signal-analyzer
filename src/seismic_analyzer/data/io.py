"""CSV ingestion with explicit time-axis and sampling validation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Waveform:
    """A uniformly sampled waveform; time is elapsed seconds from record start."""

    time: np.ndarray
    data: np.ndarray
    channel: str
    unit: str = "counts"
    source: str = "uploaded CSV"

    @property
    def sampling_rate(self) -> float:
        """Median-rate estimate in Hz; timestamp jitter is checked by the loader."""
        return float(1.0 / np.median(np.diff(self.time)))

    @property
    def duration(self) -> float:
        return float(self.time[-1] - self.time[0])

    @property
    def nyquist(self) -> float:
        return self.sampling_rate / 2.0


def _time_axis(frame: pd.DataFrame) -> tuple[np.ndarray, str]:
    normalized = {str(c).strip().lower(): c for c in frame.columns}
    time_name = next((normalized[k] for k in ("time", "time_s", "timestamp", "seconds", "elapsed_s", "elapsed_seconds") if k in normalized), None)
    index_name = next((normalized[k] for k in ("sample", "sample_index", "index", "n") if k in normalized), None)
    if time_name is not None:
        raw = frame[time_name]
        numeric = pd.to_numeric(raw, errors="coerce")
        if numeric.notna().all():
            axis = numeric.to_numpy(dtype=float)
        else:
            parsed = pd.to_datetime(raw, errors="coerce", utc=True)
            if parsed.isna().any():
                raise ValueError(f"Time column '{time_name}' contains values that are neither numeric seconds nor timestamps.")
            axis = (parsed - parsed.iloc[0]).dt.total_seconds().to_numpy(dtype=float)
        label = str(time_name)
    elif index_name is not None:
        axis = pd.to_numeric(frame[index_name], errors="coerce").to_numpy(dtype=float)
        label = str(index_name)
    else:
        raise ValueError("No time column found. Add 'time'/'timestamp' in seconds or a 'sample_index' column.")
    if not np.isfinite(axis).all():
        raise ValueError(f"Time/index column '{label}' contains missing or non-numeric values.")
    if len(axis) < 16:
        raise ValueError("At least 16 samples are required for analysis.")
    delta = np.diff(axis)
    if np.any(delta <= 0):
        raise ValueError("Time values must be strictly increasing with no duplicates.")
    return axis, label


def load_csv(file: str | Path | bytes | BytesIO, *, channel: str | None = None, unit: str = "counts", source: str | None = None, sampling_rate: float = 1.0) -> Waveform:
    """Load one numeric channel from a CSV with time, timestamp, or sample index."""
    try:
        frame = pd.read_csv(file)
    except Exception as exc:
        raise ValueError(f"Could not read CSV: {exc}") from exc
    if frame.empty or len(frame.columns) < 2:
        raise ValueError("CSV must contain a time/index column and at least one amplitude channel.")
    axis, axis_name = _time_axis(frame)
    time_columns = {axis_name.lower(), "time", "time_s", "timestamp", "seconds", "elapsed_s", "elapsed_seconds", "sample", "sample_index", "index", "n"}
    channels = [c for c in frame.columns if str(c).strip().lower() not in time_columns and pd.to_numeric(frame[c], errors="coerce").notna().all()]
    if not channels:
        raise ValueError("No numeric amplitude channel found. Check that channel columns contain only numbers.")
    if channel is None:
        channel = str(channels[0])
    selected = next((c for c in channels if str(c) == channel), None)
    if selected is None:
        raise ValueError(f"Channel '{channel}' is unavailable. Numeric channels: {', '.join(map(str, channels))}.")
    values = pd.to_numeric(frame[selected], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"Channel '{selected}' contains missing or non-finite samples.")
    if np.ptp(values) == 0:
        raise ValueError(f"Channel '{selected}' is constant; signal analysis requires variation.")

    # Sample indices are dimensionless; the caller supplies the rate needed to
    # express the trace axis in elapsed seconds (default 1 Hz for library use).
    if axis_name.strip().lower() in {"sample", "sample_index", "index", "n"}:
        if not np.isfinite(sampling_rate) or sampling_rate <= 0:
            raise ValueError("Sampling rate must be positive for sample-index data.")
        axis = axis - axis[0]
        axis = axis / sampling_rate
    dt = np.diff(axis)
    if np.std(dt) / np.mean(dt) > 0.01:
        raise ValueError("Samples are not uniformly spaced (interval variation exceeds 1%). Resample before analysis.")
    axis = axis - axis[0]
    return Waveform(axis, values, str(selected), unit, source or (Path(file).name if isinstance(file, (str, Path)) else "uploaded CSV"))


def load_sample() -> Waveform:
    """Load the bundled two-channel synthetic local-earthquake teaching trace."""
    sample_path = Path(__file__).resolve().parents[3] / "sample_data" / "synthetic_local_event.csv"
    return load_csv(sample_path, channel="vertical", unit="counts", source="Synthetic local event")
