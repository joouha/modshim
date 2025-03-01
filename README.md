# modshim

A Python module overlay system that lets you enhance existing modules without modifying their source code.

## What is modshim?

modshim is a Python import hook that allows you to "overlay" your own implementations on top of existing Python modules - whether they're from the standard library or third-party packages. This enables you to:

- Add new methods to existing classes
- Override existing functions with enhanced versions
- Add new functionality while preserving the original behavior
- Use alternative implementations without modifying upstream source code

## Installation

```bash
pip install modshim
```

## How it Works

modshim uses Python's import hook system to intercept imports of specified modules. When you import a module that has an overlay:

1. modshim's import hook intercepts the import
2. It loads both the original module and your overlay
3. It combines them into a single module
4. The combined module is returned to the importer, replacing your overlay module

This happens transparently at runtime, with no modification to the original source code.

## Use cases

modshim is particularly useful when you need to:

- **Add missing functionality**: Add methods that should exist but don't, like `Path.is_empty()` or `datetime.is_weekend()`
- **Fix behavior**: Override functions to fix bugs or add features without forking the original package
- **Enhance compatibility**: Add compatibility layers or shims for different Python versions or platforms
- **Add validation**: Wrap existing APIs with input validation, type checking, or schema enforcement
- **Customize output**: Modify output formats (like JSON serialization) without changing client code
- **Add instrumentation**: Insert logging, metrics, or debugging capabilities transparently
- **Test difficult scenarios**: Simulate conditions like time dilation or fixed random seeds in tests
- **Maintain backwards compatibility**: Add new features while preserving existing interfaces
- **Prototype improvements**: Try out enhancements before submitting them upstream

## Example Usage

Here's a simple example that adds an `is_empty()` method to `pathlib.Path`:

```python
# my_package.pathlib
from pathlib import Path as OriginalPath
from modshim import overlay

overlay = overlay("pathlib")

class Path(OriginalPath):
    """Enhanced Path with additional utilities."""
    
    def is_empty(self) -> bool:
        """Return True if directory is empty or file has zero size."""
        if not self.exists():
            raise FileNotFoundError(f"Path does not exist: {self}")
        if self.is_file():
            return self.stat().st_size == 0
        if self.is_dir():
            return not any(self.iterdir())
        return False
```

Now anywhere you import `Path`, you'll get the enhanced version with `is_empty()`:

```python
from my_package.pathlib import Path

path = Path("empty.txt")
path.touch()
assert path.is_empty()  # True
```

## More Examples

Check out the [examples directory](tests/examples) for more real-world use cases:

- Making `json` use single quotes
- Adding weekend detection to datetime
- Adding schema validation to csv
- Adding time dilation to time
- Adding punycode parsing to urllib
- Adding fixed seed support to random

## Best Practices
- Keep overlays focused and minimal
- Maintain backwards compatibility
- Document what you're changing and why
- Consider submitting improvements upstream
- Follow the original module's conventions

## How is this different from vendoring?

When you vendor a package, you:
1. Copy the entire source code into your project
2. Modify the code directly
3. Maintain your own fork
4. Need to merge upstream changes manually

With modshim, you:
1. Keep the original package installed normally
2. Create overlay modules that only contain your changes
3. Let modshim combine your changes with the original at runtime
4. Get upstream updates automatically

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
