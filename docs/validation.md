# Numerical validation

Run from the repository root after the editable installation:

```sh
python examples/validate.py
```

The script generates 10,000 samples at 100 Hz containing a 7.5 Hz sine with
amplitude 2.0 and a 30 Hz sine with amplitude 0.5. These inputs are constructed
independently of the analysis routines, giving a known reference.

| Check | Expected | Observed |
| --- | --- | --- |
| Dominant frequency | 7.500 Hz | 7.500 Hz |
| 7.5 Hz amplitude | 2.000 | 2.000000 |
| Dominant frequency after a 5–10 Hz band-pass | 7.500 Hz | 7.500 Hz |
| Fraction of original 30 Hz amplitude retained | Less than 0.01 | About 0.00000006 |

Measured on 2026-10-13 with Python 3.14. The script checks frequency within one
FFT bin, original amplitude within 1%, and rejection of at least 99% of the
interfering amplitude. It removes five seconds from each filtered edge before
measurement to avoid confusing padding transients with interior behavior.
`tests/test_validation.py` executes this same example in CI.

This is a deterministic synthetic check, not a calibrated instrument test.
Bin-aligned sinusoids are an easier case than short, noisy, nonstationary field
records. It does not validate event identification, physical amplitude units,
or every filter configuration. See the README's scientific notes for the
Hann-window normalization and forward/backward filter interpretation.

