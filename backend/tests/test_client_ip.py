"""Client-IP rule (BUILDPLAN 1.10.6, decisions section 3)."""

import pytest

from app.security.client_ip import DEFAULT_TRUSTED_PROXIES, networks, resolve

TRUSTED = networks(DEFAULT_TRUSTED_PROXIES)
TRAEFIK = "10.0.1.5"
CLOUDFLARE = "172.70.1.2"  # inside 172.64.0.0/13
VISITOR = "203.0.113.9"


@pytest.mark.parametrize(
    ("peer", "xff", "cf", "expected"),
    [
        (TRAEFIK, CLOUDFLARE, VISITOR, VISITOR),  # normal: client → Cloudflare → Traefik
        (TRAEFIK, f"6.6.6.6, {CLOUDFLARE}", VISITOR, VISITOR),  # forged left entries are irrelevant
        (TRAEFIK, "198.51.100.4", "6.6.6.6", "198.51.100.4"),  # direct to VPS IP: spoofed CF header ignored
        (TRAEFIK, "198.51.100.4, 1.2.3.4", None, "1.2.3.4"),  # rightmost entry wins
        ("198.51.100.4", CLOUDFLARE, "6.6.6.6", "198.51.100.4"),  # peer not a trusted proxy: headers ignored
        (TRAEFIK, CLOUDFLARE, "not-an-ip", CLOUDFLARE),
        (TRAEFIK, None, VISITOR, TRAEFIK),
        (TRAEFIK, "2606:4700::1", "2001:db8::7", "2001:db8::7"),  # Cloudflare over IPv6
        ("127.0.0.1", "garbage", None, "127.0.0.1"),
    ],
)
def test_resolve(peer, xff, cf, expected):
    assert resolve(peer, xff, cf, TRUSTED) == expected


def test_custom_trusted_proxies():
    only = networks(["10.9.0.0/16"])
    assert resolve(TRAEFIK, CLOUDFLARE, VISITOR, only) == TRAEFIK
    assert resolve("10.9.1.1", CLOUDFLARE, VISITOR, only) == VISITOR
