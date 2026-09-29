from io import BytesIO

import numpy as np
import pytest

from seismic_analyzer.data import load_csv, load_sample


def test_load_timestamp_and_choose_channel():
    data = b"timestamp,vertical,north\n2024-01-01T00:00:00Z,1,2\n2024-01-01T00:00:01Z,2,3\n2024-01-01T00:00:02Z,3,4\n2024-01-01T00:00:03Z,4,5\n2024-01-01T00:00:04Z,5,6\n2024-01-01T00:00:05Z,6,7\n2024-01-01T00:00:06Z,7,8\n2024-01-01T00:00:07Z,8,9\n2024-01-01T00:00:08Z,9,10\n2024-01-01T00:00:09Z,10,11\n2024-01-01T00:00:10Z,11,12\n2024-01-01T00:00:11Z,12,13\n2024-01-01T00:00:12Z,13,14\n2024-01-01T00:00:13Z,14,15\n2024-01-01T00:00:14Z,15,16\n2024-01-01T00:00:15Z,16,17\n"
    trace = load_csv(BytesIO(data), channel="north")
    assert trace.channel == "north"
    assert trace.sampling_rate == pytest.approx(1)
    assert trace.data[-1] == 17


def test_sample_index_is_loaded_as_monotonic_axis():
    table = "sample_index,amplitude\n" + "\n".join(f"{i},{np.sin(i)}" for i in range(32))
    trace = load_csv(BytesIO(table.encode()))
    assert trace.time[0] == 0
    assert np.all(np.diff(trace.time) > 0)


@pytest.mark.parametrize("table, message", [
    ("x,y\n0,1\n1,2\n", "time column"),
    ("time,a\n" + "".join(f"{i + (0.1 if i >= 10 else 0)},{np.sin(i)}\n" for i in range(16)), "uniformly spaced"),
])
def test_invalid_data(table, message):
    with pytest.raises(ValueError, match=message):
        load_csv(BytesIO(table.encode()))


def test_bundled_sample_loads():
    trace = load_sample()
    assert len(trace.data) == 12000
    assert trace.sampling_rate == pytest.approx(100)
    assert trace.channel == "vertical"
