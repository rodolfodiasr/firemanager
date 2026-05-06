"""GLPI 11.0.4 REST API async client."""
import base64
import logging
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# GLPI ticket statuses
STATUS_NEW        = 1
STATUS_ASSIGNED   = 2
STATUS_PLANNED    = 3
STATUS_PENDING    = 4
STATUS_SOLVED     = 5
STATUS_CLOSED     = 6
OPEN_STATUSES = {STATUS_NEW, STATUS_ASSIGNED, STATUS_PLANNED, STATUS_PENDING}

# GLPI ticket types
TYPE_INCIDENT = 1
TYPE_REQUEST  = 2


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(p.strip() for p in self._parts if p.strip())


class GlpiClient:
    """Async context-manager client for GLPI 11.0.4 REST API.

    Usage::

        async with GlpiClient(url, app_token, user, password) as client:
            tickets = await client.get_open_tickets(min_priority=3)
    """

    def __init__(
        self,
        glpi_url: str,
        app_token: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
    ) -> None:
        self._base = glpi_url.rstrip("/") + "/apirest.php"
        self._app_token = app_token
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._session_token: str | None = None
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "GlpiClient":
        self._http = httpx.AsyncClient(verify=self._verify_ssl, timeout=30)
        await self.init_session()
        return self

    async def __aexit__(self, *_: Any) -> None:
        try:
            await self.kill_session()
        finally:
            if self._http:
                await self._http.aclose()

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def init_session(self) -> None:
        credentials = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        resp = await self._http.get(
            f"{self._base}/initSession",
            headers={
                "Authorization": f"Basic {credentials}",
                "App-Token": self._app_token,
            },
        )
        resp.raise_for_status()
        self._session_token = resp.json()["session_token"]

    async def kill_session(self) -> None:
        if not self._session_token:
            return
        try:
            await self._http.get(f"{self._base}/killSession", headers=self._headers())
        except Exception:
            pass
        self._session_token = None

    # ------------------------------------------------------------------
    # Tickets
    # ------------------------------------------------------------------

    async def get_open_tickets(
        self,
        min_priority: int = 3,
        trigger_types: list[int] | None = None,
        trigger_categories: list[int] | None = None,
        lookback_hours: int = 24,
        limit: int = 200,
    ) -> list[dict]:
        """Return open tickets created or modified within *lookback_hours*.

        Applies priority, type, and category filters.
        """
        since = (
            datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        ).strftime("%Y-%m-%d %H:%M:%S")

        criteria: list[dict] = [
            # status in open set
            {"field": "12", "searchtype": "equals", "value": str(STATUS_NEW)},
            {"link": "OR", "field": "12", "searchtype": "equals", "value": str(STATUS_ASSIGNED)},
            {"link": "OR", "field": "12", "searchtype": "equals", "value": str(STATUS_PLANNED)},
            {"link": "OR", "field": "12", "searchtype": "equals", "value": str(STATUS_PENDING)},
            # priority >= min_priority
            {"link": "AND", "field": "10", "searchtype": "greaterthan", "value": str(min_priority - 1)},
            # modified recently
            {"link": "AND", "field": "19", "searchtype": "morethan", "value": since},
        ]

        if trigger_types:
            for i, t in enumerate(trigger_types):
                link = "AND" if i == 0 else "OR"
                criteria.append({"link": link, "field": "4", "searchtype": "equals", "value": str(t)})

        if trigger_categories:
            for i, cat in enumerate(trigger_categories):
                link = "AND" if i == 0 else "OR"
                criteria.append({"link": link, "field": "7", "searchtype": "equals", "value": str(cat)})

        params: dict[str, Any] = {
            "forcedisplay[0]": "1",   # name
            "forcedisplay[1]": "4",   # type
            "forcedisplay[2]": "10",  # priority
            "forcedisplay[3]": "12",  # status
            "forcedisplay[4]": "15",  # date_creation
            "forcedisplay[5]": "19",  # date_mod
            "forcedisplay[6]": "21",  # content
            "forcedisplay[7]": "7",   # itilcategories_id
            "range": f"0-{limit - 1}",
            "as_map": "0",
        }
        for i, c in enumerate(criteria):
            for k, v in c.items():
                params[f"criteria[{i}][{k}]"] = v

        resp = await self._http.get(
            f"{self._base}/search/Ticket",
            headers=self._headers(),
            params=params,
        )
        if resp.status_code == 206:
            # partial content — still valid
            pass
        elif resp.status_code != 200:
            logger.warning("GLPI search returned %s: %s", resp.status_code, resp.text[:300])
            return []

        data = resp.json()
        return data.get("data", [])

    async def get_ticket(self, ticket_id: int) -> dict:
        resp = await self._http.get(
            f"{self._base}/Ticket/{ticket_id}",
            headers=self._headers(),
            params={"expand_dropdowns": "true", "get_hateoas": "false"},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_ticket_followups(self, ticket_id: int) -> list[dict]:
        resp = await self._http.get(
            f"{self._base}/Ticket/{ticket_id}/ITILFollowup",
            headers=self._headers(),
            params={"range": "0-99"},
        )
        if resp.status_code in (200, 206):
            return resp.json() if isinstance(resp.json(), list) else []
        return []

    async def get_open_problems(
        self,
        lookback_hours: int = 24,
        limit: int = 200,
    ) -> list[dict]:
        """Return open Problems (GLPI Problem module) modified within lookback_hours."""
        since = (
            datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        ).strftime("%Y-%m-%d %H:%M:%S")
        # Problem open statuses: 1=New, 2=Accepted, 3=Assigned, 4=Planned, 5=Observed
        params: dict[str, Any] = {
            "criteria[0][field]": "12",
            "criteria[0][searchtype]": "equals",
            "criteria[0][value]": "1",
            "criteria[1][link]": "OR",
            "criteria[1][field]": "12",
            "criteria[1][searchtype]": "equals",
            "criteria[1][value]": "2",
            "criteria[2][link]": "OR",
            "criteria[2][field]": "12",
            "criteria[2][searchtype]": "equals",
            "criteria[2][value]": "3",
            "criteria[3][link]": "OR",
            "criteria[3][field]": "12",
            "criteria[3][searchtype]": "equals",
            "criteria[3][value]": "4",
            "criteria[4][link]": "OR",
            "criteria[4][field]": "12",
            "criteria[4][searchtype]": "equals",
            "criteria[4][value]": "5",
            "criteria[5][link]": "AND",
            "criteria[5][field]": "19",
            "criteria[5][searchtype]": "morethan",
            "criteria[5][value]": since,
            "forcedisplay[0]": "1",   # name
            "forcedisplay[1]": "12",  # status
            "forcedisplay[2]": "19",  # date_mod
            "forcedisplay[3]": "21",  # content
            "range": f"0-{limit - 1}",
            "as_map": "0",
        }
        resp = await self._http.get(
            f"{self._base}/search/Problem",
            headers=self._headers(),
            params=params,
        )
        if resp.status_code in (200, 206):
            return resp.json().get("data", [])
        logger.warning("GLPI Problem search returned %s: %s", resp.status_code, resp.text[:300])
        return []

    async def get_similar_tickets(self, title: str, limit: int = 5) -> list[dict]:
        """Search for tickets with a similar title (closed/solved)."""
        params = {
            "criteria[0][field]": "1",
            "criteria[0][searchtype]": "contains",
            "criteria[0][value]": title[:80],
            "criteria[1][link]": "AND",
            "criteria[1][field]": "12",
            "criteria[1][searchtype]": "equals",
            "criteria[1][value]": str(STATUS_SOLVED),
            "forcedisplay[0]": "1",
            "forcedisplay[1]": "12",
            "range": f"0-{limit - 1}",
        }
        resp = await self._http.get(
            f"{self._base}/search/Ticket",
            headers=self._headers(),
            params=params,
        )
        if resp.status_code in (200, 206):
            return resp.json().get("data", [])
        return []

    async def get_ticket_category(self, category_id: int) -> dict | None:
        if not category_id:
            return None
        resp = await self._http.get(
            f"{self._base}/ITILCategory/{category_id}",
            headers=self._headers(),
        )
        if resp.status_code == 200:
            return resp.json()
        return None

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add_followup(self, ticket_id: int, content: str, is_private: bool = False, itemtype: str = "Ticket") -> int | None:
        """Add a followup note to a ticket/problem/change. Returns the created followup ID."""
        payload = {
            "input": {
                "items_id": ticket_id,
                "itemtype": itemtype,
                "content": content,
                "is_private": int(is_private),
            }
        }
        resp = await self._http.post(
            f"{self._base}/ITILFollowup",
            headers=self._headers(),
            json=payload,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            return data.get("id")
        logger.warning("add_followup failed %s: %s", resp.status_code, resp.text[:200])
        return None

    async def set_ticket_status(self, ticket_id: int, status: int) -> bool:
        payload = {"input": {"id": ticket_id, "status": status}}
        resp = await self._http.put(
            f"{self._base}/Ticket/{ticket_id}",
            headers=self._headers(),
            json=payload,
        )
        return resp.status_code in (200, 201)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        h = {"App-Token": self._app_token, "Content-Type": "application/json"}
        if self._session_token:
            h["Session-Token"] = self._session_token
        return h

    @staticmethod
    def strip_html(html: str | None) -> str:
        if not html:
            return ""
        stripper = _HTMLStripper()
        stripper.feed(html)
        return stripper.get_text()

    @staticmethod
    def extract_hostname_from_ticket(title: str, content: str | None = "") -> str | None:
        """Try to extract a hostname or IP from ticket title/content."""
        combined = f"{title} {content or ''}"
        # IPv4
        ip_match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", combined)
        if ip_match:
            return ip_match.group(1)
        # Hostname-like word (letters, digits, hyphens, dots — at least one dot)
        host_match = re.search(r"\b([a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b", combined)
        if host_match:
            return host_match.group(0)
        return None
