"""Dev.to connector — publish technical articles via the Dev.to API.

Revenue model: Dev.to does not pay directly, but drives traffic to newsletter/products.
Also eligible for Dev.to listings sponsorship ($50–150 per listing).
Authentication: API key.
Set DEVTO_API_KEY in ~/.openjarvis/cloud-keys.env.

Docs: https://developers.forem.com/api
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://dev.to/api"


@ConnectorRegistry.register("devto")
class DevToConnector(BaseConnector):
    """Publish technical articles to Dev.to."""

    connector_id = "devto"
    display_name = "Dev.to"
    auth_type = "api_key"

    def __init__(self, api_key: str = "") -> None:
        self._key = api_key or os.environ.get("DEVTO_API_KEY", "")
        self._status = SyncStatus()

    def _headers(self) -> Dict[str, str]:
        return {"api-key": self._key, "Content-Type": "application/json"}

    def is_connected(self) -> bool:
        return bool(self._key)

    def disconnect(self) -> None:
        self._key = ""

    def create_article(
        self,
        title: str,
        body_markdown: str,
        *,
        tags: Optional[List[str]] = None,
        published: bool = False,
        canonical_url: str = "",
        series: str = "",
    ) -> Dict[str, Any]:
        """Create a Dev.to article (draft by default)."""
        article: Dict[str, Any] = {
            "title": title,
            "body_markdown": body_markdown,
            "published": published,
        }
        if tags:
            article["tags"] = tags[:4]  # Dev.to max 4 tags
        if canonical_url:
            article["canonical_url"] = canonical_url
        if series:
            article["series"] = series

        resp = httpx.post(
            f"{_BASE}/articles",
            headers=self._headers(),
            json={"article": article},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "id": data.get("id"),
            "url": data.get("url"),
            "title": data.get("title"),
            "published": data.get("published"),
        }

    def get_articles(self, *, per_page: int = 10) -> List[Dict[str, Any]]:
        """Return the user's published articles."""
        try:
            resp = httpx.get(
                f"{_BASE}/articles/me",
                headers=self._headers(),
                params={"per_page": per_page},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected():
            return
        for article in self.get_articles():
            ts_raw = article.get("published_at") or article.get("created_at", "")
            try:
                ts = datetime.fromisoformat(ts_raw.rstrip("Z"))
            except Exception:
                ts = datetime.now()
            if since and ts < since:
                continue
            yield Document(
                doc_id=f"devto-{article.get('id', '')}",
                source="devto",
                doc_type="article",
                content=article.get("description", ""),
                title=article.get("title", ""),
                timestamp=ts,
                url=article.get("url"),
                metadata={
                    "reactions": article.get("public_reactions_count", 0),
                    "comments": article.get("comments_count", 0),
                    "page_views": article.get("page_views_count", 0),
                },
            )
        self._status.last_sync = datetime.now()

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="devto_create_draft",
                description=(
                    "Create a Dev.to article draft. "
                    "Good for technical tutorials, tool comparisons, and how-to guides. "
                    "Cross-post from Ghost/blog with canonical_url to avoid SEO duplication."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body_markdown": {"type": "string", "description": "Article body in Markdown."},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Up to 4 tags."},
                        "canonical_url": {"type": "string", "description": "Original URL if cross-posting."},
                    },
                    "required": ["title", "body_markdown"],
                },
                category="publishing",
            ),
            ToolSpec(
                name="devto_publish",
                description="Publish a Dev.to article publicly.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "body_markdown": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "canonical_url": {"type": "string"},
                    },
                    "required": ["title", "body_markdown"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="devto_article_stats",
                description="Get stats for published Dev.to articles: views, reactions, comments.",
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
        ]
