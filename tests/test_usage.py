"""Tests for modshim usage patterns and edge cases."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from modshim import shim


def test_multiple_registrations() -> None:
    """Test behavior when registering the same module multiple times."""
    # First registration
    shim(lower="json", upper="tests.examples.json_single_quotes", mount="json_multiple")
    import json_multiple  # type: ignore [reportMissingImports]

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
    import json_multiple_other  # type: ignore [reportMissingImports]

    result3 = json_multiple_other.dumps({"test": "value"})
    assert result3 == "{'test': 'value'}"


def test_concurrent_shims() -> None:
    """Test that multiple threads can safely create and use shims."""

    def create_and_use_shim(i: int) -> str:
        # Create unique module names for this thread
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
    import json_shim_shared  # type: ignore [reportMissingImports]

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


def test_attribute_access() -> None:
    """Test various attribute access patterns on shimmed modules."""
    shim(lower="json", upper="tests.examples.json_single_quotes", mount="json_attrs")
    import json_attrs  # type: ignore [reportMissingImports]

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

    # Create a shim
    shim(lower="json", upper="tests.examples.json_single_quotes", mount="json_reload")
    import json_reload  # type: ignore [reportMissingImports]

    # Test initial behavior
    initial_result = json_reload.dumps({"test": "value"})
    assert initial_result == "{'test': 'value'}"

    # Store a reference to the original module
    original_module_id = id(json_reload)

    # Reload the module
    reloaded = importlib.reload(json_reload)

    # Test that functionality is preserved after reload
    reload_result = reloaded.dumps({"test": "value"})
    assert reload_result == "{'test': 'value'}"

    # Verify it's the same module object (identity preserved)
    assert id(reloaded) == original_module_id
    assert reloaded is json_reload

    # Verify it's still accessible through normal import
    import json_reload as jr_again  # type: ignore [reportMissingImports]

    assert jr_again is json_reload


def test_package_paths() -> None:
    """Test that __path__ and package attributes are handled correctly."""
    shim(
        upper="tests.examples.textwrap_prefix",
        lower="textwrap",
        mount="textwrap_paths",
    )
    import textwrap_paths as merged  # type: ignore [reportMissingImports]

    # Verify package attributes are set correctly because the upper module is a package.
    assert hasattr(merged, "__path__")
    assert merged.__package__ == "textwrap_paths"

    # Test importing from package
    from textwrap_paths import TextWrapper  # type: ignore [reportMissingImports]  # noqa: F401, I001


def test_nonexistent_modules() -> None:
    """Test that ImportError is raised when neither upper nor lower module exists."""
    # Create a shim with non-existent modules
    shim(
        lower="nonexistent_lower", upper="nonexistent_upper", mount="nonexistent_mount"
    )

    # Attempt to import the non-existent module
    with pytest.raises(ImportError):
        import nonexistent_mount as nonexistent_mount  # type: ignore [reportMissingImports]

    # Also test using __import__
    with pytest.raises(ImportError):
        __import__("nonexistent_mount")


def test_import_error_on_nonexistent_submodule() -> None:
    """Test that ImportError is raised when importing a non-existent submodule."""
    # Create a shim with a known module
    shim(
        lower="json",
        upper="tests.examples.json_single_quotes",
        mount="json_import_error",
    )

    # Attempt to import a non-existent submodule
    with pytest.raises(ImportError):
        from json_import_error import (  # type: ignore [reportMissingImports]
            non_existent_submodule as non_existent_submodule,
        )

    # Also test using __import__
    with pytest.raises(ImportError):
        __import__("json_import_error.non_existent_submodule")


def test_context_preservation() -> None:
    """Test that module context (__file__, __package__, etc.) is preserved."""
    shim(upper="tests.examples.json_single_quotes", lower="json", mount="json_context")
    import json_context as merged  # type: ignore [reportMissingImports]

    # Verify important context attributes
    assert hasattr(merged, "__file__")
    assert hasattr(merged, "__package__")
    assert hasattr(merged, "__spec__")

    # Verify they contain sensible values
    assert merged.__package__ == "json_context"
    assert merged.__spec__ is not None
