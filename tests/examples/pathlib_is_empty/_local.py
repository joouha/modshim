"""Enhanced pathlib local implementations."""
from pathlib._local import (
    Path as OriginalPath,
    PurePath as OriginalPurePath,
    PurePosixPath as OriginalPurePosixPath,
    PureWindowsPath as OriginalPureWindowsPath,
    WindowsPath as OriginalWindowsPath,
    PosixPath as OriginalPosixPath
)
from ._abc import PathBase

# Re-export the pure path classes unchanged
PurePath = OriginalPurePath
PurePosixPath = OriginalPurePosixPath
PureWindowsPath = OriginalPureWindowsPath

# Create enhanced Path classes with our PathBase
class Path(PathBase, OriginalPath):
    """Enhanced Path with additional utilities."""
    pass

class WindowsPath(PathBase, OriginalWindowsPath):
    """Enhanced WindowsPath with additional utilities."""
    pass

class PosixPath(PathBase, OriginalPosixPath):
    """Enhanced PosixPath with additional utilities."""
    pass
