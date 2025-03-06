import threading
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from modshim import shim

def test_concurrent_shims():
    """Test that multiple threads can safely create and use shims."""
    def create_and_use_shim(i):
        # Create unique module names for this thread
        upper = f"tests.examples.json_single_quotes"
        lower = "json"
        as_name = f"json_shim_{i}"
        
        # Create shim
        merged = shim(upper, lower, as_name)
        
        # Use the shim to verify it works
        result = merged.dumps({"test": "value"})
        assert isinstance(result, str)
        assert "{'test': 'value'}" == result
        
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

def test_concurrent_access():
    """Test that multiple threads can safely access the same shim."""
    # Create a single shim first
    merged = shim("tests.examples.json_single_quotes", "json", "json_shim_shared")
    
    def use_shim():
        result = merged.dumps({"test": "value"})
        assert isinstance(result, str)
        assert "{'test': 'value'}" == result
        time.sleep(0.001)  # Add delay to increase chance of race conditions
        return result
    
    # Access the same shim from multiple threads
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(use_shim) for _ in range(10)]
        results = [f.result() for f in futures]
        
        assert len(results) == 10
        assert all(r == "{'test': 'value'}" for r in results)
