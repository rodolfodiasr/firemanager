"""SSRF (Server-Side Request Forgery) protection utility.

Validates outbound URLs/hosts before connecting to them to prevent:
- Access to cloud metadata endpoints (169.254.169.254)
- Access to internal RFC1918 networks
- Localhost/loopback requests
- Non-HTTP(S) schemes (file://, ftp://, etc.)

Usage:
    from app.utils.ssrf_guard import validate_outbound_host, validate_outbound_url

    validate_outbound_host("192.168.1.1")  # raises SSRFError for RFC1918
    validate_outbound_url("http://example.com/api")  # OK
    validate_outbound_url("file:///etc/passwd")  # raises SSRFError
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class SSRFError(ValueError):
    """Raised when a URL or host is blocked by SSRF protection."""


# Cloud metadata and link-local ranges to block
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),        # RFC1918 private
    ipaddress.ip_network("172.16.0.0/12"),      # RFC1918 private
    ipaddress.ip_network("192.168.0.0/16"),     # RFC1918 private
    ipaddress.ip_network("127.0.0.0/8"),        # Loopback
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local + AWS/GCP metadata
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]

_ALLOWED_SCHEMES = {"http", "https"}


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return False


def validate_outbound_host(host: str, resolve_dns: bool = False) -> None:
    """Check that host is not an internal/RFC1918/loopback address.

    Args:
        host: Hostname or IP address string.
        resolve_dns: If True, also resolve the hostname and check the resolved IP.
                     Disabled by default to avoid DNS latency in hot paths.

    Raises:
        SSRFError: If the host is blocked.
    """
    if not host:
        raise SSRFError("Host vazio não é permitido")

    # Direct IP check
    if _is_blocked_ip(host):
        raise SSRFError(
            f"Conexão bloqueada: '{host}' pertence a uma faixa de IP privada ou reservada "
            "(RFC1918, loopback, link-local). Use somente hosts públicos."
        )

    # DNS resolution check (optional, catches DNS rebinding)
    if resolve_dns:
        try:
            resolved_ips = {info[4][0] for info in socket.getaddrinfo(host, None)}
            for ip in resolved_ips:
                if _is_blocked_ip(ip):
                    raise SSRFError(
                        f"Conexão bloqueada: '{host}' resolve para o IP privado '{ip}'."
                    )
        except SSRFError:
            raise
        except OSError:
            pass  # DNS failure is handled by the connector, not here


def validate_outbound_url(url: str, resolve_dns: bool = False) -> None:
    """Validate a full URL for SSRF safety.

    Checks:
    - Scheme must be http or https
    - Host must not be RFC1918/loopback/link-local
    - No credentials embedded in URL (user:pass@host)

    Raises:
        SSRFError: If the URL fails any check.
    """
    if not url:
        raise SSRFError("URL vazia não é permitida")

    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise SSRFError(
            f"Scheme '{parsed.scheme}' não é permitido. Use http ou https."
        )

    if parsed.username or parsed.password:
        raise SSRFError(
            "Credenciais embutidas na URL não são permitidas (user:pass@host). "
            "Use cabeçalhos de autenticação."
        )

    host = parsed.hostname or ""
    validate_outbound_host(host, resolve_dns=resolve_dns)
