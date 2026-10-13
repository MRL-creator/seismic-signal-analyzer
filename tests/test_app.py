"""Check that the bundled example renders without contacting external services."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_bundled_example_renders_without_exceptions():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    app.run()
    assert not app.exception, [error.message for error in app.exception]
    assert app.metric

