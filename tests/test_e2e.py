"""Test some realistic patching of stdlib modules."""

from modshim import register

# Register overlays
register(lower="csv", upper="upper.csv_schema", merge="csv_schema")
register(lower="datetime", upper="upper.datetime_weekend", merge="datetime_weekend")
register(lower="json", upper="upper.json_metadata", merge="json_metadata")
register(lower="json", upper="upper.json_single_quotes", merge="json_single_quotes")
register(lower="pathlib", upper="upper.pathlib_is_empty", merge="pathlib_is_empty")
register(lower="random", upper="upper.random_fixed", merge="random_fixed")
register(lower="time", upper="upper.time_dilation", merge="time_dilation")
register(lower="urllib", upper="upper.urllib_punycode", merge="urllib_punycode")


def test_json_single_quotes_override() -> None:
    """Test that json strings are encoded with single quotes while preserving original behavior."""
    import json

    import json_single_quotes as json_test

    data = {"name": "test", "list": ["a", "b"]}
    result = json_test.dumps(data)
    original_result = json.dumps(data)

    # Our version uses single quotes
    assert result == "{'name': 'test', 'list': ['a', 'b']}"
    # Original json module should still use double quotes
    assert original_result == '{"name": "test", "list": ["a", "b"]}'


def test_json_metadata_override() -> None:
    """Test that json.dumps can be overridden while preserving original behavior."""
    import json

    from json_metadata import dumps

    data = {"name": "test"}
    result = dumps(data)

    # Original json should be unaffected
    original_result = json.dumps(data)

    assert json.loads(result) == {
        "name": "test",
        "_metadata": {"timestamp": "2024-01-01"},
    }
    assert json.loads(original_result) == {"name": "test"}


def test_datetime_weekend_override() -> None:
    """Test that datetime can be extended with new properties while preserving original."""
    from datetime import datetime

    from datetime_weekend import datetime as datetime_weekend

    # Test custom property
    dt = datetime_weekend(2024, 1, 6)  # Saturday
    assert dt.is_weekend is True

    dt = datetime_weekend(2024, 1, 3)  # Wednesday
    assert dt.is_weekend is False

    # Test overridden class method
    assert datetime_weekend.now().is_weekend is True

    # Original datetime should be unaffected
    assert isinstance(datetime.now(), datetime)
    assert not hasattr(datetime.now(), "is_weekend")


def test_random_fixed_seed() -> None:
    """Test that random module can be configured with a fixed seed."""
    import random

    from random_fixed import Random

    # Set a fixed seed
    Random.set_fixed_seed(42)

    # Create two generators
    gen1 = Random()
    gen2 = Random()

    # Both should generate the same sequence
    assert gen1.random() == gen2.random()
    assert gen1.random() == gen2.random()

    # Clear fixed seed
    Random.set_fixed_seed(None)

    # Now they should (probably!) generate different sequences
    gen3 = Random()
    gen4 = Random()
    assert gen3.random() != gen4.random()

    # Original random should be unaffected
    assert isinstance(random.Random(), random.Random)  # noqa: S311


def test_pathlib_is_empty() -> None:
    """Test enhanced pathlib with is_empty method."""
    import pathlib
    import tempfile
    from pathlib import Path

    from pathlib_is_empty import Path as PathTest

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files and directories
        empty_dir = PathTest(tmpdir) / "empty_dir"
        empty_dir.mkdir()

        nonempty_dir = PathTest(tmpdir) / "nonempty_dir"
        nonempty_dir.mkdir()
        (nonempty_dir / "file.txt").touch()

        empty_file = PathTest(tmpdir) / "empty.txt"
        empty_file.touch()

        nonempty_file = PathTest(tmpdir) / "nonempty.txt"
        nonempty_file.write_text("content")

        # Test is_empty() method
        assert empty_dir.is_empty() is True
        assert nonempty_dir.is_empty() is False
        assert empty_file.is_empty() is True
        assert nonempty_file.is_empty() is False

        # Original Path should be unaffected
        assert not hasattr(Path(tmpdir), "is_empty")
        assert isinstance(pathlib.Path(tmpdir), pathlib.Path)


def test_time_dilation() -> None:
    """Test that time can be dilated while preserving original behavior."""
    import time as time_original

    from time_dilation import set_dilation, sleep, time

    # Set time to run at 2x speed
    set_dilation(2.0)

    # Record start times
    start_dilated = time()
    start_original = time_original.time()

    # Sleep for 0.1 dilated seconds (should actually sleep for 0.05 real seconds)
    sleep(0.1)

    # Check elapsed times
    elapsed_dilated = time() - start_dilated
    elapsed_original = time_original.time() - start_original

    # Dilated time should be ~0.1 seconds
    assert 0.09 <= elapsed_dilated <= 0.11
    # Real time should be ~0.05 seconds
    assert 0.04 <= elapsed_original <= 0.06

    # Original time module should be unaffected
    assert time_original.sleep is not sleep


def test_urllib_punycode_override() -> None:
    """Test that urllib automatically decodes punycode domains."""
    # Test direct usage of patched urlparse
    from urllib_punycode.parse import urlparse as test_urlparse

    url = "https://xn--bcher-kva.example.com/path"
    result = test_urlparse(url)
    assert result.netloc == "bücher.example.com"

    # Test that urllib.request uses our decoded version internally
    from urllib_punycode.request import (  # type: ignore [reportMissingImports]
        Request,
        request_host,
    )

    request = Request(url)
    assert request_host(request) == "bücher.example.com"

    # Verify original stdlib urlparse remains unaffected
    from urllib.parse import urlparse as original_urlparse

    orig_result = original_urlparse(url)
    assert orig_result.netloc == "xn--bcher-kva.example.com"


def test_csv_schema_override() -> None:
    """Test that csv module supports schema validation."""
    import csv as original_csv
    from datetime import datetime
    from io import StringIO

    from csv_schema import DictReader, Schema

    # Test data with mixed types
    csv_data = StringIO(
        """
id,name,date,score
1,Alice,2024-01-15,95.5
2,Bob,15/01/2024,87.3
3,Charlie,2024/01/15,92.8
""".strip()
    )

    # Define schema
    schema = Schema(id=int, name=str, date=datetime, score=float)

    # Read with schema validation
    reader = DictReader(csv_data, schema=schema)
    rows = list(reader)

    # Verify conversions
    assert len(rows) == 3
    assert isinstance(rows[0]["id"], int)
    assert isinstance(rows[0]["name"], str)
    assert isinstance(rows[0]["date"], datetime)
    assert isinstance(rows[0]["score"], float)

    # Verify values
    assert rows[0]["id"] == 1
    assert rows[0]["name"] == "Alice"
    assert rows[0]["date"].year == 2024
    assert rows[0]["score"] == 95.5

    # Verify different date formats are handled
    assert rows[1]["date"].year == 2024
    assert rows[2]["date"].year == 2024

    # Verify original csv remains unaffected
    csv_data.seek(0)
    original_reader = original_csv.DictReader(csv_data)
    original_row = next(original_reader)
    assert isinstance(original_row["id"], str)  # Still strings
    assert isinstance(original_row["score"], str)
