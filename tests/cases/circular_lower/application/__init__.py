"""Application subpackage for circular import testing."""

from .application import Application

# from tests.examples.circular_a.application import Application
from .current import get_app

__all__ = ["Application", "get_app"]
