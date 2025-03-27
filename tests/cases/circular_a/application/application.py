from typing import Generic, TypeVar

from ..layout.containers import Container

print("RUNNING!", __name__, f"{Container.__module__=}")
#
T = TypeVar("T")


class Application(Generic[T]):
    c = Container()
