import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from modshim import shim


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
    from urllib_nested.parse import urlparse
    from urllib_nested import parse
    
    # Verify both import styles work
    url = "https://xn--bcher-kva.example.com/path"
    assert urlparse(url).netloc == "bücher.example.com"
    assert parse.urlparse(url).netloc == "bücher.example.com"


def test_error_handling():
    """Test error cases and edge conditions."""
    # Test with non-existent upper module
    with pytest.raises(ImportError):
        shim("nonexistent.module", "json", "json_error")
    
    # Test with invalid lower module
    with pytest.raises(ImportError):
        shim("tests.examples.json_single_quotes", "nonexistent", "json_error")
        
    # Test with invalid module names
    with pytest.raises(ValueError):
        shim("", "json", "json_error")


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
    
    merged = shim("tests.examples.json_single_quotes", "json", "json_reload")
    
    # Store original state
    original_id = id(merged)
    
    # Reload the module
    reloaded = importlib.reload(merged)
    
    # Verify behavior
    assert id(reloaded) != original_id
    assert reloaded.dumps({"test": "value"}) == "{'test': 'value'}"


def test_package_paths():
    """Test that __path__ and package attributes are handled correctly."""
    merged = shim("tests.examples.pathlib_is_empty", "pathlib", "pathlib_paths")
    
    # Verify package attributes are set correctly
    assert hasattr(merged, "__path__")
    assert merged.__package__ == "pathlib_paths"
    
    # Test importing from package
    from pathlib_paths import Path
    assert hasattr(Path, "is_empty")


def test_import_hook_cleanup():
    """Test that import hooks are properly cleaned up."""
    import sys
    
    # Count initial meta_path entries
    initial_meta_path_count = len(sys.meta_path)
    
    # Create and remove several shims
    shim1 = shim("tests.examples.json_single_quotes", "json", "json_cleanup1")
    shim2 = shim("tests.examples.json_single_quotes", "json", "json_cleanup2")
    
    # Force cleanup
    del shim1
    del shim2
    
    # Verify meta_path is cleaned up
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
