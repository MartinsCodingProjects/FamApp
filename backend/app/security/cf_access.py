"""Cloudflare Access JWT check for the admin host (decisions section 3, spec-backend-skeleton.md).

Missing or invalid `Cf-Access-Jwt-Assertion` → 404. Keys come from the team's JWKS endpoint,
cached for an hour; an unknown key ID triggers at most one refetch per minute. Time comes
from the Clock, so expiry is testable.
"""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from datetime import timedelta

import httpx2
import jwt
from jwt.algorithms import RSAAlgorithm

from app.clock import Clock

log = logging.getLogger(__name__)
HEADER = "cf-access-jwt-assertion"
CACHE_TTL = timedelta(hours=1)
REFETCH_MIN_INTERVAL = timedelta(seconds=60)
LEEWAY = timedelta(seconds=60)

KeyFetcher = Callable[[str], dict]


def fetch_jwks(url: str) -> dict:
    response = httpx2.get(url, timeout=5.0)
    response.raise_for_status()
    return response.json()


class AccessVerifier:
    def __init__(self, team_domain: str, audience: str, clock: Clock, fetch: KeyFetcher = fetch_jwks) -> None:
        self.issuer = f"https://{team_domain}"
        self.certs_url = f"{self.issuer}/cdn-cgi/access/certs"
        self.audience = audience
        self.clock = clock
        self.fetch = fetch
        self._keys: dict[str, object] = {}
        self._fetched_at = None
        self._lock = threading.Lock()

    def _refresh(self, force: bool) -> None:
        now = self.clock.now()
        with self._lock:
            age = None if self._fetched_at is None else now - self._fetched_at
            if age is not None and (age < REFETCH_MIN_INTERVAL or (not force and age < CACHE_TTL)):
                return
            try:
                jwks = self.fetch(self.certs_url)
                keys = {k["kid"]: RSAAlgorithm.from_jwk(json.dumps(k)) for k in jwks.get("keys", []) if "kid" in k}
            except Exception:
                log.warning("could not fetch Cloudflare Access keys", exc_info=True)
                self._fetched_at = now  # back off; keep old keys
                return
            self._keys = keys
            self._fetched_at = now

    def _key_for(self, kid: str):
        self._refresh(force=False)
        if kid not in self._keys:
            self._refresh(force=True)
        return self._keys.get(kid)

    def verify(self, token: str | None) -> bool:
        if not token:
            return False
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not header.get("kid"):
                return False
            key = self._key_for(header["kid"])
            if key is None:
                return False
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                    "require": ["exp", "aud", "iss"],
                },
            )
        except jwt.PyJWTError:
            return False
        now = self.clock.now().timestamp()
        leeway = LEEWAY.total_seconds()
        if not isinstance(claims.get("exp"), int | float) or now > claims["exp"] + leeway:
            return False
        nbf = claims.get("nbf")
        return not (isinstance(nbf, int | float) and now < nbf - leeway)
