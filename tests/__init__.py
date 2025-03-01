from modshim import register

# Register overlays
register(lower="csv", upper="modshim.upper.csv_schema", merge="csv_schema")
register(lower="datetime", upper="modshim.upper.datetime_weekend", merge="datetime_weekend")
register(lower="json", upper="modshim.upper.json_metadata", merge="json_metadata")
register(lower="json", upper="modshim.upper.json_single_quotes", merge="json_single_quotes")
register(lower="pathlib", upper="modshim.upper.pathlib_is_empty", merge="pathlib_is_empty")
register(lower="random", upper="modshim.upper.random_fixed", merge="random_fixed")
register(lower="time", upper="modshim.upper.time_dilation", merge="time_dilation")
register(lower="urllib", upper="modshim.upper.urllib_punycode", merge="urllib_punycode")
