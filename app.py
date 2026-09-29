"""Streamlit entry point for the Seismic Signal Analyzer workstation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from seismic_analyzer.analysis import amplitude_spectrum, detect_events, estimate_snr, spectrogram
from seismic_analyzer.data import Waveform, load_csv, load_sample
from seismic_analyzer.processing import preprocess


st.set_page_config(page_title="Seismic Signal Analyzer", page_icon="S", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
html, body, [class*="css"] { font-family: Arial, sans-serif; }
.stApp { background: #f4f5f2; color: #192728; }
[data-testid="stSidebar"] { background: #142829; }
[data-testid="stSidebar"] * { color: #edf3ed !important; }
.eyebrow { font: 500 11px Consolas, monospace; letter-spacing: .16em; color:#bf6a49; text-transform:uppercase; }
.hero { padding: 8px 0 18px; border-bottom: 1px solid #d8dfd9; margin-bottom: 20px; }
.hero h1 { font-size: 34px; line-height:1.15; letter-spacing:-.04em; margin: 8px 0 6px; color:#172829; }
.hero p { color:#687777; margin:0; font-size:14px; }
.metric-label { color:#667777; font: 500 10px Consolas,monospace; text-transform:uppercase; letter-spacing:.1em; }
[data-testid="stMetric"] { background:#fff; border:1px solid #e1e6e1; border-radius:8px; padding:14px 16px; }
[data-testid="stMetricValue"] { color:#183b3c; font-family:Consolas,monospace; }
.stTabs [data-baseweb="tab-list"] { gap:22px; }
.note { border-left:3px solid #c57552; padding:9px 13px; background:#fff9f4; color:#675b53; font-size:12px; }
.sidebar-footer { padding-top:14px; margin-top:18px; border-top:1px solid #3a5050; color:#a9b8b1; font:11px Consolas,monospace; }
</style>
<div class="hero"><div class="eyebrow">Field notes · signal lab / 01</div><h1>Seismic Signal Analyzer</h1><p>Inspect a waveform, condition the trace, and explore its frequency content.</p></div>
""", unsafe_allow_html=True)


def plot_layout(fig: go.Figure, height: int = 310) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=18, r=18, t=20, b=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff", font=dict(family="Consolas, monospace", size=10, color="#637272"), hovermode="x unified", xaxis=dict(showgrid=True, gridcolor="#e9eeea", zeroline=False), yaxis=dict(showgrid=True, gridcolor="#e9eeea", zeroline=False), legend=dict(orientation="h", y=1.12))
    return fig


def upload_waveform() -> tuple[Waveform, float]:
    with st.sidebar:
        st.markdown('<div class="eyebrow">01 / Source</div>', unsafe_allow_html=True)
        mode = st.radio("Waveform source", ["Example trace", "Upload CSV"], label_visibility="collapsed")
        if mode == "Example trace":
            waveform = load_sample()
            fs = waveform.sampling_rate
            st.caption("Bundled synthetic two-component local-event example · 100 Hz")
        else:
            uploaded = st.file_uploader("Choose a waveform CSV", type=["csv"])
            unit = st.text_input("Amplitude unit", "counts")
            fs_override = st.number_input("Sampling rate for sample-index files (Hz)", min_value=0.001, value=100.0, step=1.0, help="Used when the CSV time axis is a sample index; timestamp files infer their rate.")
            if uploaded is None:
                st.info("Upload a CSV with a time or sample-index column and one or more numeric channels. The bundled trace is available as the default.")
                waveform = load_sample()
                fs = waveform.sampling_rate
            else:
                raw = pd.read_csv(uploaded)
                excluded = {"time", "time_s", "timestamp", "seconds", "elapsed_s", "elapsed_seconds", "sample", "sample_index", "index", "n"}
                channels = [str(c) for c in raw.columns if str(c).strip().lower() not in excluded and pd.to_numeric(raw[c], errors="coerce").notna().all()]
                if not channels:
                    raise ValueError("No numeric channels found in the uploaded CSV.")
                selected = st.selectbox("Amplitude channel", channels)
                uploaded.seek(0)
                waveform = load_csv(uploaded, channel=selected, unit=unit, source=uploaded.name, sampling_rate=fs_override)
                fs = waveform.sampling_rate
        st.markdown('<div class="sidebar-footer">LOCAL ANALYSIS · CSV / SCI-PY</div>', unsafe_allow_html=True)
    return waveform, fs


try:
    waveform, fs = upload_waveform()
except Exception as exc:
    st.error(str(exc))
    st.stop()

with st.sidebar:
    st.markdown('<div class="eyebrow">02 / Conditioning</div>', unsafe_allow_html=True)
    detrend = st.checkbox("Remove linear trend", value=True)
    normalization = st.selectbox("Normalization", ["none", "peak", "z-score"], format_func=lambda x: {"none": "None", "peak": "Peak amplitude", "z-score": "Z-score"}[x])
    filter_type = st.selectbox("Filter", ["none", "bandpass", "highpass", "lowpass"], format_func=lambda x: x.title())
    nyquist = fs / 2
    low_hz, high_hz = 1.0, min(15.0, nyquist * .8)
    if filter_type == "bandpass":
        low_hz = st.number_input("Low edge (Hz)", min_value=0.001, max_value=max(0.002, nyquist * .95), value=min(1.0, nyquist * .2), step=.1)
        high_hz = st.number_input("High edge (Hz)", min_value=0.002, max_value=max(0.003, nyquist * .99), value=max(.003, min(15.0, nyquist * .8)), step=.5)
    elif filter_type == "highpass":
        low_hz = st.number_input("Cutoff (Hz)", min_value=0.001, max_value=max(0.002, nyquist * .95), value=min(1.0, nyquist * .2), step=.1)
    elif filter_type == "lowpass":
        high_hz = st.number_input("Cutoff (Hz)", min_value=0.002, max_value=max(0.003, nyquist * .99), value=max(.003, min(15.0, nyquist * .8)), step=.5)
    smoothing = st.slider("Smoothing window (s)", min_value=0.0, max_value=min(2.0, max(.1, waveform.duration / 5)), value=0.0, step=.1)

try:
    processed = preprocess(waveform.data, fs, detrend=detrend, normalization=normalization, filter_type=filter_type, low_hz=low_hz, high_hz=high_hz, smooth_seconds=smoothing)
except Exception as exc:
    st.error(f"Processing settings: {exc}")
    st.stop()

freq, amp, dominant = amplitude_spectrum(processed, fs)
f_spec, t_spec, power = spectrogram(processed, fs)
events = detect_events(processed, waveform.time, fs)
amplitude_label = "normalized amplitude" if normalization != "none" else waveform.unit

m1, m2, m3, m4 = st.columns(4)
m1.metric("Samples", f"{len(processed):,}")
m2.metric("Sample rate", f"{fs:g} Hz")
m3.metric("Nyquist", f"{fs/2:g} Hz")
m4.metric("Dominant frequency", f"{dominant:.2f} Hz")
st.caption(f"{waveform.source}  /  channel: {waveform.channel}  /  duration: {waveform.duration:.2f} s  /  amplitude: {waveform.unit}")

tab_wave, tab_spectrum, tab_events = st.tabs(["Waveform & spectrogram", "Frequency spectrum", "Event screening"])
with tab_wave:
    left, right = st.columns([1.55, 1])
    with left:
        st.markdown("#### Waveform")
        fig = go.Figure(go.Scattergl(x=waveform.time, y=processed, mode="lines", name="Processed", line=dict(color="#b75f42", width=1)))
        if events.shape[0]:
            fig.add_trace(go.Scatter(x=events.time_s, y=events.amplitude, mode="markers", name="Threshold peaks", marker=dict(color="#22494a", size=7, symbol="diamond")))
        fig.update_layout(xaxis_title="Elapsed time (s)", yaxis_title=f"Amplitude ({'normalized' if normalization != 'none' else waveform.unit})")
        st.plotly_chart(plot_layout(fig, 355), use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
    with right:
        st.markdown("#### Time-frequency")
        db = 10 * np.log10(np.maximum(power, np.finfo(float).tiny))
        fig = go.Figure(go.Heatmap(x=t_spec, y=f_spec, z=db, colorscale=[[0, "#e9eee9"], [.45, "#9db8ac"], [.75, "#477575"], [1, "#bf704e"]], colorbar=dict(title="dB/Hz", thickness=10)))
        fig.update_layout(xaxis_title="Elapsed time (s)", yaxis_title="Frequency (Hz)")
        st.plotly_chart(plot_layout(fig, 355), use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
        st.caption("Hann-windowed power spectral density · segment length 4 s (or trace length for short records).")

with tab_spectrum:
    st.markdown("#### One-sided amplitude spectrum")
    fig = go.Figure(go.Scattergl(x=freq[1:], y=amp[1:], mode="lines", line=dict(color="#315f60", width=1.5), name="Amplitude"))
    fig.add_vline(x=dominant, line_dash="dot", line_color="#bd6848", annotation_text=f"Peak {dominant:.2f} Hz")
    fig.update_layout(xaxis_title="Frequency (Hz)", yaxis_title=f"Amplitude ({amplitude_label}; Hann corrected)")
    st.plotly_chart(plot_layout(fig, 430), use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
    st.caption(f"Frequency resolution: {fs/len(processed):.4g} Hz · Nyquist limit: {fs/2:g} Hz. Dominant frequency is the strongest non-zero FFT bin.")

with tab_events:
    st.markdown("#### Amplitude threshold screening")
    st.markdown('<div class="note">These peaks are an educational amplitude-based screen. They are not validated event catalogs and do not identify P- or S-wave arrivals.</div>', unsafe_allow_html=True)
    threshold_sigma = st.slider("Peak threshold (robust standard deviations)", 2.0, 10.0, 4.0, .5)
    events = detect_events(processed, waveform.time, fs, threshold_sigma=threshold_sigma)
    if events.empty:
        st.info("No local maxima exceeded the selected threshold.")
    else:
        st.dataframe(events.rename(columns={"time_s": "Time (s)", "amplitude": f"Amplitude ({amplitude_label})", "prominence": "Prominence"}), use_container_width=True, hide_index=True)
        st.download_button("Download peak table", events.to_csv(index=False).encode(), file_name="screened_peaks.csv", mime="text/csv")
    st.markdown("#### Windowed signal-to-noise ratio")
    st.caption("Choose representative windows. SNR = 20 log10(RMS signal / RMS noise), reported in dB.")
    max_t = max(float(waveform.time[-1]), .1)
    a, b = st.columns(2)
    with a:
        n0 = st.number_input("Noise start (s)", 0.0, max_t, 0.0, max(.1, max_t / 100))
        n1 = st.number_input("Noise end (s)", 0.01, max_t, min(5.0, max_t), max(.1, max_t / 100))
    with b:
        s0 = st.number_input("Signal start (s)", 0.0, max_t, min(20.0, max_t / 2), max(.1, max_t / 100))
        s1 = st.number_input("Signal end (s)", 0.01, max_t, min(40.0, max_t), max(.1, max_t / 100))
    try:
        st.metric("Windowed RMS SNR", f"{estimate_snr(processed, fs, s0, s1, n0, n1):.2f} dB")
    except ValueError as exc:
        st.info(str(exc))

with st.expander("Processing notes & assumptions"):
    st.write(f"Applied: linear detrend **{'on' if detrend else 'off'}** · {filter_type} filter · {normalization} scaling · smoothing {smoothing:g} s. Zero-phase filtering uses forward/backward processing and can affect record edges. CSV time samples must be near-uniform (interval variation ≤1%). Sample rate: {fs:g} Hz; frequencies at or above Nyquist ({fs/2:g} Hz) cannot be represented reliably.")
    st.write("P/S phase picking is intentionally not attempted: reliable phase identification depends on station response, instrument metadata, noise, event context, and validated picking methods.")
