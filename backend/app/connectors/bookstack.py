"""BookStack API connector.

Authentication: Token-Id + Token-Secret sent as Authorization header.
Config keys (stored encrypted in Integration.encrypted_config):
  base_url      — e.g. "https://bookstack.empresa.com"
  token_id      — API token ID
  token_secret  — API token secret
  book_id       — int: the BookStack book that maps to this tenant/client
  shelf_id      — int | None: shelf to use when creating new books (optional)
"""
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class BSBook:
    id: int
    name: str
    slug: str
    description: str


@dataclass
class BSChapter:
    id: int
    book_id: int
    name: str
    slug: str
    description: str


@dataclass
class BSPage:
    id: int
    book_id: int
    chapter_id: int | None
    name: str
    slug: str
    html: str = ""
    markdown: str = ""


@dataclass
class BSSearchResult:
    id: int
    name: str
    type: str          # "page" | "chapter" | "book"
    url: str
    preview_html: str = ""


class BookStackConnector:
    def __init__(self, base_url: str, token_id: str, token_secret: str):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Token {token_id}:{token_secret}",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self._headers,
            timeout=15.0,
            verify=False,
        )

    # ── Connectivity ──────────────────────────────────────────────────────────

    async def ping(self) -> tuple[bool, str]:
        """Verify credentials by listing books (lightweight call)."""
        start = time.monotonic()
        try:
            async with self._client() as c:
                resp = await c.get(f"{self.base_url}/api/books", params={"count": 1})
            latency_ms = (time.monotonic() - start) * 1000
            if resp.status_code == 200:
                total = resp.json().get("total", "?")
                return True, f"Conectado — {total} livro(s) disponível(is) | {latency_ms:.0f}ms"
            if resp.status_code == 401:
                return False, "Credenciais inválidas (401) — verifique token_id e token_secret"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except httpx.ConnectError:
            return False, f"Não foi possível conectar em {self.base_url}"
        except Exception as exc:
            return False, str(exc)

    # ── Books ─────────────────────────────────────────────────────────────────

    async def list_books(self) -> list[BSBook]:
        async with self._client() as c:
            resp = await c.get(f"{self.base_url}/api/books", params={"count": 500})
        resp.raise_for_status()
        return [
            BSBook(id=b["id"], name=b["name"], slug=b["slug"],
                   description=b.get("description", ""))
            for b in resp.json().get("data", [])
        ]

    # ── Chapters ──────────────────────────────────────────────────────────────

    async def list_chapters(self, book_id: int) -> list[BSChapter]:
        """List all chapters inside a book."""
        async with self._client() as c:
            resp = await c.get(f"{self.base_url}/api/chapters",
                               params={"filter[book_id]": book_id, "count": 500})
        resp.raise_for_status()
        return [
            BSChapter(id=ch["id"], book_id=ch["book_id"], name=ch["name"],
                      slug=ch["slug"], description=ch.get("description", ""))
            for ch in resp.json().get("data", [])
        ]

    async def get_chapter(self, chapter_id: int) -> BSChapter:
        async with self._client() as c:
            resp = await c.get(f"{self.base_url}/api/chapters/{chapter_id}")
        resp.raise_for_status()
        ch = resp.json()
        return BSChapter(id=ch["id"], book_id=ch["book_id"], name=ch["name"],
                         slug=ch["slug"], description=ch.get("description", ""))

    # ── Pages ─────────────────────────────────────────────────────────────────

    async def list_pages_in_book(self, book_id: int) -> list[BSPage]:
        """List all pages in a book regardless of chapter."""
        async with self._client() as c:
            resp = await c.get(f"{self.base_url}/api/pages",
                               params={"filter[book_id]": book_id, "count": 500})
        resp.raise_for_status()
        return [
            BSPage(id=p["id"], book_id=p["book_id"], chapter_id=p.get("chapter_id"),
                   name=p["name"], slug=p["slug"])
            for p in resp.json().get("data", [])
        ]

    async def list_pages_in_chapter(self, chapter_id: int) -> list[BSPage]:
        async with self._client() as c:
            resp = await c.get(f"{self.base_url}/api/pages",
                               params={"filter[chapter_id]": chapter_id, "count": 500})
        resp.raise_for_status()
        return [
            BSPage(id=p["id"], book_id=p["book_id"],
                   chapter_id=p.get("chapter_id"), name=p["name"], slug=p["slug"])
            for p in resp.json().get("data", [])
        ]

    async def get_page(self, page_id: int) -> BSPage:
        async with self._client() as c:
            resp = await c.get(f"{self.base_url}/api/pages/{page_id}")
        resp.raise_for_status()
        p = resp.json()
        return BSPage(
            id=p["id"], book_id=p["book_id"], chapter_id=p.get("chapter_id"),
            name=p["name"], slug=p["slug"],
            html=p.get("html", ""), markdown=p.get("markdown", ""),
        )

    async def create_page(
        self,
        book_id: int,
        name: str,
        markdown: str,
        chapter_id: int | None = None,
    ) -> BSPage:
        payload: dict = {"book_id": book_id, "name": name, "markdown": markdown}
        if chapter_id:
            payload["chapter_id"] = chapter_id
        async with self._client() as c:
            resp = await c.post(f"{self.base_url}/api/pages", json=payload)
        resp.raise_for_status()
        p = resp.json()
        return BSPage(
            id=p["id"], book_id=p["book_id"], chapter_id=p.get("chapter_id"),
            name=p["name"], slug=p["slug"], markdown=markdown,
        )

    async def update_page(self, page_id: int, name: str, markdown: str) -> BSPage:
        payload = {"name": name, "markdown": markdown}
        async with self._client() as c:
            resp = await c.put(f"{self.base_url}/api/pages/{page_id}", json=payload)
        resp.raise_for_status()
        p = resp.json()
        return BSPage(
            id=p["id"], book_id=p["book_id"], chapter_id=p.get("chapter_id"),
            name=p["name"], slug=p["slug"], markdown=markdown,
        )

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        book_id: int | None = None,
        page_count: int = 5,
    ) -> list[BSSearchResult]:
        """Full-text search across the BookStack instance (or scoped to a book)."""
        q = query
        if book_id:
            q = f"{query} [book_id:{book_id}]"
        async with self._client() as c:
            resp = await c.get(f"{self.base_url}/api/search",
                               params={"query": q, "count": page_count})
        if resp.status_code != 200:
            return []
        return [
            BSSearchResult(
                id=r["id"], name=r["name"], type=r["type"],
                url=r.get("url", ""),
                preview_html=r.get("preview_html", ""),
            )
            for r in resp.json().get("data", [])
        ]

    async def get_page_content_by_search(
        self,
        query: str,
        book_id: int | None = None,
        max_chars: int = 3000,
    ) -> str:
        """Search and return combined plain-text content of matching pages."""
        results = await self.search(query, book_id=book_id, page_count=5)
        page_results = [r for r in results if r.type == "page"]
        if not page_results:
            return ""

        parts: list[str] = []
        total = 0
        for result in page_results:
            if total >= max_chars:
                break
            try:
                page = await self.get_page(result.id)
                text = page.markdown or _strip_html(page.html)
                chunk = f"## {page.name}\n{text}"[:max_chars - total]
                parts.append(chunk)
                total += len(chunk)
            except Exception:
                continue

        return "\n\n---\n\n".join(parts)


def _strip_html(html: str) -> str:
    """Minimal HTML stripper — removes tags, keeps text."""
    import re
    return re.sub(r"<[^>]+>", "", html).strip()


def connector_from_config(config: dict) -> "BookStackConnector":
    return BookStackConnector(
        base_url=config["base_url"],
        token_id=config["token_id"],
        token_secret=config["token_secret"],
    )
