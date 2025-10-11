# modshim

A Python library for enhancing existing modules without modifying their source code - a clean alternative to vendoring and monkey-patching.

## Overview

`modshim` allows you to overlay custom functionality onto existing Python modules while preserving their original behavior. This is particularly useful when you need to:

- Fix bugs in third-party libraries without forking
- Modify behavior of existing functions
- Add new features or options to existing classes
- Test alternative implementations in an isolated way

It works by creating a new, "shimmed" module that combines the original code with your enhancements, without ever touching the original module.

## Installation

```bash
pip install modshim
```

## Usage

Suppose we want to enhance the standard library's `textwrap` module. Our goal is to add a `prefix` argument to `TextWrapper` to prepend a string to every wrapped line.

First, create a Python module containing your modifications. It should mirror the structure of the original `textwrap` module.

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
...     upper="prefixed_textwrap",  # Module with your modifications
...     lower="textwrap",           # Original module to enhance
...     mount="super_textwrap",     # Name for the new, merged module
... )
```

Now, you can import from `super_textwrap`. Notice how we can call the original `wrap()` convenience function, but pass our new `prefix` argument. This works because `modshim` ensures that the original `wrap` function now uses our enhanced `TextWrapper` class internally, demonstrating a deep integration of your changes.

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

This is done by calling `shim()` from within your package's code and using your own package's name as the `mount` point.

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

Now, anyone can use your enhanced version simply by importing your package. The original `wrap` function from `textwrap` is now available with the new `prefix` functionality.

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

## How It Works

`modshim` creates virtual merged modules by intercepting Python's import system. At its core, modshim works by installing a custom import finder (`ModShimFinder`) into `sys.meta_path`.

When you call `shim()`, it registers a mapping between three module names: the "lower" (original) module, the "upper" (enhancement) module, and the "mount" point (the name under which the combined module will be accessible).

When the mounted module is imported, the finder:

1. Locates both the lower and upper modules using Python's standard import machinery.
2. Creates a new virtual module at the mount point.
3. Executes the lower module's code first, establishing the base functionality.
4. Executes the upper module's code, which can override or extend the lower module's attributes.
5. Handles imports within these modules by rewriting their ASTs (Abstract Syntax Trees) to redirect internal references to the new mount point.

This AST transformation is key. It ensures that when code in either module imports from its own package (e.g., a relative import), those imports are redirected to the new, combined module. This maintains consistency and prevents circular import issues.

The system is thread-safe, handles sub-modules recursively, and supports bytecode caching for performance. All of this happens without modifying any source code on disk.


## Why Not Vendor?

Unlike vendoring (copying) third-party code into your project:
- No need to maintain copies of dependencies.
- It's easier to update the underlying library.
- It creates a cleaner separation between original and custom code.
- Your enhancement code is more maintainable and testable.
