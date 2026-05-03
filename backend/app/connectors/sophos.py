"""Sophos Firewall (SFOS) XML API connector.

Auth: username + password embedded in every XML request (no session tokens).
Endpoint: POST https://<host>:<port>/webconsole/APIController
Payload form-field: reqxml=<Request>...</Request>

API must be enabled in Administration > API and the caller IP must be whitelisted.
All entities are identified by name — no UUIDs. FM-prefixed names are used for
objects created by FireManager to avoid collisions with manually created objects.
"""
import ipaddress
import re as _re
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from app.connectors.base import (
    BaseConnector,
    ConnectionResult,
    ExecutionResult,
    FirewallRule,
    GroupSpec,
    NatPolicy,
    NatSpec,
    RoutePolicy,
    RouteSpec,
    RuleSpec,
)


# ── XML helpers ───────────────────────────────────────────────────────────────

def _e(tag: str, text: str | None = None, **children: str) -> ET.Element:
    """Create an XML element with optional text or child elements."""
    el = ET.Element(tag)
    if text is not None:
        el.text = text
    for child_tag, child_text in children.items():
        c = ET.SubElement(el, child_tag)
        c.text = child_text
    return el


def _to_xml(el: ET.Element) -> str:
    return ET.tostring(el, encoding="unicode")


def _parse(text: str) -> ET.Element:
    return ET.fromstring(text)


def _login_ok(root: ET.Element) -> bool:
    status = root.findtext("Login/status", "")
    return "Authentication Successful" in status


def _op_status(root: ET.Element, tag: str) -> tuple[bool, str]:
    """Return (success, message) for a given operation tag in the response."""
    node = root.find(tag)
    if node is None:
        return False, f"Tag <{tag}> not found in response"
    code = node.findtext("Status/@code") or ""
    msg = node.findtext("Status") or ""
    # ET doesn't support attribute selectors — find Status element directly
    status_el = node.find("Status")
    if status_el is not None:
        code = status_el.get("code", "")
        msg = status_el.text or ""
    return code == "200", msg


# ── Connector ─────────────────────────────────────────────────────────────────

class SophosConnector(BaseConnector):
    """Sophos Firewall SFOS XML API connector.

    Credentials: auth_type=user_pass, username=<admin>, password=<password>.
    API whitelist: the FireManager server IP must be in Administration > API.
    """

    def __init__(self, host: str, username: str, password: str,
                 verify_ssl: bool = False) -> None:
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self._endpoint = f"{self.base_url}/webconsole/APIController"

    # ── internal ─────────────────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(verify=self.verify_ssl, timeout=30.0)

    def _build_request(self, *operations: ET.Element) -> str:
        """Wrap operations in a <Request><Login>...</Login>...</Request> envelope."""
        req = ET.Element("Request")
        login = ET.SubElement(req, "Login")
        ET.SubElement(login, "Username").text = self.username
        ET.SubElement(login, "Password").text = self.password
        for op in operations:
            req.append(op)
        return _to_xml(req)

    async def _post(self, *operations: ET.Element) -> ET.Element:
        xml_body = self._build_request(*operations)
        async with self._client() as client:
            resp = await client.post(
                self._endpoint,
                data={"reqxml": xml_body},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
        root = _parse(resp.text)
        if not _login_ok(root):
            status = root.findtext("Login/status", "Authentication failed")
            raise PermissionError(f"Sophos auth failed: {status}")
        return root

    # ── address-object helpers ────────────────────────────────────────────────

    @staticmethod
    def _safe_name(value: str, prefix: str = "FM-") -> str:
        """Sanitise a name for use as a Sophos object name (max 60 chars)."""
        return (prefix + _re.sub(r"[^A-Za-z0-9\-]", "-", value))[:60]

    @staticmethod
    def _net_parts(cidr: str) -> tuple[str, str, str]:
        """Return (ip, subnet_mask, host_type) for an IPHost object."""
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            if net.prefixlen == 32:
                return str(net.network_address), "255.255.255.255", "IP"
            return str(net.network_address), str(net.netmask), "Network"
        except ValueError:
            return cidr, "255.255.255.255", "IP"

    async def _ensure_iphost(self, cidr: str) -> str:
        """Return a Sophos IPHost name for the CIDR, creating the object if needed.

        Returns 'Any' for wildcard addresses.
        """
        if not cidr or cidr.lower() in ("any", "0.0.0.0/0", ""):
            return "Any"

        ip_addr, mask, host_type = self._net_parts(cidr)
        obj_name = self._safe_name(cidr.replace("/", "-").replace(".", "-"), "FM-H-")

        host_el = ET.Element("Host")
        ET.SubElement(host_el, "Name").text = obj_name
        ET.SubElement(host_el, "IPFamily").text = "IPv4"
        ET.SubElement(host_el, "HostType").text = host_type
        ET.SubElement(host_el, "IPAddress").text = ip_addr
        if host_type == "Network":
            ET.SubElement(host_el, "Subnet").text = mask

        set_op = ET.Element("Set")
        ip_host = ET.SubElement(set_op, "IPHost")
        ip_host.append(host_el)

        try:
            await self._post(set_op)
        except Exception:
            pass  # object may already exist — ignore duplicate errors

        return obj_name

    # ── test_connection ───────────────────────────────────────────────────────

    async def test_connection(self) -> ConnectionResult:
        start = time.monotonic()
        get_op = ET.Element("Get")
        ET.SubElement(get_op, "ApplianceAccess")
        try:
            root = await self._post(get_op)
            latency = (time.monotonic() - start) * 1000
            version = root.findtext("ApplianceAccess/FirmwareVersion") or \
                      root.findtext(".//FirmwareVersion") or "unknown"
            return ConnectionResult(success=True, latency_ms=latency, firmware_version=version)
        except PermissionError as exc:
            return ConnectionResult(success=False, error=str(exc))
        except Exception as exc:
            return ConnectionResult(success=False, error=str(exc))

    # ── firewall rules ────────────────────────────────────────────────────────

    async def list_rules(self) -> list[FirewallRule]:
        get_op = ET.Element("Get")
        ET.SubElement(get_op, "FirewallRule")
        root = await self._post(get_op)
        rules: list[FirewallRule] = []
        for rule in root.findall("FirewallRule/Rule"):
            name = rule.findtext("Name", "")
            status = rule.findtext("Status", "Enable")
            np = rule.find("NetworkPolicy")
            action = "accept"
            src = "any"
            dst = "any"
            service = "any"
            src_zone = ""
            dst_zone = ""
            if np is not None:
                action = np.findtext("Action", "Accept").lower()
                src = np.findtext("SourceNetworks/Network", "any")
                dst = np.findtext("DestinationNetworks/Network", "any")
                service = np.findtext("Services/Service", "any")
                src_zone = np.findtext("SourceZones/Zone", "")
                dst_zone = np.findtext("DestinationZones/Zone", "")
            rules.append(FirewallRule(
                rule_id=name,
                name=name,
                src=src,
                dst=dst,
                service=service,
                action=action,
                enabled=status.lower() == "enable",
                src_zone=src_zone,
                dst_zone=dst_zone,
                raw={"xml": _to_xml(rule)},
            ))
        return rules

    async def create_rule(self, spec: RuleSpec) -> ExecutionResult:
        src_obj = await self._ensure_iphost(spec.src_address)
        dst_obj = await self._ensure_iphost(spec.dst_address)

        action = "Drop" if spec.action in ("deny", "drop", "block", "reject") else "Accept"
        rule_name = self._safe_name(spec.name, "FM-")

        rule_el = ET.Element("Rule")
        ET.SubElement(rule_el, "Name").text = rule_name
        ET.SubElement(rule_el, "IPFamily").text = "IPv4"
        ET.SubElement(rule_el, "Status").text = "Enable"
        ET.SubElement(rule_el, "Position").text = "Top"
        ET.SubElement(rule_el, "PolicyType").text = "Network"
        ET.SubElement(rule_el, "LogTraffic").text = "Disable"

        np = ET.SubElement(rule_el, "NetworkPolicy")
        ET.SubElement(np, "Action").text = action

        src_zones = ET.SubElement(np, "SourceZones")
        ET.SubElement(src_zones, "Zone").text = spec.src_zone or "LAN"
        dst_zones = ET.SubElement(np, "DestinationZones")
        ET.SubElement(dst_zones, "Zone").text = spec.dst_zone or "WAN"

        src_nets = ET.SubElement(np, "SourceNetworks")
        ET.SubElement(src_nets, "Network").text = src_obj
        dst_nets = ET.SubElement(np, "DestinationNetworks")
        ET.SubElement(dst_nets, "Network").text = dst_obj

        svc_el = ET.SubElement(np, "Services")
        if spec.service and spec.service not in ("any", "Any", "ALL", ""):
            ET.SubElement(svc_el, "Service").text = spec.service
        else:
            ET.SubElement(svc_el, "Service").text = "Any"

        if spec.comment:
            ET.SubElement(rule_el, "Description").text = spec.comment[:255]

        set_op = ET.Element("Set")
        fw = ET.SubElement(set_op, "FirewallRule")
        fw.append(rule_el)

        try:
            root = await self._post(set_op)
            ok, msg = _op_status(root, "FirewallRule")
            return ExecutionResult(success=ok, rule_id=rule_name,
                                   error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    async def delete_rule(self, rule_id: str) -> ExecutionResult:
        remove_op = ET.Element("Remove")
        fw = ET.SubElement(remove_op, "FirewallRule")
        ET.SubElement(fw, "Name").text = rule_id
        try:
            root = await self._post(remove_op)
            ok, msg = _op_status(root, "FirewallRule")
            return ExecutionResult(success=ok, error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    async def edit_rule(self, rule_id: str, spec: RuleSpec) -> ExecutionResult:
        src_obj = await self._ensure_iphost(spec.src_address)
        dst_obj = await self._ensure_iphost(spec.dst_address)
        action = "Drop" if spec.action in ("deny", "drop", "block", "reject") else "Accept"

        rule_el = ET.Element("Rule")
        ET.SubElement(rule_el, "Name").text = rule_id

        np = ET.SubElement(rule_el, "NetworkPolicy")
        ET.SubElement(np, "Action").text = action

        if spec.src_zone:
            src_zones = ET.SubElement(np, "SourceZones")
            ET.SubElement(src_zones, "Zone").text = spec.src_zone
        if spec.dst_zone:
            dst_zones = ET.SubElement(np, "DestinationZones")
            ET.SubElement(dst_zones, "Zone").text = spec.dst_zone

        src_nets = ET.SubElement(np, "SourceNetworks")
        ET.SubElement(src_nets, "Network").text = src_obj
        dst_nets = ET.SubElement(np, "DestinationNetworks")
        ET.SubElement(dst_nets, "Network").text = dst_obj

        svc_el = ET.SubElement(np, "Services")
        ET.SubElement(svc_el, "Service").text = (
            spec.service if spec.service and spec.service not in ("any", "Any", "ALL", "") else "Any"
        )

        update_op = ET.Element("Update")
        fw = ET.SubElement(update_op, "FirewallRule")
        fw.append(rule_el)

        try:
            root = await self._post(update_op)
            ok, msg = _op_status(root, "FirewallRule")
            return ExecutionResult(success=ok, error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    # ── groups (IPHostGroup) ──────────────────────────────────────────────────

    async def create_group(self, spec: GroupSpec) -> ExecutionResult:
        group_name = self._safe_name(spec.name, "FM-G-")

        grp = ET.Element("IPHostGroup")
        host_grp = ET.SubElement(grp, "HostGroup")
        ET.SubElement(host_grp, "Name").text = group_name
        ET.SubElement(host_grp, "IPFamily").text = "IPv4"
        if spec.comment:
            ET.SubElement(host_grp, "Description").text = spec.comment[:255]

        hosts_el = ET.SubElement(host_grp, "HostList")
        for member in spec.members:
            obj_name = await self._ensure_iphost(member)
            ET.SubElement(hosts_el, "Host").text = obj_name

        set_op = ET.Element("Set")
        set_op.append(grp)

        try:
            root = await self._post(set_op)
            ok, msg = _op_status(root, "IPHostGroup")
            return ExecutionResult(success=ok, error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    # ── NAT policies ──────────────────────────────────────────────────────────

    async def list_nat_policies(self) -> list[NatPolicy]:
        get_op = ET.Element("Get")
        ET.SubElement(get_op, "NATRule")
        root = await self._post(get_op)
        result: list[NatPolicy] = []
        for rule in root.findall("NATRule/Rule"):
            name = rule.findtext("Name", "")
            result.append(NatPolicy(
                rule_id=name,
                name=name,
                inbound=rule.findtext("InboundInterface", ""),
                outbound=rule.findtext("OutboundInterface", ""),
                source=rule.findtext("OriginalSource", "any"),
                translated_source=rule.findtext("TranslatedSource", "original"),
                destination=rule.findtext("OriginalDestination", "any"),
                translated_destination=rule.findtext("TranslatedDestination", ""),
                service=rule.findtext("OriginalService", "any"),
                translated_service=rule.findtext("TranslatedService", "any"),
                enabled=rule.findtext("Status", "Enable").lower() == "enable",
                comment=rule.findtext("Description", ""),
                raw={"xml": _to_xml(rule)},
            ))
        return result

    async def create_nat_policy(self, spec: NatSpec) -> ExecutionResult:
        rule_name = self._safe_name(spec.name or spec.comment or "rule", "FM-NAT-")
        nat_type = "DNAT"
        if spec.translated_source.lower() == "masquerade":
            nat_type = "Masquerade"
        elif spec.translated_source not in ("original", "Original", ""):
            nat_type = "SNAT"

        rule_el = ET.Element("Rule")
        ET.SubElement(rule_el, "Name").text = rule_name
        ET.SubElement(rule_el, "Status").text = "Enable" if spec.enable else "Disable"
        ET.SubElement(rule_el, "Type").text = nat_type
        ET.SubElement(rule_el, "OriginalSource").text = spec.source or "Any"
        ET.SubElement(rule_el, "OriginalDestination").text = spec.destination or "Any"
        ET.SubElement(rule_el, "TranslatedDestination").text = spec.translated_destination or "Any"
        ET.SubElement(rule_el, "OriginalService").text = spec.service or "Any"
        ET.SubElement(rule_el, "TranslatedService").text = spec.translated_service or "Any"
        if spec.inbound_interface:
            ET.SubElement(rule_el, "InboundInterface").text = spec.inbound_interface
        if spec.outbound_interface:
            ET.SubElement(rule_el, "OutboundInterface").text = spec.outbound_interface
        if spec.name or spec.comment:
            ET.SubElement(rule_el, "Description").text = (spec.comment or spec.name or "")[:255]

        set_op = ET.Element("Set")
        nat = ET.SubElement(set_op, "NATRule")
        nat.append(rule_el)

        try:
            root = await self._post(set_op)
            ok, msg = _op_status(root, "NATRule")
            return ExecutionResult(success=ok, error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    async def delete_nat_policy(self, rule_id: str) -> ExecutionResult:
        remove_op = ET.Element("Remove")
        nat = ET.SubElement(remove_op, "NATRule")
        ET.SubElement(nat, "Name").text = rule_id
        try:
            root = await self._post(remove_op)
            ok, msg = _op_status(root, "NATRule")
            return ExecutionResult(success=ok, error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    # ── static routes ─────────────────────────────────────────────────────────

    async def list_route_policies(self) -> list[RoutePolicy]:
        get_op = ET.Element("Get")
        ET.SubElement(get_op, "StaticRoute")
        root = await self._post(get_op)
        result: list[RoutePolicy] = []
        for route in root.findall("StaticRoute/Route"):
            name = route.findtext("Name", "")
            dest_ip = route.findtext("DestinationIP", "")
            prefix = route.findtext("Prefix", "0")
            destination = f"{dest_ip}/{prefix}" if dest_ip else ""
            result.append(RoutePolicy(
                rule_id=name,
                name=name,
                interface=route.findtext("Interface", ""),
                source="any",
                destination=destination,
                service="any",
                gateway=route.findtext("DefaultGateway", ""),
                metric=int(route.findtext("Distance", "1") or 1),
                distance=int(route.findtext("Distance", "1") or 1),
                route_type="static",
                comment=route.findtext("Description", ""),
                enabled=route.findtext("Status", "Enable").lower() == "enable",
                raw={"xml": _to_xml(route)},
            ))
        return result

    async def create_route_policy(self, spec: RouteSpec) -> ExecutionResult:
        route_name = self._safe_name(
            spec.name or spec.destination or "route", "FM-RT-"
        )
        try:
            net = ipaddress.ip_network(spec.destination, strict=False)
            dest_ip = str(net.network_address)
            prefix = str(net.prefixlen)
        except ValueError:
            dest_ip = spec.destination
            prefix = "32"

        route_el = ET.Element("Route")
        ET.SubElement(route_el, "Name").text = route_name
        ET.SubElement(route_el, "IPFamily").text = "IPv4"
        ET.SubElement(route_el, "DestinationIP").text = dest_ip
        ET.SubElement(route_el, "Prefix").text = prefix
        ET.SubElement(route_el, "DefaultGateway").text = spec.gateway
        ET.SubElement(route_el, "Distance").text = str(spec.distance or spec.metric or 1)
        ET.SubElement(route_el, "Status").text = "Enable"
        if spec.comment:
            ET.SubElement(route_el, "Description").text = spec.comment[:255]

        set_op = ET.Element("Set")
        sr = ET.SubElement(set_op, "StaticRoute")
        sr.append(route_el)

        try:
            root = await self._post(set_op)
            ok, msg = _op_status(root, "StaticRoute")
            return ExecutionResult(success=ok, rule_id=route_name,
                                   error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    async def delete_route_policy(self, rule_id: str) -> ExecutionResult:
        remove_op = ET.Element("Remove")
        sr = ET.SubElement(remove_op, "StaticRoute")
        ET.SubElement(sr, "Name").text = rule_id
        try:
            root = await self._post(remove_op)
            ok, msg = _op_status(root, "StaticRoute")
            return ExecutionResult(success=ok, error=None if ok else msg)
        except Exception as exc:
            return ExecutionResult(success=False, error=str(exc))

    # ── config snapshot ───────────────────────────────────────────────────────

    async def get_config_snapshot(self) -> str:
        get_op = ET.Element("Get")
        for tag in ("FirewallRule", "NATRule", "StaticRoute", "IPHost", "IPHostGroup"):
            ET.SubElement(get_op, tag)
        try:
            root = await self._post(get_op)
            return ET.tostring(root, encoding="unicode", indent="  " if hasattr(ET, "indent") else None)
        except Exception as exc:
            return f"Error fetching snapshot: {exc}"

    # ── security status ───────────────────────────────────────────────────────

    async def get_security_status(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        async def _get_section(tag: str, key: str) -> None:
            get_op = ET.Element("Get")
            ET.SubElement(get_op, tag)
            try:
                root = await self._post(get_op)
                nodes = root.findall(f"{tag}/*")
                result[key] = [
                    {child.tag: child.text for child in node} for node in nodes
                ]
            except Exception:
                result[key] = []

        await _get_section("IPSPolicy", "ips_policies")
        await _get_section("AntiVirusPolicy", "av_policies")
        await _get_section("WebFilterPolicy", "webfilter_policies")
        await _get_section("ApplicationFilterPolicy", "app_filter_policies")
        await _get_section("Interface", "interfaces")
        await _get_section("VPNIPSecPolicy", "ipsec_policies")
        await _get_section("RemoteAccessPolicy", "ssl_vpn_policies")

        # firmware version via ApplianceAccess
        get_fw = ET.Element("Get")
        ET.SubElement(get_fw, "ApplianceAccess")
        try:
            root = await self._post(get_fw)
            result["firmware"] = root.findtext(".//FirmwareVersion", "unknown")
            result["model"] = root.findtext(".//Model", "unknown")
        except Exception:
            result["firmware"] = "unknown"

        return result
