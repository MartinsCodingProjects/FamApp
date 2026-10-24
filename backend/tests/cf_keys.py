"""Locally generated RSA keys and tokens imitating Cloudflare Access (no network, no real keys)."""

from __future__ import annotations

import json
from datetime import timedelta

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

TEAM = "famapp-test.cloudflareaccess.com"
AUD = "test-aud"


class FakeTeam:
    def __init__(self) -> None:
        self.keys: dict[str, rsa.RSAPrivateKey] = {}
        self.fetches = 0
        self.fail = False
        self.add_key("key-1")

    def add_key(self, kid: str) -> None:
        self.keys[kid] = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def jwks(self, url: str) -> dict:
        assert url == f"https://{TEAM}/cdn-cgi/access/certs"
        self.fetches += 1
        if self.fail:
            raise OSError("unreachable")
        keys = []
        for kid, key in self.keys.items():
            jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
            keys.append({**jwk, "kid": kid, "alg": "RS256", "use": "sig"})
        return {"keys": keys}

    def token(
        self,
        clock,
        kid: str = "key-1",
        aud: str = AUD,
        iss: str | None = None,
        lifetime: timedelta = timedelta(hours=1),
        **claims,
    ) -> str:
        now = clock.now()
        payload = {
            "aud": [aud],
            "iss": iss or f"https://{TEAM}",
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + lifetime).timestamp()),
            "email": "admin@example.invalid",
            **claims,
        }
        return jwt.encode(payload, self.keys[kid], algorithm="RS256", headers={"kid": kid})
