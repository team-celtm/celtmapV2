from __future__ import annotations

import random
from typing import TypeVar

T = TypeVar("T")


def shuffled(items: list[T], seed: int | None = None) -> list[T]:
    cloned = list(items)
    random.Random(seed).shuffle(cloned)
    return cloned
