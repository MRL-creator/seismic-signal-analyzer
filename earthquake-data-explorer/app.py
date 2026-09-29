"""Streamlit dashboard entry point for Earthquake Data Explorer."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import streamlit as st

from earthquake_explorer.analysis import (
    EventFilters, calculate_summary, filter_events,
)
from earthquake_explorer.api import BoundingBox, SearchRequest, USGSEventClient, USGSAPIError
from earthquake_explorer.data import EarthquakeEvent, events_to_frame, load_csv
from earthquake_explorer.visualization import (
    depth_magnitude_figure, earthquake_map, magnitude_histogram_figure, timeline_figure,
)


st.set_page_config(page_title="Earthquake Data Explorer", page_icon="E", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
html, body, [class*="css"] { font-family: Arial, sans-serif; }
.stApp { background: #f3f5f1; color: #1d3030; }
[data-testid="stSidebar"] { background: #183132; }
[data-testid="stSidebar"] * { color: #edf2ed !important; }
.hero { padding: 5px 0 18px; border-bottom: 1px solid #d8dfd9; margin-bottom: 20px; }
.eyebrow { color:#b96e4e; font: 11px Consolas,monospace; letter-spacing:.17em; text-transform:uppercase; }
.hero h1 { font-size:34px; line-height:1.16; letter-spacing:-.04em; margin:8px 0; color:#1c3131; }
.hero p { color:#687977; margin:0; font-size:14px; }
[data-testid="stMetric"] { background:#fff; border:1px solid #e0e6df; border-radius:8px; padding:13px 15px; }
[data-testid="stMetricValue"] { color:#244344; font-family:Consolas,monospace; }
.source-note { border-left:3px solid #bd7654; padding:8px 12px; background:#fff9f3; color:#675d53; font-size:12px; }
.side-label { color:#d49b79; font:11px Consolas,monospace; letter-spacing:.15em; text-transform:uppercase; padding:4px 0; }
</style>
<div class="hero"><div class="eyebrow">Catalog observatory / 01</div><h1>Earthquake Data Explorer</h1><p>Map catalog events, inspect reported source parameters, and summarize a selected catalog window.</p></div>
""", unsafe_allow_html=True)


@st.cache_data(ttl=900, max_entries=32, show_spinner=False)
def cached_usgs_search(request: SearchRequest):
    """Cache identical catalog requests for 15 minutes within this app process."""
    return USGSEventClient().search(request)


def bundled_sample():
    path = ROOT / "sample_data" / "usgs_2025_q1_m5plus.csv"
    return load_csv(path, source="USGS ComCat snapshot · Jan–Mar 2025 · M5+")


def request_form() -> tuple[SearchRequest | None, bool]:
    today = datetime.now(timezone.utc).date()
    with st.sidebar.form("catalog_query"):
        st.markdown('<div class="side-label">Live catalog query</div>', unsafe_allow_html=True)
        start = st.date_input("Start date (UTC)", today - timedelta(days=30), key="api_start")
        end = st.date_input("End date (UTC)", today, key="api_end")
        min_mag = st.number_input("Minimum magnitude", min_value=-2.0, max_value=10.0, value=4.0, step=.1, key="api_minmag")
        use_max = st.checkbox("Set a maximum magnitude", value=False, key="api_use_maxmag")
        max_mag = st.number_input("Maximum magnitude", min_value=-2.0, max_value=10.0, value=7.0, step=.1, disabled=not use_max, key="api_maxmag")
        region = st.checkbox("Limit to a latitude/longitude box", value=False, key="api_bbox_enabled")
        box = None
        box_error = None
        if region:
            c1, c2 = st.columns(2)
            with c1:
                min_lat = st.number_input("South latitude", -90.0, 89.0, -20.0, step=1.0)
                min_lon = st.number_input("West longitude", -180.0, 179.0, -130.0, step=1.0)
            with c2:
                max_lat = st.number_input("North latitude", -89.0, 90.0, 70.0, step=1.0)
                max_lon = st.number_input("East longitude", -179.0, 180.0, -60.0, step=1.0)
            try:
                box = BoundingBox(min_lat, max_lat, min_lon, max_lon)
            except ValueError as exc:
                box_error = str(exc)
                st.warning(box_error)
        limit = st.select_slider("Maximum events", options=[500, 1_000, 2_000, 5_000, 10_000, 20_000], value=5_000)
        submitted = st.form_submit_button("Fetch from USGS", type="primary", use_container_width=True)
    if not submitted:
        return None, False
    try:
        if start > end:
            raise ValueError("Start date must be on or before end date.")
        if use_max and max_mag < min_mag:
            raise ValueError("Maximum magnitude must be at least the minimum magnitude.")
        if box_error:
            raise ValueError(box_error)
        return SearchRequest(start, end, min_mag, max_mag if use_max else None, box, limit), True
    except ValueError as exc:
        st.sidebar.error(str(exc))
        return None, True


with st.sidebar:
    st.markdown('<div class="side-label">Data source</div>', unsafe_allow_html=True)
    source_choice = st.radio("Choose catalog source", ["Bundled USGS sample (offline)", "Upload a CSV", "Live USGS catalog"], label_visibility="collapsed")

events: list[EarthquakeEvent] = []
source_label = ""
source_message = ""

if source_choice == "Bundled USGS sample (offline)":
    sample = bundled_sample()
    events = list(sample.events)
    source_label = sample.source or "USGS ComCat snapshot · Jan–Mar 2025 · M5+"
    if sample.skipped_rows:
        source_message = f"Skipped {sample.skipped_rows} malformed sample rows."
elif source_choice == "Upload a CSV":
    upload = st.sidebar.file_uploader("Choose an event CSV", type=["csv"])
    if upload is not None:
        try:
            local = load_csv(upload.getvalue(), source=upload.name)
            events = list(local.events)
            source_label = upload.name
            if local.skipped_rows:
                source_message = f"Skipped {local.skipped_rows} malformed rows; valid events remain available."
        except ValueError as exc:
            st.error(str(exc))
else:
    request, submitted = request_form()
    if submitted and request:
        try:
            with st.spinner("Querying the USGS catalog..."):
                result = cached_usgs_search(request)
            st.session_state["live_events"] = result.events
            st.session_state["live_source"] = f"USGS FDSN Event Service · {request.start_date} to {request.end_date} UTC"
            st.session_state["live_skipped"] = result.skipped_features
            st.session_state["live_limit_reached"] = result.result_limit_reached
            st.session_state.pop("live_error", None)
        except (USGSAPIError, ValueError) as exc:
            st.session_state["live_error"] = str(exc)
    if "live_events" in st.session_state and "live_error" not in st.session_state:
        events = list(st.session_state["live_events"])
        source_label = st.session_state.get("live_source", "USGS FDSN Event Service")
        if st.session_state.get("live_skipped"):
            source_message = f"Skipped {st.session_state['live_skipped']} malformed API features."
        if st.session_state.get("live_limit_reached"):
            source_message += " The selected result cap was reached; narrow the time/region or raise the cap to inspect the full request."
    else:
        sample = bundled_sample()
        events = list(sample.events)
        source_label = "Offline USGS sample · used until the live query succeeds"
        if "live_error" in st.session_state:
            st.warning(f"USGS query failed: {st.session_state['live_error']} The bundled sample is shown so analysis remains available.")
        else:
            st.info("Submit the live catalog query in the sidebar. The bundled sample is shown until a query completes.")

if source_message:
    st.info(source_message)
if not events:
    st.warning("No events are loaded. Try a broader query or select another source.")
    st.stop()

all_frame = events_to_frame(events)
valid_mags = all_frame["magnitude"].dropna()
valid_depths = all_frame["depth_km"].dropna()

with st.sidebar:
    st.markdown('<div class="side-label">Explore loaded events</div>', unsafe_allow_html=True)
    min_date = all_frame["time"].min().date()
    max_date = all_frame["time"].max().date()
    selected_dates = st.date_input("Origin time range (UTC)", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    mag_bounds = None
    if len(valid_mags):
        low, high = float(valid_mags.min()), float(valid_mags.max())
        if high == low:
            low, high = low - .5, high + .5
        mag_range = st.slider("Reported magnitude", min_value=float(low), max_value=float(high), value=(float(low), float(high)), step=.1)
        mag_bounds = mag_range
    else:
        st.caption("No reported magnitudes in this selection.")
    depth_bounds = None
    if len(valid_depths):
        low_d, high_d = float(valid_depths.min()), float(valid_depths.max())
        if high_d == low_d:
            low_d, high_d = low_d - 1, high_d + 1
        depth_range = st.slider("Depth (km)", min_value=float(low_d), max_value=float(high_d), value=(float(low_d), float(high_d)), step=1.0)
        depth_bounds = depth_range
    region_enabled = st.checkbox("Limit to a geographic box", value=False)
    local_box = None
    if region_enabled:
        region_cols = st.columns(2)
        with region_cols[0]:
            south = st.number_input("South", -90.0, 89.0, -20.0, step=1.0, key="filter_south")
            west = st.number_input("West", -180.0, 179.0, -130.0, step=1.0, key="filter_west")
        with region_cols[1]:
            north = st.number_input("North", -89.0, 90.0, 70.0, step=1.0, key="filter_north")
            east = st.number_input("East", -179.0, 180.0, -60.0, step=1.0, key="filter_east")
        try:
            local_box = BoundingBox(south, north, west, east)
        except ValueError as exc:
            st.warning(str(exc))
    include_missing_mag = st.checkbox("Keep events with unknown magnitude", True)
    include_missing_depth = st.checkbox("Keep events with unknown depth", True)
    type_options = sorted(str(value) for value in all_frame["event_type"].dropna().unique())
    chosen_type = st.selectbox("Event type", ["All types", *type_options])

date_start = selected_dates[0] if isinstance(selected_dates, (tuple, list)) and selected_dates else min_date
date_end = selected_dates[-1] if isinstance(selected_dates, (tuple, list)) and len(selected_dates) > 1 else date_start
filter_spec = EventFilters(
    start_date=date_start, end_date=date_end, magnitude_range=mag_bounds,
    depth_range_km=depth_bounds, bbox=local_box,
    event_types=None if chosen_type == "All types" else frozenset({chosen_type}),
    include_missing_magnitude=include_missing_mag, include_missing_depth=include_missing_depth,
)
filtered = filter_events(events, filter_spec)
summary = calculate_summary(filtered)
filtered_frame = events_to_frame(filtered)

st.caption(f"SOURCE  /  {source_label}     ·     FILTERED WINDOW  /  {date_start} to {date_end} UTC     ·     {len(filtered):,} of {len(events):,} events")
if len(filtered) == 0:
    st.warning("No events match these filters. Adjust the date, magnitude, depth, or event-type controls.")
    st.stop()

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Events", f"{summary.event_count:,}")
k2.metric("Largest reported M", f"{summary.largest_magnitude:.1f}" if summary.largest_magnitude is not None else "—", help=f"Available for {summary.magnitude_count:,} events; magnitude values are reported by the source.")
k3.metric("Mean reported M", f"{summary.mean_magnitude:.2f}" if summary.mean_magnitude is not None else "—", help="Descriptive arithmetic mean of available catalog magnitudes; scales/types may differ.")
k4.metric("Mean depth", f"{summary.mean_depth_km:.1f} km" if summary.mean_depth_km is not None else "—", help=f"Available for {summary.depth_count:,} events.")
k5.metric("Median depth", f"{summary.median_depth_km:.1f} km" if summary.median_depth_km is not None else "—", help=f"Available for {summary.depth_count:,} events.")
k6.metric("Deep (>300 km)", f"{summary.deep_count:,}", help=f"Depth grouping only; {summary.missing_depth_count:,} events have no reported depth.")
st.markdown('<div class="source-note">Catalog values are observations reported by contributing networks. Missing measurements stay missing. Mean magnitude is descriptive, especially when the catalog mixes magnitude types.</div>', unsafe_allow_html=True)

map_col, detail_col = st.columns([1.65, 1])
with map_col:
    st.subheader("Global event map")
    st.plotly_chart(earthquake_map(filtered), width="stretch", config={"scrollZoom": True, "displaylogo": False})
    st.caption("Marker size is a bounded visual cue for reported magnitude; color encodes reported depth, with unknown depths in gray. Hover for catalog details. This is not an energy scale.")

with detail_col:
    st.subheader("Catalog event list")
    table = filtered_frame.sort_values("time", ascending=False).copy()
    table["time"] = table["time"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    visible_columns = ["event_id", "time", "magnitude", "magnitude_type", "depth_km", "place"]
    selection = st.dataframe(
        table[visible_columns], width="stretch", height=390, hide_index=True,
        on_select="rerun", selection_mode="single-row", key="event_table",
        column_config={
            "event_id": st.column_config.TextColumn("Event ID", width="small"),
            "time": st.column_config.TextColumn("Origin time (UTC)", width="medium"),
            "magnitude": st.column_config.NumberColumn("M", format="%.1f"),
            "magnitude_type": st.column_config.TextColumn("Type", width="small"),
            "depth_km": st.column_config.NumberColumn("Depth km", format="%.1f"),
            "place": st.column_config.TextColumn("USGS place", width="large"),
        },
    )
    selected_rows = selection.selection.rows
    if selected_rows and 0 <= selected_rows[0] < len(table):
        selected_event = table.iloc[selected_rows[0]]
        st.markdown("#### Selected event details")
        st.write(f"**{selected_event['place'] or 'Location not reported'}**")
        d1, d2 = st.columns(2)
        d1.metric("Magnitude", f"{selected_event['magnitude']:.1f} {selected_event['magnitude_type'] or ''}" if pd.notna(selected_event["magnitude"]) else "Not reported")
        d2.metric("Depth", f"{selected_event['depth_km']:.1f} km" if pd.notna(selected_event["depth_km"]) else "Not reported")
        st.caption(f"ID: {selected_event['event_id']} · Origin: {selected_event['time']}")
        st.caption(f"Epicenter: {selected_event['latitude']:.4f}°, {selected_event['longitude']:.4f}°")
        url = selected_event["url"]
        if isinstance(url, str) and url.startswith("https://"):
            st.link_button("Open source event", url)
    else:
        st.caption("Select a row to inspect its reported source details and event link.")

st.divider()
st.subheader("Activity and source-parameter distributions")
period_days = max(1, (date_end - date_start).days + 1)
frequency = "D" if period_days <= 45 else "W-MON" if period_days <= 400 else "MS"
time_label = {"D": "Daily", "W-MON": "Weekly", "MS": "Monthly"}[frequency]
chart_a, chart_b = st.columns(2)
with chart_a:
    st.markdown(f"#### {time_label} event counts")
    st.plotly_chart(timeline_figure(filtered, frequency), width="stretch", config={"displaylogo": False})
with chart_b:
    st.markdown("#### Reported magnitude distribution")
    st.plotly_chart(magnitude_histogram_figure(filtered), width="stretch", config={"displaylogo": False})
chart_c, chart_d = st.columns(2)
with chart_c:
    st.markdown("#### Magnitude and depth")
    st.plotly_chart(depth_magnitude_figure(filtered), width="stretch", config={"displaylogo": False})
    st.caption(f"Plotted events with both values: {int(filtered_frame.dropna(subset=['magnitude', 'depth_km']).shape[0]):,} (unknown values omitted from this chart only).")
with chart_d:
    st.markdown("#### Depth groups")
    depth_counts = pd.DataFrame({"Depth class": ["Shallow <70 km", "Intermediate 70–300 km", "Deep >300 km"], "Events": [summary.shallow_count, summary.intermediate_count, summary.deep_count]})
    st.bar_chart(depth_counts, x="Depth class", y="Events", color="#608d83", width="stretch")
    st.caption(f"Depth available for {summary.depth_count:,} events; unknown depth: {summary.missing_depth_count:,}. These bins are descriptive groupings.")

with st.expander("Export filtered catalog"):
    export_frame = events_to_frame(filtered)
    st.download_button("Download filtered events as CSV", export_frame.to_csv(index=False).encode("utf-8"), file_name="earthquake_events_filtered.csv", mime="text/csv")

with st.expander("Interpretation and limitations"):
    st.write("Magnitude is a logarithmic measure of event size, not a linear quantity or a direct measurement of local shaking. The API's preferred magnitude may use different methods (for example Mw, mb, or ML); the dashboard preserves the reported type and labels the mean as descriptive.")
    st.write("Depth is the catalog's reported hypocentral depth in kilometers. It can be less well constrained than horizontal location and may use different reference conventions across networks. The epicenter is the surface coordinate associated with the reported hypocenter; it is not a rupture footprint.")
    st.write("The map and charts describe the events in the selected catalog and filters. Temporal rates and spatial patterns depend on magnitude completeness, station coverage, catalog revisions, and query bounds. This tool does not predict earthquakes or replace professional seismicity analysis.")
