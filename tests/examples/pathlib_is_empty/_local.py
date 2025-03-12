"""Enhanced pathlib local implementations."""

from pathlib._local import Path as OriginalPath
from pathlib._local import PosixPath as OriginalPosixPath
from pathlib._local import WindowsPath as OriginalWindowsPath

from ._abc import PathBase


# Create enhanced Path classes with our PathBase
class Path(PathBase, OriginalPath):
    """Enhanced Path with additional utilities."""


class WindowsPath(PathBase, OriginalWindowsPath):
    """Enhanced WindowsPath with additional utilities."""


class PosixPath(PathBase, OriginalPosixPath):
    """Enhanced PosixPath with additional utilities."""
