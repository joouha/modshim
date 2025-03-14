"""Custom datetime implementation with weekend detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from _pydatetime import datetime as OriginalDateTime

if TYPE_CHECKING:
    from datetime import tzinfo

MAXYEAR = 3000


class datetime(OriginalDateTime):
    """Enhanced datetime class with weekend detection."""

    @property
    def is_weekend(self) -> bool:
        """Return True if the date falls on a weekend (Saturday or Sunday)."""
        return self.weekday() >= 5

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        """Return the current date and time (fixed for testing)."""
        # Always return a fixed time for testing
        return cls(2024, 1, 6)  # A Saturday
