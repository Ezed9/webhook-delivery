import hashlib
import hmac
import time


def sign(secret: str, timestamp: str, body: bytes) -> str:
    msg = timestamp.encode() + b"." + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(
    secret: str, timestamp: str, body: bytes, signature: str, tolerance_s: int = 300
) -> bool:
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > tolerance_s:
        return False
    if signature.startswith("v1="):
        signature = signature[3:]
    expected = sign(secret, timestamp, body)
    return hmac.compare_digest(expected, signature)
