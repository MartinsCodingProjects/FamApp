from datetime import timedelta

import jwt
import pytest

from app.security.cf_access import AccessVerifier
from tests.cf_keys import AUD, TEAM, FakeTeam


@pytest.fixture
def team():
    return FakeTeam()


@pytest.fixture
def verifier(team, clock):
    return AccessVerifier(TEAM, AUD, clock, fetch=team.jwks)


def test_valid_token(verifier, team, clock):
    assert verifier.verify(team.token(clock))


@pytest.mark.parametrize("token", [None, "", "not-a-jwt", "a.b.c"])
def test_missing_or_garbage(verifier, token):
    assert not verifier.verify(token)


def test_wrong_audience_or_issuer(verifier, team, clock):
    assert not verifier.verify(team.token(clock, aud="other-app"))
    assert not verifier.verify(team.token(clock, iss="https://evil.cloudflareaccess.com"))


def test_expiry_uses_the_clock(verifier, team, clock):
    token = team.token(clock, lifetime=timedelta(minutes=5))
    clock.advance(minutes=5, seconds=59)
    assert verifier.verify(token)  # within 60 s leeway
    clock.advance(seconds=2)
    assert not verifier.verify(token)


def test_not_yet_valid(verifier, team, clock):
    token = team.token(clock, nbf=int((clock.now() + timedelta(minutes=5)).timestamp()))
    assert not verifier.verify(token)


def test_unsigned_or_symmetric_tokens_rejected(verifier, clock):
    payload = {"aud": [AUD], "iss": f"https://{TEAM}", "exp": int((clock.now() + timedelta(hours=1)).timestamp())}
    assert not verifier.verify(jwt.encode(payload, "s" * 32, algorithm="HS256", headers={"kid": "key-1"}))
    assert not verifier.verify(jwt.encode(payload, None, algorithm="none", headers={"kid": "key-1"}))


def test_foreign_key_rejected(verifier, clock):
    other = FakeTeam()  # same kid, different key
    assert not verifier.verify(other.token(clock))


def test_keys_are_cached_and_refetched_for_new_kid(verifier, team, clock):
    assert verifier.verify(team.token(clock))
    assert verifier.verify(team.token(clock))
    assert team.fetches == 1
    team.add_key("key-2")  # Cloudflare rotates keys
    clock.advance(seconds=30)
    assert not verifier.verify(team.token(clock, kid="key-2"))  # refetch rate-limited
    clock.advance(seconds=31)
    assert verifier.verify(team.token(clock, kid="key-2"))
    assert team.fetches == 2
    clock.advance(hours=1, seconds=1)
    assert verifier.verify(team.token(clock))
    assert team.fetches == 3  # cache expired


def test_unreachable_key_endpoint_fails_closed(verifier, team, clock):
    team.fail = True
    assert not verifier.verify(team.token(clock))


def test_cached_keys_survive_an_outage(verifier, team, clock):
    assert verifier.verify(team.token(clock))
    team.fail = True
    clock.advance(hours=2)
    assert verifier.verify(team.token(clock))
