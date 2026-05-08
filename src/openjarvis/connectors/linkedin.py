"""LinkedIn connector — publish posts and articles via the LinkedIn API.

Revenue model: B2B lead generation → consulting/services/courses.
Authentication: OAuth 2.0 access token with w_member_social scope.
Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN in ~/.openjarvis/cloud-keys.env.

URN format: urn:li:person:{id} — find yours at linkedin.com/in/your-profile
Docs: https://learn.microsoft.com/en-us/linkedin/marketing/
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://api.linkedin.com/v2"


@ConnectorRegistry.register("linkedin")
class LinkedInConnector(BaseConnector):
    """Post content to LinkedIn and retrieve basic post analytics."""

    connector_id = "linkedin"
    display_name = "LinkedIn"
    auth_type = "oauth"

    def __init__(self, access_token: str = "", person_urn: str = "") -> None:
        self._token = access_token or os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
        self._urn = person_urn or os.environ.get("LINKEDIN_PERSON_URN", "")
        self._status = SyncStatus()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def is_connected(self) -> bool:
        return bool(self._token and self._urn)

    def disconnect(self) -> None:
        self._token = ""

    def post_text(self, text: str, *, visibility: str = "PUBLIC") -> Dict[str, Any]:
        """Post a text update to the LinkedIn feed."""
        body = {
            "author": self._urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
        }
        resp = httpx.post(
            f"{_BASE}/ugcPosts",
            headers=self._headers(),
            json=body,
            timeout=20.0,
        )
        resp.raise_for_status()
        return {"post_id": resp.headers.get("x-restli-id", ""), "status": "published"}

    def post_article(
        self,
        title: str,
        body_text: str,
        *,
        article_url: str = "",
        visibility: str = "PUBLIC",
    ) -> Dict[str, Any]:
        """Post an article link or long-form text to LinkedIn."""
        content: Dict[str, Any] = {
            "shareCommentary": {"text": body_text[:3000]},
            "shareMediaCategory": "NONE",
        }
        if article_url:
            content["shareMediaCategory"] = "ARTICLE"
            content["media"] = [{"status": "READY", "originalUrl": article_url, "title": {"text": title}}]

        body = {
            "author": self._urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": content},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": visibility},
        }
        resp = httpx.post(f"{_BASE}/ugcPosts", headers=self._headers(), json=body, timeout=20.0)
        resp.raise_for_status()
        return {"post_id": resp.headers.get("x-restli-id", ""), "status": "published"}

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        return iter([])

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="linkedin_post",
                description=(
                    "Post a text update to LinkedIn (max 3,000 chars). "
                    "Good for thought leadership and driving newsletter signups."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Post content (max 3,000 chars)."},
                    },
                    "required": ["text"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="linkedin_share_article",
                description="Share a blog post or article URL on LinkedIn with a commentary.",
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Article title."},
                        "body_text": {"type": "string", "description": "Your commentary on the article."},
                        "article_url": {"type": "string", "description": "URL of the article to share."},
                    },
                    "required": ["title", "body_text", "article_url"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
        ]
