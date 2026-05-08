"""Reddit publisher connector — post to subreddits via the Reddit API.

Revenue model: Traffic driver → newsletter signups, affiliate links, product sales.
Authentication: OAuth 2.0 (script app type — personal use).
Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
in ~/.openjarvis/cloud-keys.env.

Rate limits: 60 requests/minute. Post limits: ~1 post/10 min per subreddit.
Docs: https://www.reddit.com/dev/api/
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_BASE = "https://oauth.reddit.com"
_USER_AGENT = "openjarvis-passive-income/1.0"


@ConnectorRegistry.register("reddit_publisher")
class RedditPublisherConnector(BaseConnector):
    """Post content to Reddit subreddits to drive traffic and brand awareness."""

    connector_id = "reddit_publisher"
    display_name = "Reddit Publisher"
    auth_type = "oauth"

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        username: str = "",
        password: str = "",
    ) -> None:
        self._client_id = client_id or os.environ.get("REDDIT_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET", "")
        self._username = username or os.environ.get("REDDIT_USERNAME", "")
        self._password = password or os.environ.get("REDDIT_PASSWORD", "")
        self._access_token: str = ""
        self._token_expiry: float = 0.0
        self._status = SyncStatus()

    def is_connected(self) -> bool:
        return bool(self._client_id and self._client_secret and self._username and self._password)

    def disconnect(self) -> None:
        self._access_token = ""

    def _ensure_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token
        resp = httpx.post(
            _TOKEN_URL,
            auth=(self._client_id, self._client_secret),
            data={"grant_type": "password", "username": self._username, "password": self._password},
            headers={"User-Agent": _USER_AGENT},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"bearer {self._ensure_token()}",
            "User-Agent": _USER_AGENT,
        }

    def submit_link(
        self, subreddit: str, title: str, url: str, *, flair_id: str = ""
    ) -> Dict[str, Any]:
        """Submit a link post to a subreddit."""
        data: Dict[str, Any] = {
            "sr": subreddit, "kind": "link", "title": title, "url": url, "resubmit": True,
        }
        if flair_id:
            data["flair_id"] = flair_id
        resp = httpx.post(
            f"{_BASE}/api/submit", headers=self._headers(), data=data, timeout=20.0
        )
        resp.raise_for_status()
        return resp.json().get("jquery", [{}])[-1]

    def submit_text(
        self, subreddit: str, title: str, text: str
    ) -> Dict[str, Any]:
        """Submit a self-text post to a subreddit."""
        resp = httpx.post(
            f"{_BASE}/api/submit",
            headers=self._headers(),
            data={"sr": subreddit, "kind": "self", "title": title, "text": text},
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_subreddit_info(self, subreddit: str) -> Dict[str, Any]:
        """Return basic stats for a subreddit (subscriber count, description)."""
        try:
            resp = httpx.get(
                f"{_BASE}/r/{subreddit}/about.json",
                headers=self._headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "name": data.get("display_name", ""),
                "subscribers": data.get("subscribers", 0),
                "description": data.get("public_description", ""),
                "over18": data.get("over18", False),
                "allow_links": not data.get("is_crosspostable_subreddit", False),
            }
        except Exception:
            return {}

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        return iter([])

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="reddit_post_link",
                description=(
                    "Submit a link post to a Reddit subreddit. "
                    "Great for driving traffic to blog posts and newsletters."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "subreddit": {"type": "string", "description": "Subreddit name (without r/)."},
                        "title": {"type": "string", "description": "Post title."},
                        "url": {"type": "string", "description": "URL to share."},
                    },
                    "required": ["subreddit", "title", "url"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="reddit_post_text",
                description=(
                    "Submit a self-text post to a subreddit. "
                    "Good for discussion, value-add posts, and soft promotion."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "subreddit": {"type": "string"},
                        "title": {"type": "string"},
                        "text": {"type": "string", "description": "Markdown-formatted post body."},
                    },
                    "required": ["subreddit", "title", "text"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="reddit_subreddit_info",
                description="Get subscriber count and description for a subreddit before posting.",
                parameters={
                    "type": "object",
                    "properties": {
                        "subreddit": {"type": "string", "description": "Subreddit name."}
                    },
                    "required": ["subreddit"],
                },
                category="research",
            ),
        ]
