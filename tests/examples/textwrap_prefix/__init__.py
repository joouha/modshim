"""Enhanced textwrap module that adds a prefix to wrapped lines."""

from textwrap import TextWrapper as OriginalTextWrapper
from typing import Any


class TextWrapper(OriginalTextWrapper):
    """Enhanced TextWrapper that adds a prefix to each line."""

    def __init__(self, *args: Any, prefix: str = "", **kwargs: Any) -> None:
        """Initialize TextWrapper with an optional prefix."""
        self.prefix = prefix
        if prefix:
            kwargs["width"] -= len(prefix)
        super().__init__(*args, **kwargs)

    def wrap(self, text: str) -> list[str]:
        """Wrap text and apply prefix to each line."""
        lines = super().wrap(text)
        if self.prefix:
            return [self.prefix + line for line in lines]
        return lines
