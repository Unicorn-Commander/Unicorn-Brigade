"""
Key-rotation drill for Brigade federation (the 7-step proof sequence).

Exercises the real KeyStore rotation slots (current + previous) and a
kid-based JWKS verifier (what a per-app verifier does): a token is verifiable
only while its signing key's `kid` is still published in the JWKS. The proof is
step 7: once the old key drops out of the JWKS, tokens it signed STOP verifying.

Run: python -m pytest app/federation/test_rotation_drill.py -v
"""
import os
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt

ISS = "https://brigade.unicorncommander.ai"


def _pem() -> str:
    k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return k.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def _keystore(current_pem, current_kid, prev_pem=None, prev_kid=None):
    """Fresh KeyStore loaded from a specific env config (simulates a rotation phase)."""
    os.environ["BRIGADE_JWT_PRIVATE_KEY"] = current_pem
    os.environ["BRIGADE_JWT_KID"] = current_kid
    os.environ["BRIGADE_ISSUER"] = ISS
    if prev_pem:
        os.environ["BRIGADE_JWT_PRIVATE_KEY_PREV"] = prev_pem
        os.environ["BRIGADE_JWT_KID_PREV"] = prev_kid
    else:
        os.environ.pop("BRIGADE_JWT_PRIVATE_KEY_PREV", None)
        os.environ.pop("BRIGADE_JWT_KID_PREV", None)
    from app.federation.keys import KeyStore
    return KeyStore()


def _mint(ks, sub="u-1", aud="project-ops") -> str:
    k = ks.signing_key()
    now = int(time.time())
    return jose_jwt.encode(
        {"iss": ISS, "aud": aud, "sub": sub, "iat": now, "nbf": now, "exp": now + 300, "jti": "drill"},
        k.private_pem, algorithm="RS256", headers={"kid": k.kid},
    )


def _verify_via_jwks(token: str, jwks: dict):
    """A per-app verifier: resolve the JWK by the token's kid, then verify.

    Raises if the kid is not published in the JWKS (the rotation-expiry behavior).
    """
    kid = jose_jwt.get_unverified_header(token).get("kid")
    key = next((k for k in jwks["keys"] if k["kid"] == kid), None)
    if key is None:
        raise KeyError(f"kid {kid} not in JWKS")
    return jose_jwt.decode(token, key, algorithms=["RS256"], audience="project-ops", issuer=ISS)


def test_rotation_drill_seven_steps():
    pem_a, pem_b = _pem(), _pem()

    # Step 1: mint with key A (current); it round-trips.
    ks1 = _keystore(pem_a, "brigade-keyA")
    jwks1 = ks1.public_jwks()
    assert {k["kid"] for k in jwks1["keys"]} == {"brigade-keyA"}
    tok_a = _mint(ks1)
    assert _verify_via_jwks(tok_a, jwks1)["sub"] == "u-1"

    # Step 2: rotate, B becomes current, A demoted to previous; JWKS publishes both.
    ks2 = _keystore(pem_b, "brigade-keyB", prev_pem=pem_a, prev_kid="brigade-keyA")
    jwks2 = ks2.public_jwks()
    assert {k["kid"] for k in jwks2["keys"]} == {"brigade-keyB", "brigade-keyA"}

    # Step 3: the OLD A-signed token still verifies during the grace window.
    assert _verify_via_jwks(tok_a, jwks2)["sub"] == "u-1"

    # Step 4: mint a new token with key B; it verifies.
    tok_b = _mint(ks2)
    assert _verify_via_jwks(tok_b, jwks2)["sub"] == "u-1"

    # Step 5: during overlap BOTH tokens verify.
    assert _verify_via_jwks(tok_a, jwks2) and _verify_via_jwks(tok_b, jwks2)

    # Step 6: expire key A out of the JWKS entirely (only B remains).
    ks3 = _keystore(pem_b, "brigade-keyB")
    jwks3 = ks3.public_jwks()
    assert {k["kid"] for k in jwks3["keys"]} == {"brigade-keyB"}

    # Step 7 (THE PROOF): the old A-signed token now fails, its kid is gone.
    failed = False
    try:
        _verify_via_jwks(tok_a, jwks3)
    except (KeyError, Exception):
        failed = True
    assert failed, "old A-signed token must STOP verifying once key A leaves the JWKS"

    # ...and the current B-signed token still verifies.
    assert _verify_via_jwks(tok_b, jwks3)["sub"] == "u-1"
