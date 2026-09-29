"""Small validated model for a catalog earthquake's preferred origin/magnitude."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math


@dataclass(frozen=True)
class EarthquakeEvent:
    """One preferred event solution as reported by a source catalog.

    Coordinates refer to the reported epicenter; depth is the source's
    hypocentral depth in km when supplied. Optional measurements stay missing.
    """

    event_id: str
    time: datetime
    latitude: float
    longitude: float
    depth_km: float | None
    magnitude: float | None
    magnitude_type: str | None = None
    place: str | None = None
    event_type: str | None = None
    url: str | None = None

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("Event ID cannot be empty.")
        if self.time.tzinfo is None or self.time.utcoffset() is None:
            raise ValueError("Event time must include a timezone.")
        object.__setattr__(self, "time", self.time.astimezone(timezone.utc))
        if not math.isfinite(self.latitude) or not -90 <= self.latitude <= 90:
            raise ValueError("Latitude must be finite and between -90 and 90 degrees.")
        if not math.isfinite(self.longitude) or not -180 <= self.longitude <= 180:
            raise ValueError("Longitude must be finite and between -180 and 180 degrees.")
        if self.depth_km is not None and not math.isfinite(self.depth_km):
            raise ValueError("Depth must be finite or missing.")
        if self.magnitude is not None and not math.isfinite(self.magnitude):
            raise ValueError("Magnitude must be finite or missing.")
