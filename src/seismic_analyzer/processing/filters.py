"""Reusable signal conditioning based on SciPy's established implementations."""

from __future__ import annotations

import numpy as np
from scipy import signal


def preprocess(data: np.ndarray, sampling_rate: float, *, detrend: bool = False, normalization: str = "none", filter_type: str = "none", low_hz: float | None = None, high_hz: float | None = None, order: int = 4, smooth_seconds: float = 0.0) -> np.ndarray:
    """Apply optional linear detrending, Butterworth filtering, scaling, and smoothing.

    Butterworth cutoffs are in Hz; filtering is forward-backward (zero phase),
    which doubles the effective order and can create edge transients.
    """
    values = np.asarray(data, dtype=float).copy()
    if values.ndim != 1 or len(values) < 16 or not np.isfinite(values).all():
        raise ValueError("Processing requires at least 16 finite, one-dimensional samples.")
    if sampling_rate <= 0:
        raise ValueError("Sampling rate must be positive.")
    if not isinstance(order, int) or order < 1:
        raise ValueError("Filter order must be a positive integer.")
    if smooth_seconds < 0:
        raise ValueError("Smoothing duration cannot be negative.")
    if detrend:
        values = signal.detrend(values, type="linear")
    nyquist = sampling_rate / 2
    if filter_type != "none":
        if filter_type in {"lowpass", "highpass"}:
            cutoff = high_hz if filter_type == "lowpass" else low_hz
            if cutoff is None or not 0 < cutoff < nyquist:
                raise ValueError(f"{filter_type} cutoff must be between 0 and Nyquist ({nyquist:g} Hz).")
            wn, btype = cutoff, filter_type
        elif filter_type == "bandpass":
            if low_hz is None or high_hz is None or not 0 < low_hz < high_hz < nyquist:
                raise ValueError(f"Band-pass edges must satisfy 0 < low < high < Nyquist ({nyquist:g} Hz).")
            wn, btype = (low_hz, high_hz), "bandpass"
        else:
            raise ValueError("Filter type must be none, lowpass, highpass, or bandpass.")
        if len(values) < 3 * (2 * order + 1):
            raise ValueError("Trace is too short for the selected zero-phase filter order.")
        sos = signal.butter(order, wn, btype=btype, fs=sampling_rate, output="sos")
        values = signal.sosfiltfilt(sos, values)
    if smooth_seconds > 0:
        width = max(3, int(round(smooth_seconds * sampling_rate)) | 1)
        if width >= len(values):
            raise ValueError("Smoothing window must be shorter than the trace.")
        values = signal.savgol_filter(values, width, polyorder=min(2, width - 1))
    if normalization == "peak":
        scale = np.max(np.abs(values))
        if scale == 0:
            raise ValueError("Cannot peak-normalize a zero-valued signal.")
        values /= scale
    elif normalization == "z-score":
        scale = np.std(values)
        if scale == 0:
            raise ValueError("Cannot z-score a constant signal.")
        values = (values - np.mean(values)) / scale
    elif normalization != "none":
        raise ValueError("Normalization must be none, peak, or z-score.")
    return values
