from modshim import register

register(lower="csv", upper="upper.csv_schema", merge="csv_schema")
register(lower="datetime", upper="upper.datetime_weekend", merge="datetime_weekend")
register(lower="json", upper="upper.json_metadata", merge="json_metadata")
register(lower="json", upper="upper.json_single_quotes", merge="json_single_quotes")
register(lower="pathlib", upper="upper.pathlib_is_empty", merge="pathlib_is_empty")
register(lower="random", upper="upper.random_fixed", merge="random_fixed")
register(lower="time", upper="upper.time_dilation", merge="time_dilation")
register(lower="urllib", upper="upper.urllib_punycode", merge="urllib_punycode")
