"""Enhanced pathlib local implementations."""

from pathlib._abc import PathBase as OriginalPathBase


class PathBase(OriginalPathBase):
    """Enhanced Path with additional utilities."""

    @property
    def is_empty(self) -> bool:
        """Return True if directory is empty or file has zero size."""
        if not self.exists():
            raise FileNotFoundError(f"Path does not exist: {self}")
        if self.is_file():
            return self.stat().st_size == 0
        if self.is_dir():
            return not any(self.iterdir())
        return False
