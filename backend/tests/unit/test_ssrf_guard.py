"""Unit tests for app.utils.ssrf_guard — SSRF protection.

Validates that internal/private/reserved IPs and dangerous URL patterns
are blocked before any outbound connection is made.
"""
import pytest

from app.utils.ssrf_guard import SSRFError, validate_outbound_host, validate_outbound_url


class TestValidateOutboundHostBlocked:
    """All RFC1918, loopback, link-local and metadata IPs must be blocked."""

    def test_rfc1918_10_0_0_1(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("10.0.0.1")

    def test_rfc1918_10_255_255_255(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("10.255.255.255")

    def test_rfc1918_172_16_0_1(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("172.16.0.1")

    def test_rfc1918_172_31_255_254(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("172.31.255.254")

    def test_rfc1918_172_middle_range(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("172.20.100.50")

    def test_rfc1918_192_168_0_1(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("192.168.0.1")

    def test_rfc1918_192_168_100_200(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("192.168.100.200")

    def test_loopback_127_0_0_1(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("127.0.0.1")

    def test_loopback_127_127_127_127(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("127.127.127.127")

    def test_loopback_127_0_0_254(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("127.0.0.254")

    def test_link_local_169_254_0_1(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("169.254.0.1")

    def test_aws_metadata_169_254_169_254(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("169.254.169.254")

    def test_gcp_metadata_169_254_169_253(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("169.254.169.253")

    def test_ipv6_loopback(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("::1")

    def test_ipv6_link_local_fe80(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("fe80::1")

    def test_ipv6_unique_local_fc00(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("fc00::1")

    def test_ipv6_unique_local_fd00(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("fd00::1")

    def test_empty_host_raises(self):
        with pytest.raises(SSRFError):
            validate_outbound_host("")


class TestValidateOutboundHostAllowed:
    """Public IPs must pass through without exception."""

    def test_google_dns_8_8_8_8(self):
        validate_outbound_host("8.8.8.8")  # must not raise

    def test_cloudflare_dns_1_1_1_1(self):
        validate_outbound_host("1.1.1.1")

    def test_public_200_range(self):
        validate_outbound_host("200.200.200.200")

    def test_public_45_range(self):
        validate_outbound_host("45.90.10.1")

    def test_public_54_range(self):
        validate_outbound_host("54.239.192.1")


class TestValidateOutboundUrlBlocked:
    """Dangerous URLs must be blocked regardless of format."""

    def test_private_ip_in_http_url(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://10.0.0.1/api")

    def test_private_ip_in_https_url(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("https://192.168.1.100/admin")

    def test_loopback_in_url(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://127.0.0.1:8080/health")

    def test_metadata_endpoint_in_url(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://169.254.169.254/latest/meta-data/")

    def test_file_scheme_blocked(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("file:///etc/passwd")

    def test_ftp_scheme_blocked(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("ftp://files.example.com/data")

    def test_gopher_scheme_blocked(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("gopher://evil.example.com/")

    def test_embedded_credentials_blocked(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://admin:secret@example.com/api")

    def test_embedded_username_only_blocked(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://user@example.com/api")

    def test_empty_url_raises(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("")

    def test_link_local_in_url(self):
        with pytest.raises(SSRFError):
            validate_outbound_url("http://169.254.0.50/api")


class TestValidateOutboundUrlAllowed:
    """Valid external URLs must pass without exception."""

    def test_valid_https_api(self):
        validate_outbound_url("https://api.anthropic.com/v1/messages")

    def test_valid_http_endpoint(self):
        validate_outbound_url("http://example.com/api")

    def test_valid_url_with_port(self):
        validate_outbound_url("https://external.service.com:8443/path")

    def test_valid_url_with_path_and_query(self):
        validate_outbound_url("https://api.shodan.io/shodan/host/8.8.8.8?key=abc")
