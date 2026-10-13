# Seismic Signal Analyzer: visible signal-processing decisions

## Problem and implementation

Waveform analysis combines sampling, preprocessing, and interpretation.
This project makes those steps visible through CSV loading, sampling checks,
optional filtering and normalization, FFT spectra, spectrograms, peak screening,
and exports. Processing lives in reusable NumPy/SciPy modules behind Streamlit.

## Decision and trade-off

The interface rejects irregular sampling for operations that assume a uniform
time grid. It uses a Hann-windowed spectrum and forward/backward Butterworth
filtering. These choices reduce leakage and net interior phase shift, but they
do not remove resolution limits, edge transients, or the need for calibration.

## Evidence

The [reproducible numerical example](validation.md) recovers a known 7.5 Hz
signal and its amplitude, then demonstrates rejection of 30 Hz interference.
The sample workstation record is explicitly synthetic. CI also covers CSV
validation, event-screening behavior, and short-trace normalization.

## Engineering lesson and next step

A clear plot needs clear assumptions about sample rate and units. The next
step would be a documented real, openly licensed waveform and instrument
metadata, with reference results from established seismological software.

