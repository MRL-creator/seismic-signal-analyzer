# Seismic Signal Analyzer

<p align="center">
  <strong>A small local waveform workstation for inspecting seismic-style time series.</strong><br>
  CSV in · SciPy processing · interactive waveform, spectrum, and spectrogram out
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-315f60?style=flat-square">
  <img alt="SciPy" src="https://img.shields.io/badge/Signal%20processing-SciPy-bc704e?style=flat-square">
  <img alt="Interface" src="https://img.shields.io/badge/Interface-Streamlit-315f60?style=flat-square">
</p>

## Why this project

Waveform analysis brings together acquisition metadata, sampling theory, signal conditioning, and interpretation. This project makes those steps visible in one approachable workstation, while keeping the calculations in small reusable Python modules. It is designed as a Geophysics Engineering portfolio project and as a learning tool for exploring uniformly sampled waveforms.

> **Scope:** educational/engineering software. It is not a replacement for professional seismological software, calibrated instrument workflows, or expert event/phase review. The included record is synthetic and is not an observation of an earthquake.

## Features

- Read CSV files with elapsed numeric time, ISO-style timestamps, or sample indices; select among multiple amplitude channels.
- Check monotonicity, missing values, numeric samples, and near-uniform time spacing before frequency-domain work.
- View the waveform with zoom and pan, alongside an interactive time-frequency power spectrogram.
- Apply optional linear detrending, Butterworth low-pass/high-pass/band-pass filtering, peak or z-score normalization, and Savitzky–Golay smoothing.
- Inspect a Hann-windowed one-sided FFT amplitude spectrum and strongest non-DC frequency bin.
- Screen for prominent amplitude peaks with SciPy and export the resulting table.
- Calculate RMS-window signal-to-noise ratio from windows the user selects.
- Start immediately with the bundled deterministic, two-channel synthetic local-event record.

## Quick start

Python 3.10 or newer is required.

```bash
git clone <your-repository-url>
cd seismic-signal-analyzer
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
streamlit run app.py
```

The `seismic-analyzer` command is also installed by the editable package. To run the scientific test suite:

```bash
python -m pytest
```

### Run from VS Code

Select the project Python environment, then choose **Seismic Signal Analyzer** in the Run and Debug configuration dropdown and press **F5**. The launch profile starts Streamlit with the correct `streamlit run app.py` command. The plain **Run Python File** action does not launch a Streamlit interface.

## Example workflow

1. Launch the app and leave **Example trace** selected. The bundled vertical component is sampled at 100 Hz.
2. Inspect the waveform and the time-frequency panel. The example contains low-amplitude background noise and synthetic transient packets.
3. Try a 1–15 Hz band-pass, then compare the changed waveform and spectrum. Cutoffs must be below the Nyquist frequency (50 Hz for this example).
4. Adjust the robust amplitude threshold in **Event screening** and review or download the candidate peak table.
5. Choose a pre-event noise window and a later signal window to calculate an RMS SNR.

## CSV format

CSV needs one recognized time column plus one or more numeric channels. Column names are case-insensitive.

| Time column | Meaning | Example |
|---|---|---|
| `time`, `time_s`, `seconds`, `elapsed_s` | Elapsed numeric seconds | `time_s,vertical` |
| `timestamp` | Numeric seconds or parseable date/time | `timestamp,vertical,north` |
| `sample_index`, `sample`, `index`, `n` | Increasing sample number | `sample_index,amplitude` |

For a sample-index file, provide its actual sample rate in the sidebar. Numeric timestamp files infer the sample rate. Date/timestamp files are converted to elapsed UTC seconds. Timestamps must be increasing, and interval coefficient of variation must be at most 1%; irregularly sampled recordings should be resampled with a documented method before using these FFT and filter operations. Units are supplied by the user and default to `counts`; the program does not infer physical calibration.

```csv
time_s,vertical,north
0.00,1.7,-2.1
0.01,2.3,-1.8
0.02,-0.4,0.5
```

## Scientific notes and limits

- **Sampling and Nyquist:** `fs` is the number of samples per second. The Nyquist frequency is `fs / 2`; content above it cannot be uniquely represented after sampling. Uniform sampling is assumed by the FFT, digital filters, and spectrogram.
- **FFT:** SciPy's real-input FFT produces a one-sided spectrum. A Hann window reduces leakage from finite record boundaries; the magnitude is corrected by the window sum. The displayed dominant frequency is the largest non-zero frequency bin, so its resolution is approximately `fs / N` and it is not a sub-bin frequency estimate.
- **Filters:** Butterworth filters are designed in second-order sections and applied forward then backward. This avoids a net phase shift in the interior of the trace; it doubles the effective filter order and edge handling can create transients. Filtering does not recover information absent from the recording.
- **Spectrogram:** The view displays windowed power spectral density (dB/Hz) using 4-second Hann segments with 50% overlap (or a shorter segment for short records). Time and frequency resolution trade off with segment length.
- **Peak screening:** Candidate peaks are local maxima over a robust MAD-derived threshold, with a minimum prominence and separation. They are not verified earthquakes, and threshold peaks can be noise, instrument response, or other transients.
- **SNR:** `20 log10(RMS_signal / RMS_noise)` is calculated for the user-selected windows. It is meaningful only when those windows represent comparable data and the chosen signal/noise intervals suit the use case.
- **P and S phases:** no automatic P/S picker is included. Arrivals depend on component orientation, instrument response, noise conditions, event distance, and seismological context. A threshold peak or change in frequency is not enough to label a phase responsibly.

## Architecture

```text
app.py                         Streamlit interface and Plotly workstation
src/seismic_analyzer/
  data/io.py                   CSV parsing, validation, Waveform value object
  processing/filters.py        Detrend, SOS Butterworth filters, normalization, smoothing
  analysis/spectrum.py         FFT amplitude spectrum and PSD spectrogram
  analysis/events.py           Threshold peak screening and RMS SNR
  cli.py                       Installed command-line launcher
sample_data/                   Synthetic example record
examples/generate_sample.py    Deterministic sample-data generator
tests/                         Scientific and data-validation tests
```

## Research and implementation references

- [ObsPy](https://docs.obspy.org/) is an established open-source Python ecosystem for seismological waveform handling. Its examples show trace-oriented processing and zero-phase filtering; this CSV-first project borrows the transparent workflow idea without adding ObsPy as a dependency.
- SciPy documents the [Butterworth filter design](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html), recommends second-order sections for general-purpose numerical stability, and describes [forward/backward filtering](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.filtfilt.html).
- SciPy's [signal processing tutorial](https://docs.scipy.org/doc/scipy/tutorial/signal.html) explains the Nyquist limit, and its [spectrogram API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.spectrogram.html) exposes segment, overlap, detrending, and PSD scaling choices.
- The UI uses Streamlit's [file uploader](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader) and [interactive Plotly chart support](https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart) for a local workflow without a separate frontend build.

## Testing

The tests use deterministic synthetic signals to check timestamp and sample-index ingestion, invalid/irregular CSV rejection, bundled data, filter behavior and cutoff validation, FFT frequency recovery, peak screening, and a known 20 dB SNR case.

## Future improvements

- Add MiniSEED and StationXML reading through ObsPy, preserving station, component, response, and timing metadata.
- Add documented resampling and response-removal workflows with metadata-aware safeguards.
- Add user-controlled event windows and reviewable manual phase markers; keep automated phase-picking separate and validated.
- Add exportable processing provenance and reproducible analysis sessions.

## Limitations

The app currently accepts CSV only and analyzes one channel at a time. It assumes uniformly sampled data and relies on the user to know the physical meaning and units of amplitude. The bundled sample is a synthetic teaching signal. Event detection is a basic amplitude heuristic, SNR depends on chosen windows, and no automatic P/S picks, source parameters, magnitude estimates, or calibrated ground-motion measurements are provided.
