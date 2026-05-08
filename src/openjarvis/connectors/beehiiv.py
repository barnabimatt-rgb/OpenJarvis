"""Beehiiv newsletter connector — publish and track newsletters via the Beehiiv API v2.

Authentication: Bearer token.
Set BEEHIIV_API_KEY in ~/.openjarvis/cloud-keys.env.

Docs: https://developers.beehiiv.com/
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE_URL = "https://api.beehiiv.com/v2"


def _headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


@ConnectorRegistry.register("beehiiv")
class BeehiivConnector(BaseConnector):
    """Publish newsletter posts and retrieve subscriber/engagement stats via Beehiiv."""

    connector_id = "beehiiv"
    display_name = "Beehiiv Newsletter"
    auth_type = "api_key"

    def __init__(
        self,
        api_key: str = "",
        publication_id: str = "",
    ) -> None:
        self._api_key = api_key or os.environ.get("BEEHIIV_API_KEY", "")
        self._publication_id = publication_id or os.environ.get("BEEHIIV_PUBLICATION_ID", "")
        self._status = SyncStatus()

    def is_connected(self) -> bool:
        return bool(self._api_key)

    def disconnect(self) -> None:
        self._api_key = ""

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def create_post(
        self,
        title: str,
        body_html: str,
        *,
        subtitle: str = "",
        status: str = "draft",
    ) -> Dict[str, Any]:
        """Create a newsletter post (default: draft for human review).

        Parameters
        ----------
        title:      Post headline.
        body_html:  Full HTML body content.
        subtitle:   Optional preview text shown in email clients.
        status:     "draft" | "confirmed" (confirmed = scheduled/sent).
        """
        resp = httpx.post(
            f"{_BASE_URL}/publications/{self._publication_id}/posts",
            headers=_headers(self._api_key),
            json={
                "title": title,
                "subtitle": subtitle,
                "content": {"type": "html", "value": body_html},
                "status": status,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    def send_post(self, post_id: str) -> Dict[str, Any]:
        """Move a draft post to confirmed (queued for sending)."""
        resp = httpx.patch(
            f"{_BASE_URL}/publications/{self._publication_id}/posts/{post_id}",
            headers=_headers(self._api_key),
            json={"status": "confirmed"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_subscriber_count(self) -> int:
        """Return total active subscriber count for the publication."""
        try:
            resp = httpx.get(
                f"{_BASE_URL}/publications/{self._publication_id}",
                headers=_headers(self._api_key),
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("stats", {}).get("total_active_subscriptions", 0)
        except Exception:
            return 0

    def get_post_stats(self, post_id: str) -> Dict[str, Any]:
        """Return engagement stats for a specific post."""
        try:
            resp = httpx.get(
                f"{_BASE_URL}/publications/{self._publication_id}/posts/{post_id}",
                headers=_headers(self._api_key),
                timeout=20.0,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "title": data.get("title", ""),
                "status": data.get("status", ""),
                "stats": data.get("stats", {}),
            }
        except Exception:
            return {}

    def get_recent_posts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return metadata for the most recent posts."""
        try:
            resp = httpx.get(
                f"{_BASE_URL}/publications/{self._publication_id}/posts",
                headers=_headers(self._api_key),
                params={"limit": limit, "order_by": "created", "direction": "desc"},
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # BaseConnector — sync yields recent posts as Documents
    # ------------------------------------------------------------------

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected():
            return
        for post in self.get_recent_posts(limit=10):
            ts_raw = post.get("created_at")
            ts = datetime.fromtimestamp(ts_raw) if ts_raw else datetime.now()
            if since and ts < since:
                continue
            yield Document(
                doc_id=f"beehiiv-{post.get('id', '')}",
                source="beehiiv",
                doc_type="newsletter_post",
                content=post.get("subtitle", "") or post.get("title", ""),
                title=post.get("title", ""),
                timestamp=ts,
                url=post.get("web_url"),
                metadata={
                    "status": post.get("status"),
                    "stats": post.get("stats", {}),
                },
            )
        self._status.last_sync = datetime.now()

    def sync_status(self) -> SyncStatus:
        return self._status

    # ------------------------------------------------------------------
    # MCP tools
    # ------------------------------------------------------------------

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="beehiiv_create_draft",
                description=(
                    "Save a newsletter issue as a draft in Beehiiv for human review "
                    "before sending. Returns the post ID."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Newsletter subject line."},
                        "body_html": {"type": "string", "description": "Full HTML body."},
                        "subtitle": {"type": "string", "description": "Preview text (optional)."},
                    },
                    "required": ["title", "body_html"],
                },
                category="publishing",
                requires_confirmation=False,
            ),
            ToolSpec(
                name="beehiiv_send",
                description="Move a Beehiiv draft post to confirmed (queued for delivery).",
                parameters={
                    "type": "object",
                    "properties": {
                        "post_id": {"type": "string", "description": "Beehiiv post ID to send."},
                    },
                    "required": ["post_id"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="beehiiv_stats",
                description=(
                    "Get newsletter stats: subscriber count and recent post engagement."
                ),
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
        ]
