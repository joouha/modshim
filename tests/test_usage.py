"""Tests for modshim usage patterns and edge cases."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Callable

import pytest

from modshim import shim


class _TestModuleLoader(Loader):
    def __init__(self, module: ModuleType) -> None:
        self.module = module

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        return self.module

    def exec_module(self, module: ModuleType) -> None:
        pass


class _TestModule(ModuleType):
    """Test module type with proper typing."""

    def __init__(self, name: str, doc: str = "") -> None:
        super().__init__(name, doc)
        self.__spec__ = ModuleSpec(name, _TestModuleLoader(self))

    get_count: Callable[[], int]


def test_multiple_registrations() -> None:
    """Test behavior when registering the same module multiple times."""
    # First registration
    shim(lower="json", upper="tests.examples.json_single_quotes", mount="json_multiple")
    import json_multiple

    result1 = json_multiple.dumps({"test": "value"})
    assert result1 == "{'test': 'value'}"

    # Second registration with same names
    shim(lower="json", upper="tests.examples.json_single_quotes", mount="json_multiple")
    result2 = json_multiple.dumps({"test": "value"})
    assert result2 == "{'test': 'value'}"

    # Third registration with same module but different name
    shim(
        lower="json",
        upper="tests.examples.json_single_quotes",
        mount="json_multiple_other",
    )
    import json_multiple_other

    result3 = json_multiple_other.dumps({"test": "value"})
    assert result3 == "{'test': 'value'}"


def test_concurrent_shims() -> None:
    """Test that multiple threads can safely create and use shims."""

    def create_and_use_shim(i: int) -> str:
        # Create unique module names for this thread
        upper = "tests.examples.json_single_quotes"
        lower = "json"
        mount = f"json_shim_{i}"

        shim(lower="json", upper="tests.examples.json_single_quotes", mount=mount)

        # Import and use the module
        module = __import__(mount)
        result = module.dumps({"test": "value"})
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


def test_concurrent_access() -> None:
    """Test that multiple threads can safely access the same shim."""
    # Create a single shim first
    shim(
        lower="json",
        upper="tests.examples.json_single_quotes",
        mount="json_shim_shared",
    )
    import json_shim_shared

    def use_shim() -> str:
        result = json_shim_shared.dumps({"test": "value"})
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


def test_nested_module_imports() -> None:
    """Test that nested/submodule imports work correctly."""
    # Create a shim that includes submodules
    shim(upper="tests.examples.urllib_punycode", lower="urllib", mount="urllib_nested")

    # Try importing various submodules
    from urllib_nested import parse  # type: ignore [reportMissingImports]
    from urllib_nested.parse import urlparse  # type: ignore [reportMissingImports]

    # Verify both import styles work
    url = "https://xn--bcher-kva.example.com/path"
    assert urlparse(url).netloc == "bücher.example.com"
    assert parse.urlparse(url).netloc == "bücher.example.com"


def test_error_handling() -> None:
    """Test error cases and edge conditions."""
    # Test with invalid lower module
    with pytest.raises(ImportError):
        shim(
            lower="nonexistent",
            upper="tests.examples.json_single_quotes",
            mount="json_error",
        )

    # Test with invalid module names
    with pytest.raises(ValueError, match="Upper module name cannot be empty"):
        shim(lower="json", upper="", mount="json_error")

    # Test with empty lower module name
    with pytest.raises(ValueError, match="Lower module name cannot be empty"):
        shim(lower="", upper="tests.examples.json_single_quotes", mount="json_error")


def test_attribute_access() -> None:
    """Test various attribute access patterns on shimmed modules."""
    shim(lower="json", upper="tests.examples.json_single_quotes", mount="json_attrs")
    import json_attrs

    # Test accessing non-existent attribute
    with pytest.raises(AttributeError):
        _ = json_attrs.nonexistent_attribute

    # Test accessing dunder attributes
    assert hasattr(json_attrs, "__name__")
    assert json_attrs.__name__ == "json_attrs"

    # Test dir() functionality
    attrs = dir(json_attrs)
    assert "dumps" in attrs
    assert "__name__" in attrs


def test_module_reload() -> None:
    """Test behavior when reloading shimmed modules."""
    import importlib
    import sys

    # Create in-memory modules with counters
    upper_counter = 0
    lower_counter = 0

    # Create underlay module
    lower = _TestModule("test_lower")

    def get_lower_count() -> int:
        nonlocal lower_counter
        lower_counter += 1
        return lower_counter

    lower.get_count = get_lower_count
    sys.modules["test_lower"] = lower

    # Create overlay module
    upper = _TestModule("test_upper")

    def get_upper_count() -> int:
        nonlocal upper_counter
        upper_counter += 1
        return upper_counter

    upper.get_count = get_upper_count
    # Create a spec for the upper module
    sys.modules["test_upper"] = upper

    # Create merged module
    merged = shim(upper="test_upper", lower="test_lower", mount="test_merged")

    # Initial counts should be 1
    assert merged.get_count() == 1  # Gets upper's count

    # Reload the module
    reloaded = importlib.reload(merged)

    # Verify both modules were re-executed
    assert reloaded is merged  # Same module object
    assert merged.get_count() == 2  # Count increased after reload


def test_package_paths() -> None:
    """Test that __path__ and package attributes are handled correctly."""
    merged = shim(
        upper="tests.examples.pathlib_is_empty", lower="pathlib", mount="pathlib_paths"
    )

    # Verify package attributes are set correctly
    assert hasattr(merged, "__path__")
    assert merged.__package__ == "pathlib_paths"

    # Test importing from package
    from pathlib_paths import Path  # type: ignore [reportMissingImports]

    assert hasattr(Path, "is_empty")


def test_context_preservation() -> None:
    """Test that module context (__file__, __package__, etc.) is preserved."""
    merged = shim(
        upper="tests.examples.json_single_quotes", lower="json", mount="json_context"
    )

    # Verify important context attributes
    assert hasattr(merged, "__file__")
    assert hasattr(merged, "__package__")
    assert hasattr(merged, "__spec__")

    # Verify they contain sensible values
    assert merged.__package__ == "json_context"
    assert merged.__spec__ is not None
