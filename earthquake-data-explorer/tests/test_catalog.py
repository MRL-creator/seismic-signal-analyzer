"""Offline catalog parsing, filtering, and summary regression tests."""

from datetime import date, datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock

import pandas as pd
import requests

from earthquake_explorer.analysis import EventFilters, calculate_summary, count_over_time, filter_events, magnitude_histogram
from earthquake_explorer.api import BoundingBox, SearchRequest, USGSEventClient, USGSAPIError
from earthquake_explorer.api.usgs import parse_feature_collection
from earthquake_explorer.data import EarthquakeEvent, load_csv
from earthquake_explorer.data.io import DatasetError
from earthquake_explorer.visualization import earthquake_map, depth_magnitude_figure


def event(event_id, when, latitude=0, longitude=0, magnitude=4.0, depth=10.0, event_type="earthquake", mag_type="mw"):
    return EarthquakeEvent(event_id, datetime.fromisoformat(when).replace(tzinfo=timezone.utc), latitude, longitude, depth, magnitude, mag_type, "test place", event_type, "https://example.org/event")


class GeoJSONParsingTests(unittest.TestCase):
    def test_parse_preserves_null_scientific_values_and_skips_bad_feature(self):
        payload = {"type": "FeatureCollection", "features": [
            {"id": "us1", "properties": {"time": 1_735_689_600_000, "mag": None, "magType": None, "place": "Pacific", "type": "earthquake", "url": "https://example.org/us1"}, "geometry": {"type": "Point", "coordinates": [-150, 52, None]}},
            {"id": "broken", "properties": {}, "geometry": None},
        ]}
        events, skipped = parse_feature_collection(payload)
        self.assertEqual(skipped, 1)
        self.assertEqual(events[0].event_id, "us1")
        self.assertIsNone(events[0].magnitude)
        self.assertIsNone(events[0].depth_km)
        self.assertEqual(events[0].longitude, -150)

    def test_invalid_collection_raises_useful_error(self):
        with self.assertRaisesRegex(USGSAPIError, "FeatureCollection"):
            parse_feature_collection({"features": []})

    def test_model_rejects_bad_coordinates_and_naive_time(self):
        with self.assertRaisesRegex(ValueError, "Latitude"):
            event("bad", "2025-01-01T00:00:00", latitude=91)
        with self.assertRaisesRegex(ValueError, "timezone"):
            EarthquakeEvent("naive", datetime(2025, 1, 1), 0, 0, None, None)


class USGSClientTests(unittest.TestCase):
    def test_query_parameters_include_full_end_day_and_optional_box(self):
        request = SearchRequest(date(2025, 1, 1), date(2025, 1, 2), 3.5, 6.0, BoundingBox(-20, 70, -130, -60), 250)
        params = request.query_params()
        self.assertEqual(params["format"], "geojson")
        self.assertEqual(params["starttime"], "2025-01-01T00:00:00Z")
        self.assertEqual(params["endtime"], "2025-01-02T23:59:59.999Z")
        self.assertEqual(params["minlongitude"], -130)
        self.assertEqual(params["maxmagnitude"], 6.0)

    def test_search_parses_response_and_handles_empty_204(self):
        feature = {"id": "us2", "properties": {"time": 1_735_689_600_000, "mag": 5.1, "magType": "mb", "type": "earthquake"}, "geometry": {"type": "Point", "coordinates": [140, 35, 20]}}
        response = Mock(status_code=200, url="https://usgs.example/query", text="")
        response.json.return_value = {"type": "FeatureCollection", "features": [feature]}
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        result = USGSEventClient(session).search(SearchRequest(date(2025, 1, 1), date(2025, 1, 1), limit=10))
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].magnitude_type, "mb")
        self.assertFalse(result.result_limit_reached)

        empty_response = Mock(status_code=204, url="https://usgs.example/query")
        session.get.return_value = empty_response
        self.assertEqual(USGSEventClient(session).search(SearchRequest(date(2025, 1, 1), date(2025, 1, 1))).events, ())

    def test_timeout_and_http_failure_are_friendly(self):
        session = Mock()
        session.get.side_effect = requests.Timeout("late")
        request = SearchRequest(date(2025, 1, 1), date(2025, 1, 1))
        with self.assertRaisesRegex(USGSAPIError, "timed out"):
            USGSEventClient(session).search(request)

        response = Mock(status_code=503, url="https://usgs.example/query", text="temporarily unavailable")
        response.raise_for_status.side_effect = requests.HTTPError("503")
        session.get.side_effect = None
        session.get.return_value = response
        with self.assertRaisesRegex(USGSAPIError, "503"):
            USGSEventClient(session).search(request)

    def test_request_limits_and_date_order_are_validated(self):
        with self.assertRaisesRegex(ValueError, "Start date"):
            SearchRequest(date(2025, 2, 1), date(2025, 1, 1))
        with self.assertRaisesRegex(ValueError, "limit"):
            SearchRequest(date(2025, 1, 1), date(2025, 1, 1), limit=20_001)


class LocalDatasetTests(unittest.TestCase):
    def test_bundled_usgs_snapshot_loads_offline(self):
        sample = Path(__file__).parents[1] / "sample_data" / "usgs_2025_q1_m5plus.csv"
        result = load_csv(sample)
        self.assertEqual(len(result.events), 396)
        self.assertEqual(result.events[0].time.tzinfo, timezone.utc)
        self.assertTrue(all(item.magnitude is not None and item.magnitude >= 5 for item in result.events))

    def test_csv_missing_optional_columns_and_bad_rows(self):
        csv = b"id,time,lat,lon,mag\na,2025-01-01T00:00:00Z,10,20,4.2\nb,not-a-date,10,20,5\n"
        loaded = load_csv(csv)
        self.assertEqual(len(loaded.events), 1)
        self.assertEqual(loaded.skipped_rows, 1)
        self.assertIsNone(loaded.events[0].depth_km)
        with self.assertRaisesRegex(DatasetError, "missing a required column"):
            load_csv(b"id,mag\na,5\n")


class FilteringAndStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            event("a", "2025-01-06T00:00:00", latitude=10, longitude=20, magnitude=3.0, depth=10),
            event("b", "2025-01-12T23:00:00", latitude=15, longitude=25, magnitude=5.0, depth=120),
            event("c", "2025-01-13T00:00:00", latitude=-40, longitude=145, magnitude=None, depth=400),
            EarthquakeEvent("d", datetime(2025, 1, 14, tzinfo=timezone.utc), 0, 0, None, None, event_type="explosion"),
        ]

    def test_filters_date_magnitude_depth_type_and_region(self):
        filters = EventFilters(
            start_date=date(2025, 1, 6), end_date=date(2025, 1, 12),
            magnitude_range=(4, 6), depth_range_km=(50, 200),
            bbox=BoundingBox(0, 30, 0, 40), event_types=frozenset({"earthquake"}),
        )
        self.assertEqual([item.event_id for item in filter_events(self.events, filters)], ["b"])

    def test_missing_values_remain_or_can_be_excluded(self):
        self.assertEqual(len(filter_events(self.events, EventFilters(magnitude_range=(2, 6)))), 4)
        filtered = filter_events(self.events, EventFilters(magnitude_range=(2, 6), include_missing_magnitude=False))
        self.assertEqual([item.event_id for item in filtered], ["a", "b"])

    def test_depth_and_magnitude_statistics_do_not_fill_missing_values(self):
        summary = calculate_summary(self.events)
        self.assertEqual(summary.event_count, 4)
        self.assertEqual(summary.magnitude_count, 2)
        self.assertEqual(summary.missing_magnitude_count, 2)
        self.assertAlmostEqual(summary.mean_magnitude, 4.0)
        self.assertEqual(summary.median_depth_km, 120)
        self.assertEqual(summary.shallow_count, 1)
        self.assertEqual(summary.intermediate_count, 1)
        self.assertEqual(summary.deep_count, 1)
        self.assertEqual(summary.missing_depth_count, 1)

    def test_weekly_bins_start_monday_and_magnitude_bins_count_events(self):
        weekly = count_over_time(self.events, "W-MON")
        self.assertEqual(list(weekly["event_count"]), [2, 2])
        self.assertEqual(weekly.iloc[0]["period_start"].day, 6)
        histogram = magnitude_histogram(self.events, .5)
        self.assertEqual(int(histogram.event_count.sum()), 2)
        with self.assertRaisesRegex(ValueError, "Frequency"):
            count_over_time(self.events, "Y")


class VisualizationTests(unittest.TestCase):
    def test_map_uses_bundled_land_and_depth_axis_is_positive_down(self):
        one = event("map", "2025-01-01T00:00:00", latitude=12, longitude=30, magnitude=5.4, depth=80)
        figure = earthquake_map([one])
        self.assertGreater(len(figure.data), 1)
        self.assertFalse(figure.layout.geo.showland)
        self.assertTrue(any(trace.mode == "markers" for trace in figure.data))
        depth_figure = depth_magnitude_figure([one])
        self.assertEqual(depth_figure.layout.yaxis.autorange, "reversed")


if __name__ == "__main__":
    unittest.main()
