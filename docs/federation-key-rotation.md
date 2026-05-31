# Brigade Federation, Key Rotation Runbook

Brigade signs federation JWTs with **RS256** and publishes the public keys at
`/.well-known/jwks.json`. Per-app verifiers fetch that JWKS and resolve each
token's signing key by its `kid`. Rotation works by publishing a new key
alongside the old one for a grace window, then dropping the old one.

The mechanics are in `app/federation/keys.py` (KeyStore: a `current` slot and a
`previous` slot, both published in the JWKS). The 7-step drill that proves this
end to end is `app/federation/test_rotation_drill.py`.

## Key material (secret store, never committed)

| env var | meaning |
|---|---|
| `BRIGADE_JWT_PRIVATE_KEY` | current signing key (PEM). Brigade mints with this. |
| `BRIGADE_JWT_KID` | kid for the current key (human label, e.g. `brigade-2026-q3-rsa-01`) |
| `BRIGADE_JWT_PRIVATE_KEY_PREV` | previous key (PEM), published in JWKS during the grace window only |
| `BRIGADE_JWT_KID_PREV` | kid for the previous key |

If `BRIGADE_JWT_PRIVATE_KEY` is unset Brigade stays dark (empty JWKS, minting
raises) rather than serving a broken surface.

## Cadence

- Routine: quarterly.
- On suspected compromise: rotate immediately and shorten the grace window to
  just above the token TTL + verifier cache TTL (do not skip the grace, or
  in-flight tokens 401 mid-request).

## Rotation procedure

1. **Generate the new key B.**
   `docker exec unicorn-brigade python scripts/gen_brigade_jwt_key.py --kid brigade-<period>-rsa-02`
   Store the printed private PEM in the secret store. Never commit it.

2. **Promote B to current, demote A to previous.** In the instance secret
   store / `.env`:
   - `BRIGADE_JWT_PRIVATE_KEY` = B, `BRIGADE_JWT_KID` = B's kid
   - `BRIGADE_JWT_PRIVATE_KEY_PREV` = A, `BRIGADE_JWT_KID_PREV` = A's kid

3. **Reload the container.** `docker compose up -d unicorn-brigade`.
   Use `up -d`, NOT `restart`. `docker compose restart` reuses the existing
   container env and will NOT pick up the new `.env`.

4. **Confirm the JWKS now publishes both keys.**
   `curl -s https://brigade.unicorncommander.ai/.well-known/jwks.json | jq '.keys[].kid'`
   should list B's kid and A's kid. New tokens are signed by B; tokens already
   in flight signed by A still verify (the grace window).

5. **Hold the grace window.** Keep A published for at least
   `max(token TTL = 5 min) + (verifier JWKS cache TTL = 24 h) + clock skew`.
   Practically: hold A for **several days**, not hours, so every verifier's
   cached JWKS has refreshed past the rotation. Quarterly cadence makes this
   cheap.

6. **Drop A.** Unset `BRIGADE_JWT_PRIVATE_KEY_PREV` / `BRIGADE_JWT_KID_PREV`,
   `docker compose up -d unicorn-brigade`. JWKS now publishes only B.

7. **PROOF (do not declare rotation complete without this).** A token signed by
   the now-removed key A must FAIL verification everywhere, the verifier looks
   up A's `kid`, does not find it in the JWKS, and returns 401. This is the
   property that makes rotation meaningful: old keys actually stop working, not
   just "a new key exists." Verified mechanically by
   `test_rotation_drill.py::test_rotation_drill_seven_steps` step 7.

## What to monitor during the overlap

- **Verifier 401 rate.** A spike means a verifier is not refreshing its JWKS on
  an unknown `kid`, investigate that app's verifier, do not drop A yet.
- **`federation_proxy_call` logs** (`app/federation/mcp_gateway.py`), watch the
  `status` field for a rise in upstream auth failures.
- **JWKS fetch errors** in per-app logs during the window.

## Safety rules

- Never drop the **current** key.
- Never drop the **previous** key before the grace window exceeds the verifier
  cache TTL, doing so 401s in-flight tokens.
- Every kid is unique across all history, never reuse a `kid` (a recycled kid
  makes cache-holding verifiers try the wrong key).
