# modshim

A Python library for enhancing existing modules without modifying their source code - a clean alternative to vendoring.

## Overview

`modshim` allows you to overlay custom functionality onto existing Python modules while preserving their original behavior. This is particularly useful when you need to:

- Fix bugs in third-party libraries without forking
- Modify behavior of existing functions
- Add new methods or properties to built-in types
- Test alternative implementations

## Installation

```bash
pip install modshim
```

## Usage

```python
from modshim import shim

# Create an enhanced version of the json module that uses single quotes
json_single = shim(
    upper="my_json_mods",     # Module with your modifications
    lower="json",             # Original module to enhance
    as_name="json_single"     # Name for the merged result
)

# Use it like the original, but with your enhancements
result = json_single.dumps({"hello": "world"})
print(result)  # {'hello': 'world'}
```

## Key Features

- **Non-invasive**: Original modules remain usable and unchanged
- **Transparent**: Enhanced modules behave like regular Python modules
- **Thread-safe**: Safe for concurrent usage
- **Type-safe**: Fully typed with modern Python type hints

## Example Use Cases

```python
# Add weekend detection to datetime
dt = shim("my_datetime_ext", "datetime").datetime(2024, 1, 6)
print(dt.is_weekend)  # True

# Add schema validation to CSV parsing
reader = shim("my_csv_ext", "csv").DictReader(
    file,
    schema={"id": int, "name": str}
)

# Add automatic punycode decoding to urllib
url = shim("my_urllib_ext", "urllib").parse.urlparse(
    "https://xn--bcher-kva.example.com"
)
print(url.netloc)  # "bücher.example.com"
```

## Why Not Vendor?

Unlike vendoring (copying) code:
- No need to maintain copies of dependencies
- Easier updates when upstream changes
- Cleaner separation between original and custom code
- More maintainable and testable enhancement path

