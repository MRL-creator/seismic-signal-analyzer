"""CSV input and consistent conversion between event models and tables."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterable

import math
import pandas as pd

from .models import EarthquakeEvent


class DatasetError(ValueError):
    """A local dataset could not be interpreted as earthquake events."""


@dataclass(frozen=True)
class CSVLoadResult:
    events: tuple[EarthquakeEvent, ...]
    skipped_rows: int
    source: str | None = None


def _number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def load_csv(file: str | Path | bytes | BinaryIO, *, source: str | None = None) -> CSVLoadResult:
    """Load canonical earthquake CSV columns; malformed rows are counted/skipped."""
    try:
        frame = pd.read_csv(BytesIO(file) if isinstance(file, bytes) else file)
    except Exception as exc:
        raise DatasetError(f"Could not read the CSV dataset: {exc}") from exc
    label = source or (Path(file).name if isinstance(file, (str, Path)) else None)
    if frame.empty:
        return CSVLoadResult((), 0, label)
    normalized = {str(column).strip().lower(): column for column in frame.columns}
    aliases = {
        "event_id": ("event_id", "id", "eventid"),
        "time": ("time", "timestamp", "datetime", "origin_time"),
        "latitude": ("latitude", "lat"),
        "longitude": ("longitude", "lon", "lng"),
    }
    columns: dict[str, object] = {}
    for key, names in aliases.items():
        column = next((normalized[name] for name in names if name in normalized), None)
        if column is None:
            raise DatasetError(f"CSV is missing a required column: {key}. Expected event_id, time, latitude, and longitude.")
        columns[key] = column
    optional_aliases = {
        "depth_km": ("depth_km", "depth", "depthkm"),
        "magnitude": ("magnitude", "mag"),
        "magnitude_type": ("magnitude_type", "magtype", "mag_type"),
        "place": ("place", "location", "description"),
        "event_type": ("event_type", "type"),
        "url": ("url", "source_url", "event_url"),
    }
    for key, names in optional_aliases.items():
        columns[key] = next((normalized[name] for name in names if name in normalized), None)

    parsed_time = pd.to_datetime(frame[columns["time"]], errors="coerce", utc=True)
    events: list[EarthquakeEvent] = []
    skipped = 0
    for position, (_, row) in enumerate(frame.iterrows()):
        try:
            event_id = row[columns["event_id"]]
            time_value = parsed_time.iloc[position]
            latitude = _number(row[columns["latitude"]])
            longitude = _number(row[columns["longitude"]])
            if pd.isna(event_id) or pd.isna(time_value) or latitude is None or longitude is None:
                raise ValueError

            def optional_text(key: str) -> str | None:
                column = columns[key]
                if column is None or pd.isna(row[column]):
                    return None
                value = str(row[column]).strip()
                return value or None

            events.append(EarthquakeEvent(
                event_id=str(event_id).strip(), time=time_value.to_pydatetime(),
                latitude=latitude, longitude=longitude,
                depth_km=_number(row[columns["depth_km"]]) if columns["depth_km"] is not None else None,
                magnitude=_number(row[columns["magnitude"]]) if columns["magnitude"] is not None else None,
                magnitude_type=optional_text("magnitude_type"), place=optional_text("place"),
                event_type=optional_text("event_type"), url=optional_text("url"),
            ))
        except (ValueError, TypeError, OverflowError):
            skipped += 1
    if not events and skipped:
        raise DatasetError("No valid events were found. Check required values and coordinate ranges.")
    return CSVLoadResult(tuple(events), skipped, label)


def events_to_frame(events: Iterable[EarthquakeEvent]) -> pd.DataFrame:
    """Convert events to the app's stable, typed column layout."""
    columns = ["event_id", "time", "latitude", "longitude", "depth_km", "magnitude", "magnitude_type", "place", "event_type", "url"]
    rows = [{column: getattr(event, column) for column in columns} for event in events]
    frame = pd.DataFrame(rows, columns=columns)
    if not frame.empty:
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
        for column in ("latitude", "longitude", "depth_km", "magnitude"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame
