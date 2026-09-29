"""Fourier and time-frequency analysis for evenly sampled traces."""

from __future__ import annotations

import numpy as np
from scipy import signal
from scipy.fft import rfft, rfftfreq


def amplitude_spectrum(data: np.ndarray, sampling_rate: float) -> tuple[np.ndarray, np.ndarray, float]:
    """Return one-sided Hann-window amplitude spectrum and strongest non-DC bin."""
    x = np.asarray(data, dtype=float)
    if x.ndim != 1 or len(x) < 2 or not np.isfinite(x).all() or not np.isfinite(sampling_rate) or sampling_rate <= 0:
        raise ValueError("FFT requires a one-dimensional trace and positive sampling rate.")
    x = signal.detrend(x, type="constant")
    window = signal.windows.hann(len(x), sym=False)
    magnitude = np.abs(rfft(x * window)) / np.sum(window)
    if len(x) % 2 == 0:
        magnitude[1:-1] *= 2
    else:
        magnitude[1:] *= 2
    frequencies = rfftfreq(len(x), d=1 / sampling_rate)
    dominant = float(frequencies[1 + np.argmax(magnitude[1:])]) if len(frequencies) > 1 else 0.0
    return frequencies, magnitude, dominant


def spectrogram(data: np.ndarray, sampling_rate: float, segment_seconds: float = 4.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return time, frequency, and power-density arrays (amplitude units squared per Hz)."""
    x = np.asarray(data, dtype=float)
    if x.ndim != 1 or len(x) < 8 or not np.isfinite(x).all() or not np.isfinite(sampling_rate) or sampling_rate <= 0 or not np.isfinite(segment_seconds) or segment_seconds <= 0:
        raise ValueError("Spectrogram requires a one-dimensional trace and positive sampling rate.")
    nperseg = min(len(x), max(8, int(round(segment_seconds * sampling_rate))))
    return signal.spectrogram(x, fs=sampling_rate, window="hann", nperseg=nperseg, noverlap=nperseg // 2, detrend="constant", scaling="density", mode="psd")
