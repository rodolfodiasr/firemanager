"""Tests for Sophos SFOS XML API connector — XML helpers and connector utilities."""
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, patch

import pytest

from app.connectors.sophos import (
    SophosConnector,
    _e,
    _login_ok,
    _op_status,
    _parse,
    _to_xml,
)


# ── Module-level XML helpers ──────────────────────────────────────────────────

class TestXmlElementHelper:
    def test_creates_element_with_text(self):
        el = _e("Name", "MyRule")
        assert el.tag == "Name"
        assert el.text == "MyRule"

    def test_creates_element_with_child_elements(self):
        el = _e("Login", Username="admin", Password="secret")
        assert el.find("Username").text == "admin"
        assert el.find("Password").text == "secret"

    def test_creates_empty_element_when_no_args(self):
        el = _e("FirewallRule")
        assert el.tag == "FirewallRule"
        assert el.text is None
        assert len(list(el)) == 0

    def test_to_xml_returns_string(self):
        el = ET.Element("Test")
        result = _to_xml(el)
        assert isinstance(result, str)
        assert "<Test" in result

    def test_parse_round_trip(self):
        original = _e("Rule", "my-rule")
        xml_str = _to_xml(original)
        parsed = _parse(xml_str)
        assert parsed.tag == "Rule"
        assert parsed.text == "my-rule"


class TestLoginOkHelper:
    def test_returns_true_on_authentication_successful(self):
        root = ET.fromstring(
            "<Response><Login>"
            "<status>Authentication Successful</status>"
            "</Login></Response>"
        )
        assert _login_ok(root) is True

    def test_returns_false_on_authentication_failure(self):
        root = ET.fromstring(
            "<Response><Login>"
            "<status>Authentication Failure</status>"
            "</Login></Response>"
        )
        assert _login_ok(root) is False

    def test_returns_false_on_missing_login_node(self):
        root = ET.fromstring("<Response/>")
        assert _login_ok(root) is False

    def test_returns_false_on_empty_status(self):
        root = ET.fromstring(
            "<Response><Login><status></status></Login></Response>"
        )
        assert _login_ok(root) is False


class TestOpStatusHelper:
    def test_returns_true_for_code_200(self):
        root = ET.fromstring(
            '<Response>'
            '<FirewallRule><Status code="200">Configuration applied</Status></FirewallRule>'
            '</Response>'
        )
        ok, msg = _op_status(root, "FirewallRule")
        assert ok is True
        assert "Configuration applied" in msg

    def test_returns_false_for_non_200_code(self):
        root = ET.fromstring(
            '<Response>'
            '<FirewallRule><Status code="500">Internal error</Status></FirewallRule>'
            '</Response>'
        )
        ok, msg = _op_status(root, "FirewallRule")
        assert ok is False
        assert "Internal error" in msg

    def test_returns_false_when_tag_missing(self):
        root = ET.fromstring("<Response/>")
        ok, msg = _op_status(root, "FirewallRule")
        assert ok is False
        assert "not found" in msg

    def test_works_for_nat_rule_tag(self):
        root = ET.fromstring(
            '<Response><NATRule><Status code="200">OK</Status></NATRule></Response>'
        )
        ok, _ = _op_status(root, "NATRule")
        assert ok is True

    def test_works_for_static_route_tag(self):
        root = ET.fromstring(
            '<Response><StaticRoute><Status code="200">OK</Status></StaticRoute></Response>'
        )
        ok, _ = _op_status(root, "StaticRoute")
        assert ok is True


# ── SophosConnector static helpers ───────────────────────────────────────────

class TestSafeNameHelper:
    def setup_method(self):
        self.c = SophosConnector(
            host="https://192.168.1.1:4444", username="admin", password="secret"
        )

    def test_adds_default_fm_prefix(self):
        assert self.c._safe_name("MyRule").startswith("FM-")

    def test_custom_prefix_applied(self):
        assert self.c._safe_name("MyGroup", "FM-G-").startswith("FM-G-")

    def test_sanitizes_dots_and_slashes(self):
        name = self.c._safe_name("192.168.1.0/24", "FM-H-")
        assert "." not in name
        assert "/" not in name

    def test_truncates_at_60_chars(self):
        long_name = self.c._safe_name("A" * 200)
        assert len(long_name) <= 60

    def test_truncates_including_prefix(self):
        name = self.c._safe_name("X" * 100, "FM-LONGPREFIX-")
        assert len(name) <= 60


class TestNetPartsHelper:
    def setup_method(self):
        self.c = SophosConnector(
            host="https://192.168.1.1:4444", username="admin", password="secret"
        )

    def test_host_32_returns_ip_type(self):
        ip, mask, htype = self.c._net_parts("192.168.1.100/32")
        assert ip == "192.168.1.100"
        assert mask == "255.255.255.255"
        assert htype == "IP"

    def test_network_24_returns_network_type(self):
        ip, mask, htype = self.c._net_parts("10.0.0.0/24")
        assert ip == "10.0.0.0"
        assert mask == "255.255.255.0"
        assert htype == "Network"

    def test_network_16_returns_correct_mask(self):
        ip, mask, htype = self.c._net_parts("172.16.0.0/16")
        assert ip == "172.16.0.0"
        assert mask == "255.255.0.0"
        assert htype == "Network"

    def test_network_8_returns_correct_mask(self):
        ip, mask, htype = self.c._net_parts("10.0.0.0/8")
        assert ip == "10.0.0.0"
        assert mask == "255.0.0.0"
        assert htype == "Network"

    def test_invalid_cidr_falls_back_to_ip_type(self):
        ip, mask, htype = self.c._net_parts("not-an-ip")
        assert ip == "not-an-ip"
        assert htype == "IP"

    def test_normalizes_host_bits(self):
        # 192.168.1.5/24 → network address is 192.168.1.0
        ip, mask, htype = self.c._net_parts("192.168.1.5/24")
        assert ip == "192.168.1.0"
        assert htype == "Network"


class TestBuildRequest:
    def setup_method(self):
        self.c = SophosConnector(
            host="https://192.168.1.1:4444", username="admin", password="secret"
        )

    def test_root_tag_is_request(self):
        xml_str = self.c._build_request()
        root = ET.fromstring(xml_str)
        assert root.tag == "Request"

    def test_login_node_present(self):
        xml_str = self.c._build_request()
        root = ET.fromstring(xml_str)
        login = root.find("Login")
        assert login is not None

    def test_credentials_embedded_in_login(self):
        xml_str = self.c._build_request()
        root = ET.fromstring(xml_str)
        assert root.findtext("Login/Username") == "admin"
        assert root.findtext("Login/Password") == "secret"

    def test_operation_appended_after_login(self):
        get_op = ET.Element("Get")
        ET.SubElement(get_op, "FirewallRule")
        xml_str = self.c._build_request(get_op)
        root = ET.fromstring(xml_str)
        assert root.find("Get") is not None
        assert root.find("Get/FirewallRule") is not None

    def test_multiple_operations_all_appended(self):
        op1 = ET.Element("Get")
        ET.SubElement(op1, "FirewallRule")
        op2 = ET.Element("Get")
        ET.SubElement(op2, "NATRule")
        xml_str = self.c._build_request(op1, op2)
        root = ET.fromstring(xml_str)
        assert len(root.findall("Get")) == 2

    def test_endpoint_built_from_host(self):
        assert self.c._endpoint == "https://192.168.1.1:4444/webconsole/APIController"

    def test_trailing_slash_stripped_from_host(self):
        c = SophosConnector(host="https://1.2.3.4/", username="u", password="p")
        assert not c.base_url.endswith("/")
        assert c._endpoint == "https://1.2.3.4/webconsole/APIController"


# ── _ensure_iphost async helper ───────────────────────────────────────────────

async def test_ensure_iphost_returns_any_for_any():
    c = SophosConnector(host="https://1.2.3.4", username="u", password="p")
    with patch.object(c, "_post", new_callable=AsyncMock) as mock_post:
        result = await c._ensure_iphost("any")
    mock_post.assert_not_called()
    assert result == "Any"


async def test_ensure_iphost_returns_any_for_empty_string():
    c = SophosConnector(host="https://1.2.3.4", username="u", password="p")
    with patch.object(c, "_post", new_callable=AsyncMock) as mock_post:
        result = await c._ensure_iphost("")
    mock_post.assert_not_called()
    assert result == "Any"


async def test_ensure_iphost_returns_any_for_default_route():
    c = SophosConnector(host="https://1.2.3.4", username="u", password="p")
    with patch.object(c, "_post", new_callable=AsyncMock) as mock_post:
        result = await c._ensure_iphost("0.0.0.0/0")
    mock_post.assert_not_called()
    assert result == "Any"


async def test_ensure_iphost_calls_post_for_specific_ip():
    c = SophosConnector(host="https://1.2.3.4", username="u", password="p")
    mock_root = ET.fromstring(
        '<Response>'
        '<Login><status>Authentication Successful</status></Login>'
        '<IPHost><Status code="200">OK</Status></IPHost>'
        '</Response>'
    )
    with patch.object(c, "_post", new_callable=AsyncMock, return_value=mock_root):
        name = await c._ensure_iphost("192.168.1.100/32")
    assert name.startswith("FM-H-")


async def test_ensure_iphost_swallows_duplicate_error():
    """_ensure_iphost ignores errors (object may already exist)."""
    c = SophosConnector(host="https://1.2.3.4", username="u", password="p")
    with patch.object(c, "_post", new_callable=AsyncMock, side_effect=Exception("duplicate")):
        name = await c._ensure_iphost("10.0.0.1/32")
    assert name.startswith("FM-H-")


async def test_ensure_iphost_host32_uses_ip_type_in_xml():
    """Verify the XML sent for a /32 host uses HostType=IP."""
    c = SophosConnector(host="https://1.2.3.4", username="u", password="p")
    captured_ops: list[ET.Element] = []

    async def capture(*ops: ET.Element) -> ET.Element:
        captured_ops.extend(ops)
        return ET.fromstring(
            '<Response><Login><status>Authentication Successful</status></Login></Response>'
        )

    with patch.object(c, "_post", side_effect=capture):
        await c._ensure_iphost("10.10.10.10/32")

    assert captured_ops, "Expected _post to be called"
    xml_str = _to_xml(captured_ops[0])
    assert "IP" in xml_str
    assert "Network" not in xml_str
