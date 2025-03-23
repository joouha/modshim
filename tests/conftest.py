"""Common test fixtures."""

import sys
from collections.abc import Iterator

import pytest

from modshim import ModShimFinder


@pytest.fixture(autouse=True)
def cleanup_modules() -> Iterator[None]:
    """Clean up any merged modules and finders between tests."""
    # Store original state
    original_meta_path = list(sys.meta_path)
    original_modules = dict(sys.modules)

    yield

    # Remove any MergedModuleFinder instances
    sys.meta_path = [
        finder for finder in sys.meta_path if not isinstance(finder, ModShimFinder)
    ]
    sys.meta_path.extend(
        finder for finder in original_meta_path if finder not in sys.meta_path
    )

    # Remove any modules that weren't present originally
    for name in list(sys.modules):
        if name not in original_modules:
            del sys.modules[name]
