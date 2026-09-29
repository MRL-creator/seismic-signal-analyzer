"""Deterministic client-side filtering shared by API and local datasets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

from earthquake_explorer.api.usgs import BoundingBox
from earthquake_explorer.data.models import EarthquakeEvent


@dataclass(frozen=True)
class EventFilters:
    start_date: date | None = None
    end_date: date | None = None
    magnitude_range: tuple[float, float] | None = None
    depth_range_km: tuple[float, float] | None = None
    bbox: BoundingBox | None = None
    event_types: frozenset[str] | None = None
    include_missing_magnitude: bool = True
    include_missing_depth: bool = True


def filter_events(events: Iterable[EarthquakeEvent], filters: EventFilters) -> list[EarthquakeEvent]:
    """Filter events inclusively; unknown magnitudes/depths remain explicit."""
    start = datetime.combine(filters.start_date, time.min, tzinfo=timezone.utc) if filters.start_date else None
    end = datetime.combine(filters.end_date + timedelta(days=1), time.min, tzinfo=timezone.utc) if filters.end_date else None
    selected: list[EarthquakeEvent] = []
    for event in events:
        if start and event.time < start:
            continue
        if end and event.time >= end:
            continue
        if filters.magnitude_range:
            low, high = filters.magnitude_range
            if event.magnitude is None:
                if not filters.include_missing_magnitude:
                    continue
            elif not low <= event.magnitude <= high:
                continue
        if filters.depth_range_km:
            low, high = filters.depth_range_km
            if event.depth_km is None:
                if not filters.include_missing_depth:
                    continue
            elif not low <= event.depth_km <= high:
                continue
        if filters.bbox:
            box = filters.bbox
            if not box.min_latitude <= event.latitude <= box.max_latitude:
                continue
            lon = event.longitude
            if box.min_longitude < -180 or box.max_longitude > 180:
                lon = lon % 360
            if not box.min_longitude <= lon <= box.max_longitude:
                continue
        if filters.event_types and event.event_type not in filters.event_types:
            continue
        selected.append(event)
    return selected
