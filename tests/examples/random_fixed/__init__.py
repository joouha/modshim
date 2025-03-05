"""Enhanced random module with fixed seed capability."""

from __future__ import annotations

import random as original_random
from typing import Any

# Store the original Random class
OriginalRandom = original_random.Random


class Random(OriginalRandom):
    """Enhanced Random with fixed seed capability."""

    _fixed_seed: int | None = None

    def seed(self, a: Any = None, version: int = 2) -> None:
        """Seed the generator. If fixed seed is set, always use that."""
        if self._fixed_seed is not None:
            super().seed(self._fixed_seed, version)
        else:
            super().seed(a, version)

    @classmethod
    def set_fixed_seed(cls, seed: int | None) -> None:
        """Set a fixed seed that will be used for all seeding operations."""
        cls._fixed_seed = seed


# Replace the default random generator
_instance = Random()
setstate = _instance.setstate
getstate = _instance.getstate
seed = _instance.seed
random = _instance.random
