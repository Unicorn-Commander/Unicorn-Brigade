#!/usr/bin/env python3
"""
Generate a Brigade federation RS256 signing keypair.

Prints the private key PEM (store it in the secret manager / bigboy .env as
BRIGADE_JWT_PRIVATE_KEY, never commit it), the kid, and the public JWK for a
sanity check. Run inside the unicorn-brigade container or any env with the
`cryptography` package.

  python scripts/gen_brigade_jwt_key.py --kid brigade-2026-q2-rsa-01
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def b64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


def thumbprint(n: int, e: int) -> str:
    members = {"e": b64url_uint(e), "kty": "RSA", "n": b64url_uint(n)}
    canonical = json.dumps(members, separators=(",", ":"), sort_keys=True).encode("ascii")
    return base64.urlsafe_b64encode(hashlib.sha256(canonical).digest()).rstrip(b"=").decode("ascii")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kid", default=None, help="kid for the key (default: RFC 7638 thumbprint)")
    ap.add_argument("--bits", type=int, default=2048)
    args = ap.parse_args()

    priv = rsa.generate_private_key(public_exponent=65537, key_size=args.bits)
    pub = priv.public_key().public_numbers()
    kid = args.kid or thumbprint(pub.n, pub.e)

    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    jwk = {"kty": "RSA", "use": "sig", "alg": "RS256", "kid": kid,
           "n": b64url_uint(pub.n), "e": b64url_uint(pub.e)}

    print("# ---- BRIGADE_JWT_PRIVATE_KEY (store in secret manager, do NOT commit) ----")
    print(pem.strip())
    print(f"\n# ---- BRIGADE_JWT_KID ----\n{kid}\n")
    print("# ---- public JWK (reference; served at /.well-known/jwks.json) ----")
    print(json.dumps(jwk, indent=2))


if __name__ == "__main__":
    main()
