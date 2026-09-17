"""Pure-Python Ed25519 (RFC 8032). Vendored so the kernel has zero
cryptographic dependencies: audit this file, depend on nothing.

Correctness is proven by cross-verification against the `cryptography`
package in tests/test_crypto.py (both directions), not by trust.
"""
import hashlib

_B = 256
_Q = (1 << 255) - 19
_L = (1 << 252) + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, -1, _Q) % _Q
_GY = (4 * pow(5, -1, _Q)) % _Q
_GX = None  # computed below


def _xrec(y):
    xx = (y * y - 1) * pow(_D * y * y + 1, -1, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * pow(2, (_Q - 1) // 4, _Q)) % _Q
    return x if x % 2 == 0 else _Q - x


def _edwards(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _Q
    b = (y1 + x1) * (y2 + x2) % _Q
    c = t1 * 2 * _D * t2 % _Q
    d = z1 * 2 * z2 % _Q
    e = b - a
    f = d - c
    g = d + c
    h = b + a
    return (e * f % _Q, g * h % _Q, f * g % _Q, e * h % _Q)


def _scalarmult(p, e):
    q = (0, 1, 1, 0)
    while e > 0:
        if e & 1:
            q = _edwards(q, p)
        p = _edwards(p, p)
        e >>= 1
    return q


def _encodepoint(p):
    x, y, _, _ = p
    z = pow(p[2], -1, _Q)
    x, y = x * z % _Q, y * z % _Q
    b = (y | ((x & 1) << 255)).to_bytes(32, "little")
    return b


def _decodepoint(s):
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    sign = (s[31] >> 7) & 1
    x = _xrec(y)
    if x & 1 != sign:
        x = _Q - x
    return (x, y, 1, x * y % _Q)


_GX = _xrec(_GY)
_G = (_GX, _GY, 1, _GX * _GY % _Q)


def _hint(m):
    return int.from_bytes(hashlib.sha512(m).digest(), "little") % _L


def pubkey(secret: bytes) -> bytes:
    """Derive the 32-byte public key. Cross-checked against RFC 8032
    vectors via the tests (hand constants banned after a typo)."""
    assert len(secret) == 32
    h = hashlib.sha512(secret).digest()
    a = (int.from_bytes(h[:32], "little") & ~((1 | 2 | 4 | (1 << 255)))
         | (1 << 254))
    return _encodepoint(_scalarmult(_G, a))


def sign(secret: bytes, msg: bytes) -> bytes:
    """64-byte deterministic signature (RFC 8032, no randomness)."""
    assert len(secret) == 32
    h = hashlib.sha512(secret).digest()
    a = (int.from_bytes(h[:32], "little") & ~((1 | 2 | 4 | (1 << 255)))
         | (1 << 254))
    prefix = h[32:]
    pk = _encodepoint(_scalarmult(_G, a))
    r = _hint(prefix + msg)
    big_r = _encodepoint(_scalarmult(_G, r))
    s = (r + _hint(big_r + pk + msg) * a) % _L
    return big_r + s.to_bytes(32, "little")


def verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    """Check [s]G == R + [H(R,A,M)]A. False on any malformed input."""
    if len(pub) != 32 or len(sig) != 64:
        return False
    try:
        a_pt = _decodepoint(pub)
        r_pt = _decodepoint(sig[:32])
    except Exception:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _L:
        return False
    h = _hint(sig[:32] + pub + msg)
    lhs = _scalarmult(_G, s)
    rhs = _edwards(r_pt, _scalarmult(a_pt, h))
    return _encodepoint(lhs) == _encodepoint(rhs)
