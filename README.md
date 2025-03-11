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

Suppose we want to add a `is_weekend` property to `datetime` objects.

First create a Python module containing your modifications, following the same module layout as the builtin `datetime` module:

```python
# my_datetime_ext.py

# You can import from the target module in your overlay
from datetime import datetime as OriginalDateTime

# Objects can be override by simply declaring new version with the same name
MAX_YEAR = 3_000

# Sub-classes can be used to override and extend functionality
class datetime(OriginalDateTime):
    """Enhanced datetime class with weekend detection."""

    @property
    def is_weekend(self) -> bool:
        """Return True if the date falls on a weekend (Saturday or Sunday)."""
        return self.weekday() >= 5
```

Then use modshim to mount your modification on top of the builtin `datetime` package under a new namespace:

```python
>>> from modshim import shim
>>> shim(
...     upper="my_datetime_ext",  # Module with your modifications
...     lower="datetime",         # Original module to enhance
...     mount="datetime_mod",     # Name for the merged result
... )
```

We can then import and use the new `datetime_mod` instead of the built in `datetime`, and our modifications will be automatically applied and integrated:

```python
>>> from datetime_mod import MAX_YEAR, datetime
>> MAX_YEAR
3000
>> datetime(2024, 1, 6).is_weekend
True
```

## How It Works

`modshim` creates virtual merged modules by intercepting Python's import system. When a shimmed module is imported, modshim combines the original module with your enhancements, making your modifications appear as if they were part of the original module while preserving all existing functionality.

At its core, modshim works by installing a custom import finder into Python's import machinery. When you call `shim()`, it creates a finder that watches for imports of your specified merged module name. When that module is imported, the finder loads both the original module and your enhancement module, then creates a new virtual module that combines them.

The merging process gives priority to your enhancements - any attributes you define (functions, classes, constants, etc.) override the originals, while all other attributes from the original module remain unchanged. This merged view is completely transparent to code using the module - it behaves exactly like a normal Python module.

Importantly, modshim automatically handles sub-modules recursively. If the original module has sub-modules (like `json.encoder`), modshim will create corresponding merged versions of those sub-modules too. This ensures that imports within the original module continue to work correctly, maintaining consistency throughout the module hierarchy.

The system is thread-safe and handles complex scenarios like relative imports and module reloading. All of this happens without modifying any source code - the original modules remain untouched on disk, making modshim a clean alternative to vendoring code.

## Creating Enhancement Packages

It is possible to use modshim to create packages which automatically replace themselves with a shimmed version of their target.

This is possible because the name of the overlay package as the mount point for the merged module, and it is possible to automatically apply the shim when a module is imported. The result of this is an enhancement package which can be imported and used without the need to manually set up the shim.

To use our `datetime` example from above, if we create a new module called `datetime_mod.py` as follows:

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

# Apply the shim at import time
shim(lower="datetime")
# - The `upper` parameter defaults to the calling module, so will be `datetime_mod`
# - The `mount` parameter defaults to f`{upper}`, so will be `datetime_mod`
```

We can then import this module and use the modifications

```python
>>> from datetime_mod import datetime
>> datetime(9999, 1, 6).is_weekend
True
```

## Why Not Vendor?

Unlike vendoring (copying) code:
- No need to maintain copies of dependencies
- Easier updates when upstream changes
- Cleaner separation between original and custom code
- More maintainable and testable enhancement path
