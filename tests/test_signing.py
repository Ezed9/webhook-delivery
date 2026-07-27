import hashlib
import hmac
import time

from app.signing import sign, verify


def test_known_vector() -> None:
    secret = "test-secret"
    timestamp = "1700000000"
    body = b'{"event":"test"}'
    msg = timestamp.encode() + b"." + body
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    assert sign(secret, timestamp, body) == expected


def test_round_trip() -> None:
    secret = "whsec_abc123"
    ts = str(int(time.time()))
    body = b'{"key":"value"}'
    sig = sign(secret, ts, body)
    assert verify(secret, ts, body, f"v1={sig}")


def test_tampered_body_fails() -> None:
    secret = "s"
    ts = str(int(time.time()))
    sig = sign(secret, ts, b"original")
    assert not verify(secret, ts, b"tampered", f"v1={sig}")


def test_wrong_secret_fails() -> None:
    ts = str(int(time.time()))
    body = b"data"
    sig = sign("right", ts, body)
    assert not verify("wrong", ts, body, f"v1={sig}")


def test_stale_timestamp_fails() -> None:
    secret = "s"
    old_ts = str(int(time.time()) - 600)
    body = b"data"
    sig = sign(secret, old_ts, body)
    assert not verify(secret, old_ts, body, f"v1={sig}", tolerance_s=300)
