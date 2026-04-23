from __future__ import annotations

from contextlib import contextmanager
import ipaddress
from urllib.parse import urljoin, urlsplit

import requests


REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
HTTP_SCHEMES = {"http", "https"}


class RemoteNetworkSafetyError(RuntimeError):
    """Raised when a user-supplied remote URL crosses the runtime network boundary."""


def _normalize_hostname(hostname: str) -> str:
    return hostname.strip().rstrip(".").lower()


def _is_ip_literal(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def _is_public_ip_literal(hostname: str) -> bool:
    ip = ipaddress.ip_address(hostname)
    return bool(ip.is_global)


def validate_public_http_url(url: str, *, context: str = "remote media URL") -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in HTTP_SCHEMES:
        raise RemoteNetworkSafetyError(f"{context} must use http or https: {url}")
    if parsed.username or parsed.password:
        raise RemoteNetworkSafetyError(f"{context} cannot include embedded credentials: {url}")
    if not parsed.hostname:
        raise RemoteNetworkSafetyError(f"{context} is missing a hostname: {url}")

    hostname = _normalize_hostname(parsed.hostname)
    if hostname in {"localhost"}:
        raise RemoteNetworkSafetyError(f"{context} cannot target localhost: {url}")
    if hostname.endswith((".local", ".localdomain", ".home.arpa", ".internal")):
        raise RemoteNetworkSafetyError(f"{context} cannot target a local/private hostname: {url}")
    if "." not in hostname and not _is_ip_literal(hostname):
        raise RemoteNetworkSafetyError(f"{context} must use a public hostname: {url}")
    if _is_ip_literal(hostname) and not _is_public_ip_literal(hostname):
        raise RemoteNetworkSafetyError(f"{context} cannot target a private or reserved IP: {url}")

    return url


@contextmanager
def open_safe_public_stream(
    url: str,
    *,
    timeout: int | float = 60,
    max_redirects: int = 5,
):
    current_url = validate_public_http_url(url)
    response = None
    redirects_followed = 0

    try:
        while True:
            response = requests.get(current_url, stream=True, timeout=timeout, allow_redirects=False)
            validate_public_http_url(response.url or current_url, context="remote media response URL")

            if response.status_code not in REDIRECT_STATUS_CODES:
                response.raise_for_status()
                yield response
                return

            location = response.headers.get("Location")
            response.close()
            response = None
            if not location:
                raise RemoteNetworkSafetyError(f"remote media redirect is missing a Location header: {current_url}")

            redirects_followed += 1
            if redirects_followed > max_redirects:
                raise RemoteNetworkSafetyError(f"remote media redirect chain exceeded {max_redirects} hops: {url}")

            current_url = validate_public_http_url(
                urljoin(current_url, location),
                context="remote media redirect target",
            )
    finally:
        if response is not None:
            response.close()


__all__ = [
    "RemoteNetworkSafetyError",
    "open_safe_public_stream",
    "validate_public_http_url",
]
