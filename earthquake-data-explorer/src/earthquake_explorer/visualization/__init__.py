"""Plotly figures for geographic and descriptive exploration."""

from .maps import earthquake_map
from .charts import depth_magnitude_figure, magnitude_histogram_figure, timeline_figure

__all__ = ["earthquake_map", "timeline_figure", "magnitude_histogram_figure", "depth_magnitude_figure"]
