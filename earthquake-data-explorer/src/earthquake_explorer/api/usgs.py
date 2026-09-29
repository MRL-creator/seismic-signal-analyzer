"""Client for the USGS FDSN Event Web Service GeoJSON query endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import math
from typing import Any

import requests

from earthquake_explorer.data.models import EarthquakeEvent


API_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
MAX_API_LIMIT = 20_000


class USGSAPIError(RuntimeError):
    """A network, HTTP, or response-format problem from the USGS service."""


@dataclass(frozen=True)
class BoundingBox:
    """Rectangular geographic query bounds in decimal degrees."""

    min_latitude: float
    max_latitude: float
    min_longitude: float
    max_longitude: float

    def __post_init__(self) -> None:
        if not (-90 <= self.min_latitude < self.max_latitude <= 90):
            raise ValueError("Latitude bounds must satisfy -90 <= min < max <= 90.")
        if not (-360 <= self.min_longitude < self.max_longitude <= 360):
            raise ValueError("Longitude bounds must satisfy -360 <= min < max <= 360.")


@dataclass(frozen=True)
class SearchRequest:
    """Date and magnitude bounds for one catalog search."""

    start_date: date
    end_date: date
    min_magnitude: float = 0.0
    max_magnitude: float | None = None
    bbox: BoundingBox | None = None
    limit: int = 5_000

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("Start date must be on or before end date.")
        if not math.isfinite(self.min_magnitude):
            raise ValueError("Minimum magnitude must be finite.")
        if self.max_magnitude is not None and (not math.isfinite(self.max_magnitude) or self.max_magnitude < self.min_magnitude):
            raise ValueError("Maximum magnitude must be finite and no smaller than the minimum.")
        if not 1 <= self.limit <= MAX_API_LIMIT:
            raise ValueError(f"Result limit must be between 1 and {MAX_API_LIMIT}.")

    def query_params(self) -> dict[str, str | int | float]:
        """Return the documented FDSN query parameters; date range includes end day."""
        end_exclusive = datetime.combine(self.end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        end_inclusive = end_exclusive - timedelta(milliseconds=1)
        params: dict[str, str | int | float] = {
            "format": "geojson",
            "starttime": datetime.combine(self.start_date, time.min, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "endtime": end_inclusive.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "minmagnitude": self.min_magnitude,
            "limit": self.limit,
            "orderby": "time",
            "nodata": 204,
        }
        if self.max_magnitude is not None:
            params["maxmagnitude"] = self.max_magnitude
        if self.bbox:
            params.update({
                "minlatitude": self.bbox.min_latitude,
                "maxlatitude": self.bbox.max_latitude,
                "minlongitude": self.bbox.min_longitude,
                "maxlongitude": self.bbox.max_longitude,
            })
        return params


@dataclass(frozen=True)
class FetchResult:
    events: tuple[EarthquakeEvent, ...]
    skipped_features: int
    request_url: str
    result_limit_reached: bool


def _optional_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def parse_feature_collection(payload: Any) -> tuple[list[EarthquakeEvent], int]:
    """Parse USGS GeoJSON features; skip malformed records without inventing data."""
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise USGSAPIError("USGS response was not a GeoJSON FeatureCollection.")
    events: list[EarthquakeEvent] = []
    skipped = 0
    for feature in payload["features"]:
        try:
            if not isinstance(feature, dict):
                raise ValueError
            properties = feature.get("properties") or {}
            geometry = feature.get("geometry") or {}
            if not isinstance(properties, dict) or not isinstance(geometry, dict):
                raise ValueError
            coordinates = geometry.get("coordinates")
            if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
                raise ValueError
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
            depth = _optional_float(coordinates[2]) if len(coordinates) > 2 else None
            raw_time = properties.get("time")
            if raw_time is None or isinstance(raw_time, bool):
                raise ValueError
            event_time = datetime.fromtimestamp(float(raw_time) / 1000.0, tz=timezone.utc)
            event_id = feature.get("id") or properties.get("code")
            if not event_id:
                raise ValueError
            event = EarthquakeEvent(
                event_id=str(event_id), time=event_time, latitude=latitude, longitude=longitude,
                depth_km=depth, magnitude=_optional_float(properties.get("mag")),
                magnitude_type=_optional_text(properties.get("magType")),
                place=_optional_text(properties.get("place")),
                event_type=_optional_text(properties.get("type")),
                url=_optional_text(properties.get("url")),
            )
            events.append(event)
        except (ValueError, TypeError, OverflowError, OSError, KeyError):
            skipped += 1
    return events, skipped


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class USGSEventClient:
    """Small timeout-bounded client. Cache results at the UI boundary."""

    def __init__(self, session: requests.Session | None = None, timeout: tuple[float, float] = (4.0, 25.0)) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout

    def search(self, request: SearchRequest) -> FetchResult:
        """Fetch an event collection and report any malformed features skipped."""
        try:
            response = self.session.get(API_URL, params=request.query_params(), timeout=self.timeout, headers={"User-Agent": "EarthquakeDataExplorer/1.0 (educational research dashboard)"})
        except requests.Timeout as exc:
            raise USGSAPIError("The USGS request timed out. Try a shorter date range or use the local sample.") from exc
        except requests.RequestException as exc:
            raise USGSAPIError(f"Could not reach the USGS catalog: {exc}") from exc
        if response.status_code == 204:
            return FetchResult((), 0, response.url, False)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = response.text[:240].strip()
            raise USGSAPIError(f"USGS returned HTTP {response.status_code}. {detail}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise USGSAPIError("USGS returned a response that was not valid JSON.") from exc
        events, skipped = parse_feature_collection(payload)
        return FetchResult(tuple(events), skipped, response.url, len(events) >= request.limit)
