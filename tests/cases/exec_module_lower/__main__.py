"""Entry-point for test case."""

import atexit

from .a import X, Y

suffix = "ABC"


def finish() -> None:
    """Print a final statement."""
    if suffix:
        print(suffix)  # noqa: T201


atexit.register(finish)

if __name__ == "__main__":
    print(X)  # noqa: T201
    print(Y)  # noqa: T201
    from .b import Z

    print(Z)  # noqa: T201
