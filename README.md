# modshim

A Python library for enhancing existing modules without modifying their source code - a clean alternative to forking, vendoring, and monkey-patching.

## Overview

`modshim` allows you to overlay custom functionality onto existing Python modules while preserving their original behavior. This is particularly useful when you need to:

- Fix bugs in third-party libraries without forking
- Modify the behavior of existing functions
- Add new features or options to existing classes
- Test alternative implementations in an isolated way

It works by creating a new, "shimmed" module that combines the original code with your enhancements, without modifying the original module.

## Installation

```bash
pip install modshim
```

## Usage

Suppose we want to enhance the standard library's `textwrap` module. Our goal is to add a `prefix` argument to `TextWrapper` to prepend a string to every wrapped line.

First, create a Python module containing your modifications. It should mirror the structure of the original `textwrap` module, redefining only the parts we want to modify. For classes like `TextWrapper`, this can be done by creating a subclass with the same name as the original class:

```python
# prefixed_textwrap.py

# Import the class you want to extend from the original module
from textwrap import TextWrapper as OriginalTextWrapper

# Sub-class to override and extend functionality
class TextWrapper(OriginalTextWrapper):
    """Enhanced TextWrapper that adds a prefix to each line."""

    def __init__(self, *args, prefix: str = "", **kwargs) -> None:
        self.prefix = prefix
        super().__init__(*args, **kwargs)

    def wrap(self, text: str) -> list[str]:
        """Wrap text and add prefix to each line."""
        original_lines = super().wrap(text)
        if not self.prefix:
            return original_lines
        return [f"{self.prefix}{line}" for line in original_lines]
```

Next, use `modshim` to mount your modifications over the original `textwrap` module, creating a new, combined module.

```python
>>> from modshim import shim
>>> shim(
...     lower="textwrap",           # Original module to enhance
...     upper="prefixed_textwrap",  # Module with your modifications
...     mount="super_textwrap",     # Name for the new, merged module
... )
```

Now, you can import from `super_textwrap`. Notice how we can call the original `wrap()` convenience function, but pass our new `prefix` argument. This works because our modifications are overlaid on the original `textwrap` module, so the merged `super_textwrap` module uses our enhanced `TextWrapper` class inside the `wrap` function instead of the original.

```python
>>> from super_textwrap import wrap
>>>
>>> text = "This is a long sentence that will be wrapped into multiple lines."
>>> for line in wrap(text, width=30, prefix="> "):
...     print(line)
...
> This is a long sentence that
> will be wrapped into
> multiple lines.
```

Crucially, the original `textwrap` module remains completely unchanged. This is the key advantage over monkey-patching.

```python
# The original module is untouched
>>> from textwrap import wrap
>>>
# It works as it always did, without the 'prefix' argument
>>> text = "This is a long sentence that will be wrapped into multiple lines."
>>> for line in wrap(text, width=30):
...     print(line)
...
This is a long sentence that
will be wrapped into
multiple lines.

# Trying to use our new feature with the original module will fail, as expected
>>> wrap(text, width=30, prefix="> ")
Traceback (most recent call last):
  ...
TypeError: TextWrapper.__init__() got an unexpected keyword argument 'prefix'
```

## Creating Enhancement Packages

You can create packages that automatically apply a shim to another module, making your enhancements available just by importing your package.

This is done by calling `shim()` from within your package's code and using your own package's name as the `mount` point, so your package gets "replaced" with new merged module.

To adapt our `textwrap` example, we could create a `super_textwrap.py` file like this:

```python
# super_textwrap.py
from textwrap import TextWrapper as OriginalTextWrapper
from modshim import shim

# Define your enhancements as before
class TextWrapper(OriginalTextWrapper):
    """Enhanced TextWrapper that adds a prefix to each line."""

    def __init__(self, *args, prefix: str = "", **kwargs) -> None:
        self.prefix = prefix
        super().__init__(*args, **kwargs)

    def wrap(self, text: str) -> list[str]:
        original_lines = super().wrap(text)
        if not self.prefix:
            return original_lines
        return [f"{self.prefix}{line}" for line in original_lines]

# Apply the shim at import time. This replaces the 'super_textwrap'
# module in sys.modules with the new, combined module.
shim(lower="textwrap")
# - The `upper` parameter defaults to the calling module ('super_textwrap').
# - The `mount` parameter defaults to `upper`, so it is also 'super_textwrap'.
```

Now, anyone can use your enhanced version simply by importing your package:

```python
>>> from super_textwrap import wrap
>>>
>>> text = "This is a long sentence that will be wrapped into multiple lines."
>>> for line in wrap(text, width=30, prefix="* "):
...     print(line)
...
* This is a long sentence that
* will be wrapped into
* multiple lines.
```

## Mounting Over the Original Module

In some cases, you may want your enhanced module to completely replace the original module name. This allows existing code to benefit from your enhancements without changing any import statements.

For example, suppose you want all imports of `textwrap` in your application to automatically use your enhanced version with the `prefix` feature. You can do this by setting the `mount` point to the same name as the `lower` module:

```python
# my_app/setup_enhancements.py
from modshim import shim

shim(
    lower="textwrap",
    upper="prefixed_textwrap",
    mount="textwrap",  # Mount over the original module name
)
```

After this `shim()` call executes, any subsequent imports of `textwrap` will use the combined module:

```python
# my_app/main.py
from my_app import setup_enhancements  # Apply the shim first

# Now the standard import gets our enhanced version!
from textwrap import wrap

text = "This is a long sentence that will be wrapped into multiple lines."
for line in wrap(text, width=30, prefix=">> "):
    print(line)
```

Output:
```
>> This is a long sentence that
>> will be wrapped into
>> multiple lines.
```

### Use Case: Transparent Bug Fixes

This pattern is particularly useful when you need to apply a bug fix or security patch to a library that is used throughout your codebase or by third-party dependencies. Instead of modifying every import statement, you can apply the fix once at application startup:

```python
# my_app/__init__.py
from modshim import shim

# Apply our fix to the json module globally
shim(lower="json", upper="json_fixes", mount="json")
```

Now all code—including third-party libraries—that imports `json` will use your patched version.

### Caution

Mounting over the original module affects all subsequent imports in your application, including those from third-party libraries. Use this pattern carefully and ensure your enhancements are fully backward-compatible with the original module's API.

## Advanced Example: Adding Configurable Retries to `requests`

Let's tackle a more complex, real-world scenario. We want to add a robust, configurable retry mechanism to `requests` for handling transient network issues or server errors. The standard way to do this in `requests` is by creating a `Session` object and mounting a custom `HTTPAdapter`.

With `modshim`, we can create an enhanced `Session` class that automatically conﬁgures retries, and then overlay it onto the original `requests` library. To do this correctly, our enhancement package (`requests_extra`) must mirror the structure of the original `requests` package.

### Step 1: Create the Enhancement Package

We'll create a package named `requests_extra` with two files.

**`requests_extra/__init__.py`**

This is the entry point to our package. It contains the magic `shim` call.

```python
# requests_extra/__init__.py

from modshim import shim

# This overlays our 'requests_extra' package on the original 'requests' package.
# Because 'mount' isn't specified, it defaults to our package name ('requests_extra').
# When a submodule like 'requests_extra.sessions' is imported, modshim will
# automatically merge it with the original 'requests.sessions'.
shim(lower="requests")
```

**`requests_extra/sessions.py`**

This file matches the location of the `Session` class in the original `requests` library (`requests/sessions.py`). Here, we define our enhanced `Session` with the new functionality, by subclassing the original `Session` implementation:

```python
# requests_extra/sessions.py

from requests.adapters import HTTPAdapter
# We will create a new version of `Session` by subclassing the original
from requests.sessions import Session as OriginalSession
from urllib3.util.retry import Retry


class Session(OriginalSession):
    """
    Enhanced Session that adds automatic, configurable retries via a mounted HTTPAdapter.

    Accepts new keyword arguments in its constructor:
    - retries (int): Total number of retries to allow.
    - backoff_factor (float): A factor to apply between retry attempts.
    - status_forcelist (iterable): A set of HTTP status codes to force a retry on.
    """

    def __init__(self, *args, **kwargs):
        # Extract our custom arguments before calling the parent constructor
        retries = kwargs.pop("retries", 3)
        backoff_factor = kwargs.pop("backoff_factor", 0.1)
        status_forcelist = kwargs.pop("status_forcelist", (500, 502, 503, 504))

        super().__init__(*args, **kwargs)

        # If retries are configured, create a retry strategy and mount it
        if retries > 0:
            retry_strategy = Retry(
                total=retries,
                backoff_factor=backoff_factor,
                status_forcelist=status_forcelist,
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.mount("https://", adapter)
            self.mount("http://", adapter)
```

### Step 2: Use the Enhanced `requests`

Because our enhanced Session class now enables retries by default, we don't even need to instantiate it directly. `modshim`'s AST rewriting ensures that internal references within the requests module are updated. This means convenience functions like `requests.get()` will automatically use our enhanced `Session` class:

```python
# Configure logging to show the retry attempts
import logging
logger = logging.getLogger("urllib3.util.retry")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())

# Use our enhanced module
import requests_extra
try:
    response = requests_extra.get("https://httpbin.org/status/503")
except Exception as e:
    print(e)
```

When you run this code, you will see urllib3's log messages showing the retries in action, followed by the final caught exception:

```
Incremented Retry for (url='/status/503'): Retry(total=2, connect=None, read=None, redirect=None, status=None)
Incremented Retry for (url='/status/503'): Retry(total=1, connect=None, read=None, redirect=None, status=None)
Incremented Retry for (url='/status/503'): Retry(total=0, connect=None, read=None, redirect=None, status=None)
HTTPSConnectionPool(host='httpbin.org', port=443): Max retries exceeded with url: /status/503 (Caused by ResponseError('too many 503 error responses'))
...
```

### Benefits of this Approach

- **Internal Reference Rewriting**: This example demonstrates `modshim`'s most powerful feature. By replacing `requests.sessions.Session`, we automatically upgraded top-level functions like `requests.get()` because their internal references to Session are redirected to our new class.
- **Preservation of the Original Module**: The original `requests` package is not altered. Code in other parts of an application that imports `requests` directly will continue to use the original `Session` object without any retry logic, preventing unintended side-effects.

## How It Works

`modshim` creates virtual merged modules by extending Python's import system. At its core, modshim works by installing a custom import finder (`ModShimFinder`) into `sys.meta_path`.

When you call `shim()`, it registers a mapping between three module names: the "lower" (original) module, the "upper" (enhancement) module, and the "mount" point (the name under which the combined module will be accessible).

When the mounted module is imported, the finder:

1. Locates both the lower and upper modules using Python's standard import machinery.
2. Creates a module spec for a new virtual module at the mount point.
3. Executes the lower module's code first, establishing the base functionality. A temporary "working" copy of this namespace is saved.
4. Executes the upper module's code, which can override or extend the lower module's attributes. The upper module can access the original lower module's attributes through the working copy.
5. Combines `__all__` from both modules if present.

### AST Rewriting

The key mechanism that makes this work is AST (Abstract Syntax Tree) rewriting. When loading each module's source code, `modshim` parses it and transforms import statements and module references:

- **Import statements** (`import X` and `from X import Y`) are rewritten to point to the mount point instead of the original package names.
- **Attribute access** (e.g., `urllib.response`) is also rewritten when it references the lower or upper module names.

For example, if you mount `requests_extra` over `requests` at mount point `requests_extra`:
- Code in `requests` that does `from requests.sessions import Session` gets rewritten to `from requests_extra.sessions import Session`.
- Code in `requests_extra` that does `from requests import Response` gets rewritten to `from requests_extra import Response`.

This ensures that when code in either module imports from its own package, those imports resolve to the new, combined module. This maintains consistency and allows the upper module's enhancements to be used throughout.

### Working Module Mechanism

When your upper module imports from the lower module (e.g., `from textwrap import TextWrapper as OriginalTextWrapper`), `modshim` needs special handling to provide the *original* class rather than creating a circular reference. It does this by:

1. Executing the lower module's code and capturing its namespace.
2. Creating a temporary "working" module (e.g., `_working_textwrap`) containing this namespace.
3. Rewriting the upper module's imports to reference this working module when it imports from itself.

This allows your enhancement code to subclass or wrap the original implementations.

### Performance and Safety

The system is thread-safe, handles sub-modules recursively, and supports bytecode caching for performance. All of this happens without modifying any source code on disk.


## Why Not Monkey-Patch?

Monkey-patching involves altering a module or class at runtime. For example, you might replace `textwrap.TextWrapper` with your custom class.

```python
# The monkey-patching way
import textwrap
from my_enhancements import PrefixedTextWrapper

# This pollutes the global namespace and affects ALL code!
textwrap.TextWrapper = PrefixedTextWrapper
```

This approach has major drawbacks:
- **Global Pollution:** It alters the `textwrap` module for the entire application. Every part of your code, including third-party libraries, will now unknowingly use your modified version. This can lead to unpredictable behavior and hard-to-find bugs.
- **Fragility:** Patches can easily break when the underlying library is updated.
- **Poor Readability:** It's hard to track where modifications are applied and what version of a class or function is actually being used.

`modshim` avoids these problems by creating a **new, separate, and isolated module**. The original `textwrap` is never touched. You explicitly import from your mount point (`super_textwrap`) when you want the enhanced functionality. This provides clear, predictable, and maintainable code.


## Why Not Fork?

Forking a project means creating your own copy of its entire codebase. While this gives you total control, it comes with significant downsides:

- **Maintenance Overhead:** You become the maintainer of the forked library. When the original project releases updates, bug fixes, or security patches, you have to manually merge them into your fork. This can be time-consuming and complex.
- **Divergence:** Over time, your fork can drift away from the original, making it increasingly difficult to incorporate upstream changes.
- **Dependency Complexity:** Your project now depends on your custom fork, not the official version. This complicates deployment and can be confusing for other developers who might not realize they're using a non-standard version of the library.
- **Bridging Contribution Gaps:** Contributing changes upstream is ideal, but open-source maintainers may be slow or reluctant to merge them due to differing priorities, project vision, or contribution backlogs. Forking in response creates a permanent schism and a significant maintenance burden for what might be a small change.

`modshim` offers a more lightweight and strategic alternative. It allows you to apply necessary changes immediately for your own project's needs without waiting for upstream review. Your enhancements live in a small, separate package that depends on the *official* upstream library. This keeps your changes cleanly isolated, eliminates the maintenance burden of a full fork, and makes it easy to continue tracking upstream updates. If you still intend to contribute your changes, `modshim` keeps your patch separate and ready for a future pull request.


## Why Not Vendor?

Unlike vendoring (copying) third-party code into your project:
- No need to maintain copies of dependencies.
- It's easier to update the underlying library.
- It creates a cleaner separation between original and custom code.
- Your enhancement code is more maintainable and testable.
