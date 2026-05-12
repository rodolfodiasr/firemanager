"""NVD (National Vulnerability Database) integration — CVE sync and version matching."""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

import httpx

from app.config import settings

NVD_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

# Vendor → NVD keyword/CPE vendor mapping
VENDOR_NVD_MAP: dict[str, dict] = {
    "fortinet":   {"keyword": "fortios",      "vendor": "fortinet",     "product": "fortios"},
    "sonicwall":  {"keyword": "sonicos",      "vendor": "sonicwall",    "product": "sonicos"},
    "pfsense":    {"keyword": "pfsense",      "vendor": "pfsense",      "product": "pfsense"},
    "opnsense":   {"keyword": "opnsense",     "vendor": "deciso",       "product": "opnsense"},
    "mikrotik":   {"keyword": "routeros",     "vendor": "mikrotik",     "product": "routeros"},
    "cisco_ios":  {"keyword": "cisco ios",    "vendor": "cisco",        "product": "ios"},
    "cisco_nxos": {"keyword": "cisco nx-os",  "vendor": "cisco",        "product": "nx-os"},
    "cisco_asa":  {"keyword": "cisco asa",    "vendor": "cisco",        "product": "adaptive_security_appliance_software"},
    "juniper":    {"keyword": "junos",        "vendor": "juniper",      "product": "junos"},
    "aruba":      {"keyword": "arubaos",      "vendor": "arubanetworks","product": "arubaos"},
    "hp_comware": {"keyword": "comware",      "vendor": "hp",           "product": "comware"},
    "palo_alto":  {"keyword": "pan-os",       "vendor": "paloaltonetworks","product": "pan-os"},
    "checkpoint": {"keyword": "gaia",         "vendor": "checkpoint",   "product": "gaia_os"},
}

_SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


def _get_headers() -> dict[str, str]:
    if settings.nvd_api_key:
        return {"apiKey": settings.nvd_api_key}
    return {}


def _parse_severity(cvss_v3: float | None, cvss_v2: float | None) -> str:
    score = cvss_v3 or cvss_v2 or 0.0
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "UNKNOWN"


def _extract_affected_versions(cve_item: dict) -> dict:
    """Extract affected version ranges from NVD CPE match data."""
    versions: list[dict] = []
    for config in cve_item.get("configurations", []):
        for node in config.get("nodes", []):
            for cpe_match in node.get("cpeMatch", []):
                if not cpe_match.get("vulnerable"):
                    continue
                entry: dict = {}
                if cpe_match.get("versionStartIncluding"):
                    entry["from"] = cpe_match["versionStartIncluding"]
                if cpe_match.get("versionEndExcluding"):
                    entry["to_excl"] = cpe_match["versionEndExcluding"]
                if cpe_match.get("versionEndIncluding"):
                    entry["to_incl"] = cpe_match["versionEndIncluding"]
                if cpe_match.get("criteria"):
                    entry["cpe"] = cpe_match["criteria"]
                if entry:
                    versions.append(entry)
    return {"ranges": versions}


def _parse_cve_item(item: dict, vendor_key: str) -> dict:
    cve = item.get("cve", item)
    cve_id = cve.get("id", "")
    metrics = cve.get("metrics", {})

    cvss_v3: float | None = None
    for key in ("cvssMetricV31", "cvssMetricV30"):
        entries = metrics.get(key, [])
        if entries:
            cvss_v3 = entries[0].get("cvssData", {}).get("baseScore")
            break

    cvss_v2: float | None = None
    entries_v2 = metrics.get("cvssMetricV2", [])
    if entries_v2:
        cvss_v2 = entries_v2[0].get("cvssData", {}).get("baseScore")

    severity = _parse_severity(cvss_v3, cvss_v2)

    descriptions = cve.get("descriptions", [])
    description = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")

    published = cve.get("published")
    modified = cve.get("lastModified")

    cpe_uri: str | None = None
    weaknesses = cve.get("weaknesses", [])
    for ref in cve.get("references", []):
        if "nvd.nist.gov" in ref.get("url", ""):
            cpe_uri = ref["url"]
            break

    nvd_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
    mapping = VENDOR_NVD_MAP.get(vendor_key, {})

    return {
        "cve_id": cve_id,
        "vendor": mapping.get("vendor", vendor_key),
        "product": mapping.get("product", ""),
        "affected_versions": _extract_affected_versions(cve),
        "cvss_v3": cvss_v3,
        "cvss_v2": cvss_v2,
        "severity": severity,
        "description": description[:4000],
        "published_at": datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None,
        "modified_at": datetime.fromisoformat(modified.replace("Z", "+00:00")) if modified else None,
        "cpe_uri": cpe_uri,
        "nvd_url": nvd_url,
        "synced_at": datetime.now(timezone.utc),
    }


async def fetch_cves_for_vendor(vendor_key: str, results_per_page: int = 100) -> list[dict]:
    """Fetch CVE list for a vendor keyword from NVD API."""
    mapping = VENDOR_NVD_MAP.get(vendor_key)
    if not mapping:
        return []

    keyword = mapping["keyword"]
    headers = _get_headers()
    all_cves: list[dict] = []
    start_index = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            params = {
                "keywordSearch": keyword,
                "resultsPerPage": results_per_page,
                "startIndex": start_index,
            }
            resp = await client.get(NVD_BASE, params=params, headers=headers)
            resp.raise_for_status()
            body = resp.json()

            items = body.get("vulnerabilities", [])
            for item in items:
                all_cves.append(_parse_cve_item(item, vendor_key))

            total = body.get("totalResults", 0)
            start_index += results_per_page
            if start_index >= total:
                break

            # NVD rate limit: 5 req/30s without key, 50/30s with key
            delay = 0.6 if settings.nvd_api_key else 6.5
            await asyncio.sleep(delay)

    return all_cves


def version_is_affected(device_version: str, affected_versions: dict) -> bool:
    """Check if a device version string falls within any affected range."""
    ranges = affected_versions.get("ranges", [])
    if not ranges:
        return False

    dev_parts = _version_tuple(device_version)

    for r in ranges:
        from_v = _version_tuple(r.get("from", "0")) if r.get("from") else None
        to_excl = _version_tuple(r.get("to_excl", "")) if r.get("to_excl") else None
        to_incl = _version_tuple(r.get("to_incl", "")) if r.get("to_incl") else None

        if from_v and dev_parts < from_v:
            continue
        if to_excl and dev_parts >= to_excl:
            continue
        if to_incl and dev_parts > to_incl:
            continue
        return True

    return False


def _version_tuple(version_str: str) -> tuple:
    """Convert version string like '7.4.1' or '7.2(3)' to comparable tuple."""
    # Normalize parenthetical Cisco versions: 7.2(3) → 7.2.3
    normalized = re.sub(r"\((\d+)\)", r".\1", version_str)
    parts = re.split(r"[.\-]", normalized)
    result = []
    for part in parts:
        # Extract leading digits
        m = re.match(r"(\d+)", part)
        result.append(int(m.group(1)) if m else 0)
    return tuple(result) if result else (0,)
