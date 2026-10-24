"""Client IP behind Cloudflare → Coolify's Traefik → app (decisions section 3, spec-device-auth.md).

1. Peer not a trusted proxy → the peer is the client; forwarding headers are ignored.
2. Otherwise the rightmost X-Forwarded-For entry (the address that connected to Traefik).
3. If that address is Cloudflare's, CF-Connecting-IP (when a valid IP) is the client.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable

from starlette.requests import Request

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

# Private and loopback ranges: Traefik runs in Coolify's Docker network on the same host.
DEFAULT_TRUSTED_PROXIES = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "::1/128", "fc00::/7")

# https://www.cloudflare.com/ips-v4 and /ips-v6, fetched 2026-10-24. Update by hand when Cloudflare changes them.
CLOUDFLARE_RANGES = (
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
)


def networks(cidrs: Iterable[str]) -> tuple[IPNetwork, ...]:
    return tuple(ipaddress.ip_network(c.strip()) for c in cidrs if c.strip())


_CLOUDFLARE = networks(CLOUDFLARE_RANGES)


def _parse(value: str | None):
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _within(address, nets: tuple[IPNetwork, ...]) -> bool:
    return address is not None and any(address.version == n.version and address in n for n in nets)


def resolve(
    peer: str | None, forwarded_for: str | None, cf_connecting_ip: str | None, trusted: tuple[IPNetwork, ...]
) -> str:
    peer_ip = _parse(peer)
    if peer_ip is None:
        return peer or "unknown"
    if not _within(peer_ip, trusted):
        return str(peer_ip)
    entries = [e for e in (forwarded_for or "").split(",") if e.strip()]
    rightmost = _parse(entries[-1]) if entries else None
    if rightmost is None:
        return str(peer_ip)
    if _within(rightmost, _CLOUDFLARE):
        cf = _parse(cf_connecting_ip)
        if cf is not None:
            return str(cf)
    return str(rightmost)


def client_ip(request: Request) -> str:
    trusted = getattr(request.app.state, "trusted_proxies", None) or networks(DEFAULT_TRUSTED_PROXIES)
    peer = request.client.host if request.client else None
    return resolve(peer, request.headers.get("x-forwarded-for"), request.headers.get("cf-connecting-ip"), trusted)
