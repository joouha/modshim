import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from modshim import MergedModuleFinder, shim


def test_multiple_registrations():
    """Test behavior when registering the same module multiple times."""
    # First registration
    shim1 = shim("tests.examples.json_single_quotes", "json", "json_multiple")
    result1 = shim1.dumps({"test": "value"})
    assert result1 == "{'test': 'value'}"

    # Second registration with same names
    shim2 = shim("tests.examples.json_single_quotes", "json", "json_multiple")
    result2 = shim2.dumps({"test": "value"})
    assert result2 == "{'test': 'value'}"

    # Verify both references point to same module
    assert shim1 is shim2

    # Third registration with same module but different name
    shim3 = shim("tests.examples.json_single_quotes", "json", "json_multiple_other")
    result3 = shim3.dumps({"test": "value"})
    assert result3 == "{'test': 'value'}"

    # Verify this is a different module
    assert shim3 is not shim1


def test_concurrent_shims():
    """Test that multiple threads can safely create and use shims."""

    def create_and_use_shim(i):
        # Create unique module names for this thread
        upper = "tests.examples.json_single_quotes"
        lower = "json"
        as_name = f"json_shim_{i}"

        # Create shim
        merged = shim(upper, lower, as_name)

        # Use the shim to verify it works
        result = merged.dumps({"test": "value"})
        assert isinstance(result, str)
        assert result == "{'test': 'value'}"

        # Add some random delays to increase chance of race conditions
        time.sleep(0.001)

        return result

    # Run multiple shim creations concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_and_use_shim, i) for i in range(10)]

        # Verify all operations completed successfully
        results = [f.result() for f in futures]
        assert len(results) == 10
        assert all(r == "{'test': 'value'}" for r in results)


def test_concurrent_access():
    """Test that multiple threads can safely access the same shim."""
    # Create a single shim first
    merged = shim("tests.examples.json_single_quotes", "json", "json_shim_shared")

    def use_shim():
        result = merged.dumps({"test": "value"})
        assert isinstance(result, str)
        assert result == "{'test': 'value'}"
        time.sleep(0.001)  # Add delay to increase chance of race conditions
        return result

    # Access the same shim from multiple threads
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(use_shim) for _ in range(10)]
        results = [f.result() for f in futures]

        assert len(results) == 10
        assert all(r == "{'test': 'value'}" for r in results)


def test_nested_module_imports():
    """Test that nested/submodule imports work correctly."""
    # Create a shim that includes submodules
    shim("tests.examples.urllib_punycode", "urllib", "urllib_nested")

    # Try importing various submodules
    from urllib_nested import parse
    from urllib_nested.parse import urlparse

    # Verify both import styles work
    url = "https://xn--bcher-kva.example.com/path"
    assert urlparse(url).netloc == "bücher.example.com"
    assert parse.urlparse(url).netloc == "bücher.example.com"


def test_error_handling():
    """Test error cases and edge conditions."""
    # Test with invalid lower module
    with pytest.raises(ImportError):
        shim("tests.examples.json_single_quotes", "nonexistent", "json_error")

    # Test with invalid module names
    with pytest.raises(ValueError):
        shim("", "json", "json_error")

    # Test with empty lower module name
    with pytest.raises(ValueError):
        shim("tests.examples.json_single_quotes", "", "json_error")


def test_attribute_access():
    """Test various attribute access patterns on shimmed modules."""
    merged = shim("tests.examples.json_single_quotes", "json", "json_attrs")

    # Test accessing non-existent attribute
    with pytest.raises(AttributeError):
        merged.nonexistent_attribute

    # Test accessing dunder attributes
    assert hasattr(merged, "__name__")
    assert merged.__name__ == "json_attrs"

    # Test dir() functionality
    attrs = dir(merged)
    assert "dumps" in attrs
    assert "__name__" in attrs


def test_module_reload():
    """Test behavior when reloading shimmed modules."""
    import importlib
    import sys
    from importlib.machinery import ModuleSpec
    from types import ModuleType

    # Create in-memory modules with counters
    upper_counter = 0
    lower_counter = 0

    # Create underlay module
    lower = ModuleType("test_lower")

    def get_lower_count():
        nonlocal lower_counter
        lower_counter += 1
        return lower_counter

    lower.get_count = get_lower_count
    # Create a spec for the lower module
    lower.__spec__ = ModuleSpec("test_lower", None)
    sys.modules["test_lower"] = lower

    # Create overlay module
    upper = ModuleType("test_upper")

    def get_upper_count():
        nonlocal upper_counter
        upper_counter += 1
        return upper_counter

    upper.get_count = get_upper_count
    # Create a spec for the upper module
    upper.__spec__ = ModuleSpec("test_upper", None)
    sys.modules["test_upper"] = upper

    # Create merged module
    merged = shim("test_upper", "test_lower", "test_merged")

    # Initial counts should be 1
    assert merged.get_count() == 1  # Gets upper's count

    # Reload the module
    reloaded = importlib.reload(merged)

    # Verify both modules were re-executed
    assert reloaded is merged  # Same module object
    assert merged.get_count() == 2  # Count increased after reload

    # Clean up
    del sys.modules["test_upper"]
    del sys.modules["test_lower"]
    del sys.modules["test_merged"]


def test_package_paths():
    """Test that __path__ and package attributes are handled correctly."""
    merged = shim("tests.examples.pathlib_is_empty", "pathlib", "pathlib_paths")

    # Verify package attributes are set correctly
    assert hasattr(merged, "__path__")
    assert merged.__package__ == "pathlib_paths"

    # Test importing from package
    from pathlib_paths import Path

    assert hasattr(Path, "is_empty")


def test_overlay_chaining():
    """Test that overlaying an already overlayed module works correctly."""
    # First create a shim with single quotes
    json_quotes = shim("tests.examples.json_single_quotes", "json", "json_quotes")
    
    # Then create a shim that overlays the single quotes version with metadata
    json_both = shim("tests.examples.json_metadata", "json_quotes", "json_both")
    
    # Test data
    data = {"name": "test"}
    
    # Verify original json behavior
    import json
    assert json.dumps(data) == '{"name": "test"}'
    
    # Verify single quotes overlay
    assert json_quotes.dumps(data) == "{'name': 'test'}"
    
    # Verify combined overlay has both single quotes and metadata
    result = json_both.dumps(data)
    assert "{'name': 'test'" in result  # Single quotes from first overlay
    assert "'_metadata': {'timestamp': '2024-01-01'}" in result  # Metadata from second overlay
    
    # Verify the exact combined output
    assert result == "{'name': 'test', '_metadata': {'timestamp': '2024-01-01'}}"
    
    # Verify original modules remain unaffected
    assert json.dumps(data) == '{"name": "test"}'
    assert json_quotes.dumps(data) == "{'name': 'test'}"


def test_import_hook_cleanup():
    """Test that import hooks are properly cleaned up."""
    import gc
    import sys

    # Count initial meta_path entries
    initial_meta_path_count = len(sys.meta_path)
    initial_finders = [f for f in sys.meta_path if isinstance(f, MergedModuleFinder)]

    # Create and remove several shims
    shim1 = shim("tests.examples.json_single_quotes", "json", "json_cleanup1")
    shim2 = shim("tests.examples.json_single_quotes", "json", "json_cleanup2")

    # Force cleanup explicitly rather than relying on __del__
    shim1._finder.cleanup()
    shim2._finder.cleanup()

    # Clean up modules
    if "json_cleanup1" in sys.modules:
        del sys.modules["json_cleanup1"]
    if "json_cleanup2" in sys.modules:
        del sys.modules["json_cleanup2"]

    # Force garbage collection
    gc.collect()

    # Verify meta_path is cleaned up
    current_finders = [f for f in sys.meta_path if isinstance(f, MergedModuleFinder)]
    assert len(current_finders) == len(initial_finders)
    assert len(sys.meta_path) == initial_meta_path_count


def test_context_preservation():
    """Test that module context (__file__, __package__, etc.) is preserved."""
    merged = shim("tests.examples.json_single_quotes", "json", "json_context")

    # Verify important context attributes
    assert hasattr(merged, "__file__")
    assert hasattr(merged, "__package__")
    assert hasattr(merged, "__spec__")

    # Verify they contain sensible values
    assert merged.__package__ == "json_context"
    assert merged.__spec__ is not None
