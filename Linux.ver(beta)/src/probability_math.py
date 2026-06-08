from __future__ import annotations

import math
from typing import Iterable

PERCENT_SCALE = 10  # 0.1% precision
PERCENT_TOTAL_UNITS = 100 * PERCENT_SCALE


def distribute_percent_units(values: Iterable[float], total_units: int = PERCENT_TOTAL_UNITS) -> list[int]:
    """Normalize non-negative values into exact 0.1% units using largest remainders."""
    cleaned: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        cleaned.append(number if math.isfinite(number) and number > 0 else 0.0)

    count = len(cleaned)
    if count == 0:
        return []
    total = sum(cleaned)
    if total <= 0:
        quotient, remainder = divmod(total_units, count)
        return [quotient + (1 if index < remainder else 0) for index in range(count)]

    exact = [value / total * total_units for value in cleaned]
    result = [int(math.floor(value)) for value in exact]
    remainder = total_units - sum(result)
    order = sorted(range(count), key=lambda index: (exact[index] - result[index], -index), reverse=True)
    for index in order[:remainder]:
        result[index] += 1
    return result
