"""Module in lower package with __all__, upper has no __all__."""

x = 1
y = 2
_private = 3

__all__ = ["x", "y"]
