"""Application module for circular import testing."""

from typing import Generic, TypeVar

from ..layout.containers import Container

# Removed print statement
T = TypeVar("T")


class Application(Generic[T]):
    """Application class that uses Container from layout module."""

    c = Container()
