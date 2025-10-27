"""Test some realistic patching of stdlib modules."""

import pytest

from modshim import shim


def test_json_single_quotes_override() -> None:
    """Test that json strings are encoded with single quotes while preserving original behavior."""
    shim(
        lower="json",
        upper="tests.examples.json_single_quotes",
        mount="json_single_quotes",
    )

    import json

    import json_single_quotes as json_test  # type: ignore [reportMissingImports]

    data = {"name": "test", "list": ["a", "b"]}
    result = json_test.dumps(data)  # type: ignore [reportAttributeAccessIssue]
    original_result = json.dumps(data)

    # Our version uses single quotes
    assert result == "{'name': 'test', 'list': ['a', 'b']}"
    # Original json module should still use double quotes
    assert original_result == '{"name": "test", "list": ["a", "b"]}'


def test_json_metadata_override() -> None:
    """Test that json.dumps can be overridden while preserving original behavior."""
    shim(lower="json", upper="tests.examples.json_metadata", mount="json_metadata")
    import json

    from json_metadata import dumps  # type: ignore [reportMissingImports]

    data = {"name": "test"}
    result = dumps(data)

    # Original json should be unaffected
    original_result = json.dumps(data)

    assert json.loads(result) == {
        "name": "test",
        "_metadata": {"timestamp": "2024-01-01"},
    }
    assert json.loads(original_result) == {"name": "test"}


def test_textwrap_prefix_override() -> None:
    """Test that textwrap can be enhanced to prefix lines."""
    shim(
        lower="textwrap",
        upper="tests.examples.textwrap_prefix",
        mount="textwrap_prefix",
    )
    import textwrap

    import textwrap_prefix as textwrap_test  # type: ignore [reportMissingImports]

    text = "This is a long line of text that will be wrapped."

    # Test our shimed version
    wrapped = textwrap_test.wrap(text, width=20, prefix="> ")
    assert wrapped == [
        "> This is a long",
        "> line of text that",
        "> will be wrapped.",
    ]

    filled = textwrap_test.fill(text, width=20, prefix="> ")
    assert filled == ("> This is a long\n> line of text that\n> will be wrapped.")

    # Test that original is unaffected
    original_wrapped = textwrap.wrap(text, width=20)
    assert original_wrapped == [
        "This is a long line",
        "of text that will be",
        "wrapped.",
    ]
    # Original wrap doesn't accept 'prefix'
    with pytest.raises(TypeError):
        textwrap.wrap(text, width=20, prefix="> ")  # type: ignore [reportCallIssue]


def test_random_fixed_seed() -> None:
    """Test that random module can be configured with a fixed seed."""
    shim(lower="random", upper="tests.examples.random_fixed", mount="random_fixed")
    import random

    from random_fixed import Random  # type: ignore [reportMissingImports]

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


def test_time_dilation() -> None:
    """Test that time can be dilated while preserving original behavior."""
    shim(lower="time", upper="tests.examples.time_dilation", mount="time_dilation")
    import time as time_original

    from time_dilation import (  # type: ignore [reportMissingImports]
        set_dilation,
        sleep,
        time,
    )

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
    assert 0.05 <= elapsed_dilated <= 0.15
    # Real time should be ~0.05 seconds
    assert 0.025 <= elapsed_original <= 0.075

    # Original time module should be unaffected
    assert time_original.sleep is not sleep


def test_urllib_punycode_override() -> None:
    """Test that urllib automatically decodes punycode domains."""
    shim(
        lower="urllib",
        upper="tests.examples.urllib_punycode",
        mount="urllib_punycode",
    )
    # Test direct usage of patched urlparse
    from urllib_punycode.parse import (  # type: ignore [reportMissingImports]
        urlparse as test_urlparse,
    )

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
    shim(lower="csv", upper="tests.examples.csv_schema", mount="csv_schema")
    import csv as original_csv
    from datetime import datetime
    from io import StringIO

    from csv_schema import DictReader, Schema  # type: ignore [reportMissingImports]

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
    # Verify original DictReader rejects schema parameter
    with pytest.raises(TypeError):
        original_csv.DictReader(csv_data, schema=schema)  # type: ignore [reportCallIssue]
    original_reader = original_csv.DictReader(csv_data)
    original_row = next(original_reader)
    assert isinstance(original_row["id"], str)  # Still strings
    assert isinstance(original_row["score"], str)


def test_filecmp_ignores_override() -> None:
    """Test that filecmp.DEFAULT_IGNORES can be overridden."""
    shim(
        lower="filecmp",
        upper="tests.examples.filecmp_ignores",
        mount="filecmp_ignores",
    )
    import filecmp
    import tempfile
    from pathlib import Path

    from filecmp_ignores import (  # type: ignore [reportCallIssue]
        DEFAULT_IGNORES as SHIM_DEFAULT_IGNORES,
    )
    from filecmp_ignores import (  # type: ignore [reportMissingImports]
        dircmp,
    )

    # Check our new default ignores list
    assert ".new_ignore" in SHIM_DEFAULT_IGNORES
    # Check original is not affected
    assert ".new_ignore" not in filecmp.DEFAULT_IGNORES

    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "dir1"
        dir2 = Path(tmpdir) / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create files
        (dir1 / ".new_ignore").touch()
        (dir1 / "not_ignored").touch()

        # Use our shimmed dircmp. '.new_ignore' should be ignored by default.
        comparison = dircmp(str(dir1), str(dir2))
        assert comparison.left_only == ["not_ignored"]

        # Use original filecmp. '.new_ignore' should NOT be ignored by default.
        original_comparison = filecmp.dircmp(str(dir1), str(dir2))
        assert sorted(original_comparison.left_only) == [".new_ignore", "not_ignored"]


def test_json_single_quotes_override_overmount() -> None:
    """Test that json strings are encoded with single quotes while preserving original behavior."""
    shim(
        lower="json",
        upper="tests.examples.json_single_quotes",
        mount="tests.examples.json_single_quotes",
    )

    import json

    import tests.examples.json_single_quotes as json_test  # type: ignore [reportMissingImports]

    data = {"name": "test", "list": ["a", "b"]}
    result = json_test.dumps(data)  # type: ignore [reportAttributeAccessIssue]

    original_result = json.dumps(data)

    # Our version uses single quotes
    assert result == "{'name': 'test', 'list': ['a', 'b']}"
    # Original json module should still use double quotes
    assert original_result == '{"name": "test", "list": ["a", "b"]}'


def test_json_metadata_override_overmount() -> None:
    """Test that json.dumps can be overridden while preserving original behavior."""
    shim(
        lower="json",
        upper="tests.examples.json_metadata",
        mount="tests.examples.json_metadata",
    )
    import json

    from tests.examples.json_metadata import (  # type: ignore [reportMissingImports]
        dumps,
    )

    data = {"name": "test"}
    result = dumps(data)

    # Original json should be unaffected
    original_result = json.dumps(data)

    assert json.loads(result) == {
        "name": "test",
        "_metadata": {"timestamp": "2024-01-01"},
    }
    assert json.loads(original_result) == {"name": "test"}


def test_random_fixed_seed_overmount() -> None:
    """Test that random module can be configured with a fixed seed."""
    shim(
        lower="random",
        upper="tests.examples.random_fixed",
        mount="tests.examples.random_fixed",
    )
    import random

    from tests.examples.random_fixed import (
        Random,  # type: ignore [reportMissingImports]
    )

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


def test_time_dilation_overmount() -> None:
    """Test that time can be dilated while preserving original behavior."""
    shim(
        lower="time",
        upper="tests.examples.time_dilation",
        mount="tests.examples.time_dilation",
    )
    import time as time_original

    from tests.examples.time_dilation import (  # type: ignore [reportMissingImports]
        set_dilation,
        sleep,
        time,
    )

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
    assert 0.05 <= elapsed_dilated <= 0.15
    # Real time should be ~0.05 seconds
    assert 0.025 <= elapsed_original <= 0.075

    # Original time module should be unaffected
    assert time_original.sleep is not sleep


def test_urllib_punycode_override_overmount() -> None:
    """Test that urllib automatically decodes punycode domains."""
    shim(
        lower="urllib",
        upper="tests.examples.urllib_punycode",
        mount="tests.examples.urllib_punycode",
    )
    # Test direct usage of patched urlparse
    from tests.examples.urllib_punycode.parse import (  # type: ignore [reportMissingImports]
        urlparse as test_urlparse,
    )

    url = "https://xn--bcher-kva.example.com/path"
    result = test_urlparse(url)
    assert result.netloc == "bücher.example.com"

    # Test that urllib.request uses our decoded version internally
    from tests.examples.urllib_punycode.request import (  # type: ignore [reportMissingImports]
        Request,
        request_host,
    )

    request = Request(url)
    assert request_host(request) == "bücher.example.com"

    # Verify original stdlib urlparse remains unaffected
    from urllib.parse import urlparse as original_urlparse

    orig_result = original_urlparse(url)
    assert orig_result.netloc == "xn--bcher-kva.example.com"


def test_csv_schema_override_overmount() -> None:
    """Test that csv module supports schema validation."""
    shim(
        lower="csv",
        upper="tests.examples.csv_schema",
        mount="tests.examples.csv_schema",
    )
    import csv as original_csv
    from datetime import datetime
    from io import StringIO

    from tests.examples.csv_schema import (  # type: ignore [reportMissingImports]
        DictReader,
        Schema,
    )

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
    _ = csv_data.seek(0)
    # Verify original DictReader rejects schema parameter
    with pytest.raises(TypeError):
        _ = original_csv.DictReader(csv_data, schema=schema)  # type: ignore [reportCallIssue]
    original_reader = original_csv.DictReader(csv_data)
    original_row = next(original_reader)
    assert isinstance(original_row["id"], str)  # Still strings
    assert isinstance(original_row["score"], str)


def test_filecmp_ignores_override_overmount() -> None:
    """Test that filecmp.DEFAULT_IGNORES can be overridden."""
    shim(
        lower="filecmp",
        upper="tests.examples.filecmp_ignores",
        mount="tests.examples.filecmp_ignores",
    )
    import filecmp
    import tempfile
    from pathlib import Path

    from tests.examples.filecmp_ignores import (
        DEFAULT_IGNORES as SHIM_DEFAULT_IGNORES,
    )
    from tests.examples.filecmp_ignores import (
        dircmp,  # type: ignore [reportMissingImports]
    )

    assert ".new_ignore" in SHIM_DEFAULT_IGNORES
    assert ".new_ignore" not in filecmp.DEFAULT_IGNORES

    with tempfile.TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "dir1"
        dir2 = Path(tmpdir) / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / ".new_ignore").touch()
        (dir1 / "not_ignored").touch()

        comparison = dircmp(str(dir1), str(dir2))
        assert comparison.left_only == ["not_ignored"]

        original_comparison = filecmp.dircmp(str(dir1), str(dir2))
        assert sorted(original_comparison.left_only) == [
            ".new_ignore",
            "not_ignored",
        ]
