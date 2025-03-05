"""Enhanced pathlib with additional utility methods."""

from __future__ import annotations

from pathlib._local import Path as OriginalPath


class Path(OriginalPath):
    """Enhanced Path with additional utilities."""

    def is_empty(self) -> bool:
        """Return True if directory is empty or file has zero size."""
        if not self.exists():
            raise FileNotFoundError(f"Path does not exist: {self}")
        if self.is_file():
            return self.stat().st_size == 0
        if self.is_dir():
            return not any(self.iterdir())
        return False
