"""Client IP of a request. Placeholder until 1.10.6 implements the Traefik / Cloudflare rule
(decisions section 3); every caller already goes through this function."""

from starlette.requests import Request


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
