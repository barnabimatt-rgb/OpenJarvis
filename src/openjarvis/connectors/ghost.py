"""Ghost blog connector — publish and manage posts via the Ghost Admin API.

Authentication: JWT from a Ghost Admin API key (id:secret format).
Set GHOST_ADMIN_URL and GHOST_ADMIN_API_KEY in ~/.openjarvis/cloud-keys.env.

Docs: https://ghost.org/docs/admin-api/
"""

from __future__ import annotations

import base64
import os
import time
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec


def _make_jwt(api_key: str) -> str:
    """Generate a short-lived Ghost Admin API JWT from an id:secret key pair."""
    import hmac
    import hashlib
    import json

    key_id, secret_hex = api_key.split(":", 1)
    secret = bytes.fromhex(secret_hex)

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256", "typ": "JWT", "kid": key_id}).encode()
    ).rstrip(b"=")

    now = int(time.time())
    payload = base64.urlsafe_b64encode(
        json.dumps({"iat": now, "exp": now + 300, "aud": "/admin/"}).encode()
    ).rstrip(b"=")

    sig_input = header + b"." + payload
    sig = base64.urlsafe_b64encode(
        hmac.new(secret, sig_input, hashlib.sha256).digest()
    ).rstrip(b"=")

    return (sig_input + b"." + sig).decode()


@ConnectorRegistry.register("ghost")
class GhostConnector(BaseConnector):
    """Create and manage Ghost blog posts via the Admin API."""

    connector_id = "ghost"
    display_name = "Ghost Blog"
    auth_type = "api_key"

    def __init__(
        self,
        admin_url: str = "",
        admin_api_key: str = "",
    ) -> None:
        self._admin_url = (admin_url or os.environ.get("GHOST_ADMIN_URL", "")).rstrip("/")
        self._api_key = admin_api_key or os.environ.get("GHOST_ADMIN_API_KEY", "")
        self._status = SyncStatus()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Ghost {_make_jwt(self._api_key)}",
            "Content-Type": "application/json",
        }

    def _api(self, path: str) -> str:
        return f"{self._admin_url}/ghost/api/admin/{path.lstrip('/')}"

    def is_connected(self) -> bool:
        return bool(self._admin_url and self._api_key and ":" in self._api_key)

    def disconnect(self) -> None:
        self._api_key = ""

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def create_post(
        self,
        title: str,
        html: str,
        *,
        status: str = "draft",
        tags: Optional[List[str]] = None,
        meta_description: str = "",
    ) -> Dict[str, Any]:
        """Create a new Ghost post.

        Parameters
        ----------
        title:            Post headline.
        html:             Post body as HTML.
        status:           "draft" | "published" | "scheduled".
        tags:             Optional list of tag names.
        meta_description: SEO meta description.
        """
        post_data: Dict[str, Any] = {
            "title": title,
            "html": html,
            "status": status,
        }
        if tags:
            post_data["tags"] = [{"name": t} for t in tags]
        if meta_description:
            post_data["custom_excerpt"] = meta_description

        resp = httpx.post(
            self._api("posts"),
            headers=self._headers(),
            json={"posts": [post_data]},
            timeout=30.0,
        )
        resp.raise_for_status()
        posts = resp.json().get("posts", [{}])
        return posts[0] if posts else {}

    def update_post(self, post_id: str, updated_at: str, **fields: Any) -> Dict[str, Any]:
        """Update an existing post (requires current updated_at for conflict detection)."""
        resp = httpx.put(
            self._api(f"posts/{post_id}"),
            headers=self._headers(),
            json={"posts": [{**fields, "updated_at": updated_at}]},
            timeout=30.0,
        )
        resp.raise_for_status()
        posts = resp.json().get("posts", [{}])
        return posts[0] if posts else {}

    def get_posts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent posts."""
        try:
            resp = httpx.get(
                self._api("posts"),
                headers=self._headers(),
                params={"limit": limit, "order": "created_at desc"},
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json().get("posts", [])
        except Exception:
            return []

    # ------------------------------------------------------------------
    # BaseConnector
    # ------------------------------------------------------------------

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected():
            return
        for post in self.get_posts(limit=20):
            ts_raw = post.get("created_at", "")
            try:
                ts = datetime.fromisoformat(ts_raw.rstrip("Z"))
            except Exception:
                ts = datetime.now()
            if since and ts < since:
                continue
            yield Document(
                doc_id=f"ghost-{post.get('id', '')}",
                source="ghost",
                doc_type="blog_post",
                content=post.get("excerpt", "") or post.get("title", ""),
                title=post.get("title", ""),
                timestamp=ts,
                url=post.get("url"),
                metadata={"status": post.get("status"), "slug": post.get("slug")},
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
                name="ghost_create_draft",
                description=(
                    "Create a Ghost blog post as a draft for human review. "
                    "Returns the post ID and URL."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Post headline."},
                        "html": {"type": "string", "description": "Post body in HTML."},
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of tag names.",
                        },
                        "meta_description": {
                            "type": "string",
                            "description": "SEO meta description (optional).",
                        },
                    },
                    "required": ["title", "html"],
                },
                category="publishing",
            ),
            ToolSpec(
                name="ghost_publish",
                description="Publish a Ghost draft post (changes status to published).",
                parameters={
                    "type": "object",
                    "properties": {
                        "post_id": {"type": "string", "description": "Ghost post ID."},
                        "updated_at": {
                            "type": "string",
                            "description": "Current updated_at timestamp (required by Ghost API).",
                        },
                    },
                    "required": ["post_id", "updated_at"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="ghost_list_posts",
                description="List recent Ghost blog posts with their status and URLs.",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of posts to return.",
                            "default": 10,
                        }
                    },
                    "required": [],
                },
                category="publishing",
            ),
        ]
