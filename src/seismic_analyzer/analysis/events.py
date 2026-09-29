"""Amplitude-based event screening; outputs are not seismic phase picks."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import find_peaks


def detect_events(data: np.ndarray, time: np.ndarray, sampling_rate: float, *, threshold_sigma: float = 4.0, min_separation_seconds: float = 1.0, prominence_sigma: float = 2.0) -> pd.DataFrame:
    """Find prominent peaks above robust baseline MAD; a screening heuristic only."""
    x, t = np.asarray(data, float), np.asarray(time, float)
    if x.ndim != 1 or t.shape != x.shape or len(x) < 3 or not np.isfinite(x).all() or not np.isfinite(t).all() or not np.isfinite(sampling_rate) or sampling_rate <= 0:
        raise ValueError("Event detection requires matching one-dimensional data and time arrays.")
    median = np.median(x)
    sigma = 1.4826 * np.median(np.abs(x - median))
    sigma = max(float(sigma), float(np.std(x)) * 1e-6, np.finfo(float).eps)
    # Seismic arrivals may begin with either polarity, so screen the absolute
    # deviation from baseline while preserving signed amplitudes in the table.
    peaks, props = find_peaks(np.abs(x - median), height=threshold_sigma * sigma, prominence=prominence_sigma * sigma, distance=max(1, int(round(min_separation_seconds * sampling_rate))))
    return pd.DataFrame({"time_s": t[peaks], "amplitude": x[peaks], "prominence": props.get("prominences", np.array([]))})


def estimate_snr(data: np.ndarray, sampling_rate: float, signal_start_s: float, signal_end_s: float, noise_start_s: float, noise_end_s: float) -> float:
    """Compute RMS-window SNR in dB from caller-selected noise and signal windows."""
    x = np.asarray(data, float)
    if sampling_rate <= 0 or not np.isfinite(sampling_rate) or not np.isfinite(x).all():
        raise ValueError("SNR requires finite waveform samples and a positive sampling rate.")
    if min(signal_start_s, noise_start_s) < 0 or signal_end_s <= signal_start_s or noise_end_s <= noise_start_s:
        raise ValueError("SNR windows must have non-negative starts and end after start.")
    def rms(start: float, end: float) -> float:
        segment = x[int(start * sampling_rate):int(end * sampling_rate)]
        if len(segment) == 0:
            raise ValueError("SNR window falls outside the waveform or contains no samples.")
        return float(np.sqrt(np.mean(np.square(segment))))
    noise_rms, signal_rms = rms(noise_start_s, noise_end_s), rms(signal_start_s, signal_end_s)
    if noise_rms == 0:
        raise ValueError("Noise window has zero RMS; SNR is undefined.")
    return float(20 * np.log10(signal_rms / noise_rms))
