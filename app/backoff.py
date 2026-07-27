import random


def next_delay_s(attempt: int, base_s: float = 5.0, cap_s: float = 900.0) -> float:
    return random.uniform(0, min(cap_s, base_s * 2**attempt))
