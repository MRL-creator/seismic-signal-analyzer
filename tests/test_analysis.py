import numpy as np
import pytest

from seismic_analyzer.analysis import amplitude_spectrum, detect_events, estimate_snr


def test_fft_finds_known_sine_frequency():
    fs, frequency = 100.0, 7.5
    t = np.arange(10000) / fs
    f, a, dominant = amplitude_spectrum(np.sin(2 * np.pi * frequency * t), fs)
    assert dominant == pytest.approx(frequency)
    assert a[np.argmax(a)] == pytest.approx(1, rel=.01)


def test_peak_screening_finds_impulse_like_event():
    fs = 20
    x = np.zeros(200) + np.random.default_rng(8).normal(0, .1, 200)
    x[100] = 5
    peaks = detect_events(x, np.arange(len(x)) / fs, fs, threshold_sigma=4)
    assert len(peaks) == 1
    assert peaks.time_s.iloc[0] == 5


def test_peak_screening_keeps_negative_polarity():
    fs = 20
    x = np.random.default_rng(4).normal(0, .1, 200)
    x[100] = -5
    peaks = detect_events(x, np.arange(len(x)) / fs, fs, threshold_sigma=4)
    assert len(peaks) == 1
    assert peaks.amplitude.iloc[0] < 0


def test_snr_db_for_ten_to_one_rms():
    fs = 100
    x = np.r_[np.ones(fs), np.ones(fs) * 10]
    assert estimate_snr(x, fs, 1, 2, 0, 1) == pytest.approx(20)
