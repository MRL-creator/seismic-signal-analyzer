"""Generate the deterministic teaching waveform shipped in sample_data/."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt


def main() -> None:
    fs, duration = 100.0, 120.0
    time = np.arange(int(fs * duration)) / fs
    rng = np.random.default_rng(73021)
    # Locally recorded ground motion is presented as instrument counts, not as
    # calibrated displacement/velocity. Noise and phase-like packets are synthetic.
    common = 11 * rng.normal(size=len(time)) + 5 * np.sin(2 * np.pi * .08 * time)
    vertical, north = common.copy(), 0.7 * common.copy()
    for center, frequency, decay, amp in [(28.0, 4.2, 1.2, 85), (36.5, 2.3, 4.4, 150), (41.0, 1.1, 8.0, 62)]:
        envelope = np.exp(-np.maximum(time - center, 0) / decay) * (time >= center)
        packet = amp * envelope * np.sin(2 * np.pi * frequency * (time - center))
        vertical += packet
        north += 0.72 * amp * envelope * np.sin(2 * np.pi * (frequency * .92) * (time - center) + .5)
    # Small independent high-frequency instrument noise.
    sos = butter(3, 20, btype="lowpass", fs=fs, output="sos")
    vertical += 2 * sosfiltfilt(sos, rng.normal(size=len(time)))
    north += 2 * sosfiltfilt(sos, rng.normal(size=len(time)))
    output = Path(__file__).resolve().parents[1] / "sample_data" / "synthetic_local_event.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"time_s": time, "vertical": vertical, "north": north}).to_csv(output, index=False, float_format="%.6f")
    print(f"Wrote {output} ({len(time):,} samples at {fs:g} Hz)")


if __name__ == "__main__":
    main()
