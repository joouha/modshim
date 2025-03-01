"""Target package containing overlay modules."""
from __future__ import annotations

from . import upper
from modshim import register

# Register overlays
register(lower="csv", upper="target.upper.csv_schema", merge="csv_schema")
register(
    lower="datetime", upper="target.upper.datetime_weekend", merge="datetime_weekend"
)
register(lower="json", upper="target.upper.json_metadata", merge="json_metadata")
register(
    lower="json", upper="target.upper.json_single_quotes", merge="json_single_quotes"
)
register(
    lower="pathlib", upper="target.upper.pathlib_is_empty", merge="pathlib_is_empty"
)
register(lower="random", upper="target.upper.random_fixed", merge="random_fixed")
register(lower="time", upper="target.upper.time_dilation", merge="time_dilation")
register(lower="urllib", upper="target.upper.urllib_punycode", merge="urllib_punycode")

__all__ = ["upper"]
