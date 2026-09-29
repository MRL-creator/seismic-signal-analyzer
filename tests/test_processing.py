import numpy as np
import pytest

from seismic_analyzer.processing import preprocess


def test_bandpass_reduces_out_of_band_energy():
    fs = 100.0
    t = np.arange(4000) / fs
    x = np.sin(2 * np.pi * 5 * t) + np.sin(2 * np.pi * 30 * t)
    y = preprocess(x, fs, filter_type="bandpass", low_hz=3, high_hz=8)
    assert np.std(y[500:-500]) == pytest.approx(1 / np.sqrt(2), rel=.08)


def test_filter_rejects_invalid_nyquist_cutoff():
    with pytest.raises(ValueError, match="Nyquist"):
        preprocess(np.ones(200), 20, filter_type="lowpass", high_hz=15)


def test_peak_normalization():
    y = preprocess(np.array([-2., 1., 0.]), 1, normalization="peak")
    assert np.max(np.abs(y)) == 1
