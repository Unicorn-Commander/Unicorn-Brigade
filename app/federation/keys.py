"""
Brigade federation signing keys (RS256).

Brigade mints short-lived RS256 JWTs for federated UC apps and publishes the
matching public keys at /.well-known/jwks.json. Per BRIGADE-FEDERATION-SPEC.md
the algorithm is RS256 (python-jose, used by the FastAPI verifier apps, has no
EdDSA support), so every key here is RSA.

Private keys load from the environment as PEM and are NEVER committed or exposed.
The public half is derived and served in the JWKS. Two slots support rotation
with a grace window:

  BRIGADE_JWT_PRIVATE_KEY       current signing key (PEM)
  BRIGADE_JWT_KID               kid for the current key (optional; defaults to
                                the RFC 7638 JWK thumbprint)
  BRIGADE_JWT_PRIVATE_KEY_PREV  previous key, still published in JWKS during the
                                rotation grace window (optional)
  BRIGADE_JWT_KID_PREV          kid for the previous key (optional)

If no current key is configured the federation surface stays dark: the JWKS
endpoint returns an empty key set and minting raises. Set
BRIGADE_JWT_ALLOW_EPHEMERAL=1 to auto-generate a throwaway key at boot for local
dev/tests only (tokens do not survive a restart). Generate a real key with
scripts/gen_brigade_jwt_key.py.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

logger = logging.getLogger(__name__)

ALG = "RS256"
_MIN_KEY_SIZE = 2048


def _b64url_uint(value: int) -> str:
    """Encode an unsigned integer as base64url (no padding), big-endian (RFC 7518)."""
    length = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def _normalize_pem(raw: str) -> bytes:
    """Accept PEM with real newlines or escaped backslash-n (common in .env files)."""
    raw = raw.strip()
    if "\\n" in raw and "\n" not in raw:
        raw = raw.replace("\\n", "\n")
    return raw.encode("utf-8")


def _load_private(pem: str) -> RSAPrivateKey:
    key = serialization.load_pem_private_key(_normalize_pem(pem), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise ValueError("BRIGADE_JWT private key must be RSA (RS256 requires an RSA key)")
    if key.key_size < _MIN_KEY_SIZE:
        raise ValueError(f"RSA key too small ({key.key_size} bits); need at least {_MIN_KEY_SIZE}")
    return key


def _public_jwk(pub: RSAPublicKey, kid: str) -> dict:
    """Public-only RSA JWK. Never includes private parameters (d, p, q)."""
    n = pub.public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": ALG,
        "kid": kid,
        "n": _b64url_uint(n.n),
        "e": _b64url_uint(n.e),
    }


def _thumbprint_kid(pub: RSAPublicKey) -> str:
    """RFC 7638 JWK thumbprint, a stable kid derived from the public key."""
    n = pub.public_numbers()
    members = {"e": _b64url_uint(n.e), "kty": "RSA", "n": _b64url_uint(n.n)}
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True).encode("ascii")
    return base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class SigningKey:
    private_pem: str
    public_jwk: dict
    kid: str


class KeyStore:
    """Loads RS256 signing keys from the environment. Thread-safe and lazy."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._current: Optional[SigningKey] = None
        self._previous: Optional[SigningKey] = None

    def _build(self, pem: str, kid_env: Optional[str]) -> SigningKey:
        priv = _load_private(pem)
        pub = priv.public_key()
        kid = (kid_env or "").strip() or _thumbprint_kid(pub)
        norm_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("ascii")
        jwk = _public_jwk(pub, kid)
        assert "d" not in jwk and "p" not in jwk, "JWK must not contain private material"
        return SigningKey(private_pem=norm_pem, public_jwk=jwk, kid=kid)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            cur_pem = os.getenv("BRIGADE_JWT_PRIVATE_KEY", "").strip()
            if cur_pem:
                self._current = self._build(cur_pem, os.getenv("BRIGADE_JWT_KID"))
                logger.info("Brigade federation signing key loaded (kid=%s)", self._current.kid)
            elif os.getenv("BRIGADE_JWT_ALLOW_EPHEMERAL") == "1":
                priv = rsa.generate_private_key(public_exponent=65537, key_size=_MIN_KEY_SIZE)
                pem = priv.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode("ascii")
                self._current = self._build(pem, "brigade-ephemeral")
                logger.warning(
                    "BRIGADE_JWT_PRIVATE_KEY unset; generated an EPHEMERAL key (kid=%s). "
                    "Tokens will not survive a restart. Dev/test only.",
                    self._current.kid,
                )
            else:
                logger.warning(
                    "BRIGADE_JWT_PRIVATE_KEY unset; federation JWT minting is disabled and "
                    "JWKS is empty until a key is provisioned (scripts/gen_brigade_jwt_key.py)."
                )
            prev_pem = os.getenv("BRIGADE_JWT_PRIVATE_KEY_PREV", "").strip()
            if prev_pem:
                self._previous = self._build(prev_pem, os.getenv("BRIGADE_JWT_KID_PREV"))
                logger.info("Brigade federation previous (rotating-out) key loaded (kid=%s)", self._previous.kid)
            self._loaded = True

    def signing_key(self) -> SigningKey:
        self._ensure_loaded()
        if self._current is None:
            raise RuntimeError("Brigade federation signing key is not configured (set BRIGADE_JWT_PRIVATE_KEY).")
        return self._current

    def is_configured(self) -> bool:
        self._ensure_loaded()
        return self._current is not None

    def public_jwks(self) -> dict:
        """Public JWKS: current key first, then the previous key during rotation."""
        self._ensure_loaded()
        keys = []
        if self._current is not None:
            keys.append(self._current.public_jwk)
        if self._previous is not None and (self._current is None or self._previous.kid != self._current.kid):
            keys.append(self._previous.public_jwk)
        return {"keys": keys}


_store = KeyStore()


def get_keystore() -> KeyStore:
    return _store
