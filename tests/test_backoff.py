from app.backoff import next_delay_s


def test_bounds() -> None:
    for attempt in range(9):
        cap = min(900.0, 5.0 * 2**attempt)
        samples = [next_delay_s(attempt) for _ in range(100)]
        assert all(0 <= s <= cap for s in samples)
        assert len(set(round(s, 6) for s in samples)) > 1
