"""Reproduce a known-frequency and filtering check using the application modules."""

from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from seismic_analyzer.analysis import amplitude_spectrum
from seismic_analyzer.processing import preprocess


def validate():
    sampling_rate = 100.0
    time = np.arange(10_000) / sampling_rate
    trace = 2 * np.sin(2 * np.pi * 7.5 * time) + 0.5 * np.sin(2 * np.pi * 30 * time)
    frequency, amplitude, dominant = amplitude_spectrum(trace, sampling_rate)
    target_amplitude = float(amplitude[np.argmin(abs(frequency - 7.5))])
    original_interference = float(amplitude[np.argmin(abs(frequency - 30))])
    filtered = preprocess(trace, sampling_rate, filter_type="bandpass", low_hz=5, high_hz=10)
    # Discard 5 seconds at each end so this check does not measure filter-edge transients.
    filtered_frequency, filtered_amplitude, filtered_dominant = amplitude_spectrum(
        filtered[500:-500], sampling_rate
    )
    remaining = float(filtered_amplitude[np.argmin(abs(filtered_frequency - 30))])
    ratio = remaining / original_interference
    print(f"Expected dominant frequency: 7.500 Hz; measured: {dominant:.3f} Hz")
    print(f"Expected target amplitude: 2.000; measured: {target_amplitude:.6f}")
    print(f"Filtered dominant frequency: {filtered_dominant:.3f} Hz")
    print(f"30 Hz amplitude retained after 5-10 Hz band-pass: {ratio:.8f}")
    if abs(dominant - 7.5) > sampling_rate / len(trace):
        raise AssertionError("Known frequency was not recovered within one FFT bin.")
    if abs(target_amplitude - 2.0) > 0.02:
        raise AssertionError("Known sine amplitude differs by more than 1%.")
    if abs(filtered_dominant - 7.5) > sampling_rate / len(filtered[500:-500]) or ratio >= 0.01:
        raise AssertionError("Band-pass did not retain the target and reject 30 Hz interference.")


if __name__ == "__main__":
    validate()
