"""Medium connector — publish articles to Medium and track story stats.

Revenue model: Medium Partner Program — earn from member reading time.
Authentication: Integration token (self-issued in Medium settings).
Set MEDIUM_TOKEN in ~/.openjarvis/cloud-keys.env.

Docs: https://github.com/Medium/medium-api-docs
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://api.medium.com/v1"


@ConnectorRegistry.register("medium")
class MediumConnector(BaseConnector):
    """Publish articles to Medium and read publication/story metadata."""

    connector_id = "medium"
    display_name = "Medium"
    auth_type = "api_key"

    def __init__(self, token: str = "") -> None:
        self._token = token or os.environ.get("MEDIUM_TOKEN", "")
        self._user_id: str = ""
        self._status = SyncStatus()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def is_connected(self) -> bool:
        return bool(self._token)

    def disconnect(self) -> None:
        self._token = ""

    def _get_user_id(self) -> str:
        if self._user_id:
            return self._user_id
        try:
            resp = httpx.get(f"{_BASE}/me", headers=self._headers(), timeout=15.0)
            resp.raise_for_status()
            self._user_id = resp.json().get("data", {}).get("id", "")
        except Exception:
            pass
        return self._user_id

    def create_post(
        self,
        title: str,
        content_html: str,
        *,
        tags: Optional[List[str]] = None,
        publish_status: str = "draft",
        canonical_url: str = "",
    ) -> Dict[str, Any]:
        """Publish an article to Medium.

        publish_status: "draft" | "public" | "unlisted"
        """
        user_id = self._get_user_id()
        if not user_id:
            return {"error": "Could not resolve Medium user ID — check token."}

        body: Dict[str, Any] = {
            "title": title,
            "contentFormat": "html",
            "content": content_html,
            "publishStatus": publish_status,
        }
        if tags:
            body["tags"] = tags[:5]  # Medium allows max 5 tags
        if canonical_url:
            body["canonicalUrl"] = canonical_url

        resp = httpx.post(
            f"{_BASE}/users/{user_id}/posts",
            headers=self._headers(),
            json=body,
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    def get_publications(self) -> List[Dict[str, Any]]:
        """Return publications the user can post to."""
        user_id = self._get_user_id()
        if not user_id:
            return []
        try:
            resp = httpx.get(
                f"{_BASE}/users/{user_id}/publications",
                headers=self._headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception:
            return []

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        return iter([])  # Medium API does not expose story list for non-partners

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="medium_create_draft",
                description=(
                    "Create a Medium article draft (not yet published). "
                    "Returns the article URL for review."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Article title."},
                        "content_html": {"type": "string", "description": "Article body as HTML."},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Up to 5 tags.",
                        },
                        "canonical_url": {
                            "type": "string",
                            "description": "Original URL if cross-posting (optional).",
                        },
                    },
                    "required": ["title", "content_html"],
                },
                category="publishing",
            ),
            ToolSpec(
                name="medium_publish",
                description="Publish a Medium article publicly (status: public).",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content_html": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "canonical_url": {"type": "string"},
                    },
                    "required": ["title", "content_html"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
        ]
