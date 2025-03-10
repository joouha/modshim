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
# my_datetime_ext.py
from datetime import datetime as OriginalDateTime


class datetime(OriginalDateTime):
    """Enhanced datetime class with weekend detection."""

    @property
    def is_weekend(self) -> bool:
        """Return True if the date falls on a weekend (Saturday or Sunday)."""
        return self.weekday() >= 5
```

```python
>>> from modshim import shim

# Create an enhanced version of the json module that uses single quotes
>>> shim(
...     upper="my_datetime_ext",  # Module with your modifications
...     lower="datetime",         # Original module to enhance
...     mount="datetime_mod",     # Name for the merged result
... )

# Use it like the original, but with your enhancements available
>>> from datetime_mod import datetime
>> datetime(2024, 1, 6).is_weekend
True
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

## Creating Enhancement Packages                                                      

Enhancement packages can automatically apply their modifications when imported, meaning they can be imported and used without the need to manually set up the shim.                                                                             

```python
# datetime_mod.py
from datetime import datetime as OriginalDateTime

from modshim import shim

class datetime(OriginalDateTime):
    """Enhanced datetime class with weekend detection."""

    @property
    def is_weekend(self) -> bool:
        """Return True if the date falls on a weekend (Saturday or Sunday)."""
        return self.weekday() >= 5

# `upper` defaults to the calling module
# `mount` defaults to f`{upper}`
shim(lower="datetime")
```

```python
>>> from datetime_mod import datetime
>> datetime(2024, 1, 6).is_weekend
True
```

## Why Not Vendor?

Unlike vendoring (copying) code:
- No need to maintain copies of dependencies
- Easier updates when upstream changes
- Cleaner separation between original and custom code
- More maintainable and testable enhancement path

