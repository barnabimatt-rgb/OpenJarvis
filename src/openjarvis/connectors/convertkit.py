"""ConvertKit (Kit) connector — manage email list and sequences.

Revenue model: Sell digital products, courses, and affiliate offers to email list.
Free tier: up to 10,000 subscribers.
Authentication: API key (v3) or OAuth (v4).
Set CONVERTKIT_API_KEY in ~/.openjarvis/cloud-keys.env.

Docs: https://developers.kit.com/
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://api.convertkit.com/v3"


@ConnectorRegistry.register("convertkit")
class ConvertKitConnector(BaseConnector):
    """Manage ConvertKit email list: subscriber stats, broadcasts, and sequences."""

    connector_id = "convertkit"
    display_name = "ConvertKit / Kit"
    auth_type = "api_key"

    def __init__(self, api_key: str = "") -> None:
        self._key = api_key or os.environ.get("CONVERTKIT_API_KEY", "")
        self._status = SyncStatus()

    def _p(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {"api_key": self._key, **(extra or {})}

    def is_connected(self) -> bool:
        return bool(self._key)

    def disconnect(self) -> None:
        self._key = ""

    def get_subscriber_count(self) -> int:
        """Return total subscriber count."""
        try:
            resp = httpx.get(
                f"{_BASE}/subscribers",
                params=self._p({"sort_order": "desc"}),
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json().get("total_subscribers", 0)
        except Exception:
            return 0

    def get_forms(self) -> List[Dict[str, Any]]:
        """Return all opt-in forms with subscriber counts."""
        try:
            resp = httpx.get(f"{_BASE}/forms", params=self._p(), timeout=15.0)
            resp.raise_for_status()
            return resp.json().get("forms", [])
        except Exception:
            return []

    def create_broadcast(
        self,
        subject: str,
        content_html: str,
        *,
        description: str = "",
        email_address: str = "",
        email_layout_template: str = "Default",
        public: bool = False,
    ) -> Dict[str, Any]:
        """Create a broadcast email (draft by default, not sent immediately)."""
        resp = httpx.post(
            f"{_BASE}/broadcasts",
            params=self._p(),
            json={
                "subject": subject,
                "content": content_html,
                "description": description or subject,
                "email_address": email_address,
                "email_layout_template": email_layout_template,
                "public": public,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("broadcast", {})

    def get_broadcasts(self, page: int = 1) -> List[Dict[str, Any]]:
        """Return recent broadcasts with open/click stats."""
        try:
            resp = httpx.get(
                f"{_BASE}/broadcasts",
                params=self._p({"page": page}),
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json().get("broadcasts", [])
        except Exception:
            return []

    def tag_subscriber(self, email: str, tag_id: int) -> bool:
        """Tag a subscriber by email."""
        try:
            resp = httpx.post(
                f"{_BASE}/tags/{tag_id}/subscribe",
                params=self._p(),
                json={"email": email},
                timeout=15.0,
            )
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected():
            return
        count = self.get_subscriber_count()
        broadcasts = self.get_broadcasts()
        yield Document(
            doc_id=f"ck-snapshot-{datetime.now().date()}",
            source="convertkit",
            doc_type="email_stats",
            content=f"Subscribers: {count}. Recent broadcasts: {len(broadcasts)}.",
            title=f"ConvertKit Snapshot {datetime.now().date()}",
            timestamp=datetime.now(),
            metadata={"subscriber_count": count, "broadcast_count": len(broadcasts)},
        )
        self._status.last_sync = datetime.now()

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="convertkit_subscriber_stats",
                description="Get total ConvertKit subscriber count and recent broadcast stats.",
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
            ToolSpec(
                name="convertkit_create_broadcast",
                description=(
                    "Create a ConvertKit broadcast email draft. "
                    "The email is NOT sent — review and send manually in ConvertKit."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string", "description": "Email subject line."},
                        "content_html": {"type": "string", "description": "Email body as HTML."},
                        "description": {"type": "string", "description": "Internal description (optional)."},
                    },
                    "required": ["subject", "content_html"],
                },
                category="publishing",
            ),
        ]
