"""YouTube connector — generate video metadata and manage channel via YouTube Data API v3.

Revenue model: YouTube Partner Program ($2–8 CPM once 1,000 subs + 4,000 watch hours).
Authentication: OAuth 2.0 or API key (read-only) + service account (write).
Set YOUTUBE_API_KEY (read) and/or YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET (write)
in ~/.openjarvis/cloud-keys.env.

Docs: https://developers.google.com/youtube/v3
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://www.googleapis.com/youtube/v3"


@ConnectorRegistry.register("youtube")
class YouTubeConnector(BaseConnector):
    """Manage YouTube channel content and retrieve analytics."""

    connector_id = "youtube"
    display_name = "YouTube"
    auth_type = "api_key"

    def __init__(self, api_key: str = "", channel_id: str = "") -> None:
        self._api_key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        self._channel_id = channel_id or os.environ.get("YOUTUBE_CHANNEL_ID", "")
        self._status = SyncStatus()

    def is_connected(self) -> bool:
        return bool(self._api_key)

    def disconnect(self) -> None:
        self._api_key = ""

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        resp = httpx.get(
            f"{_BASE}/{path}",
            params={"key": self._api_key, **params},
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_channel_stats(self) -> Dict[str, Any]:
        """Return subscriber count, view count, and video count."""
        try:
            data = self._get("channels", {"part": "statistics", "id": self._channel_id})
            items = data.get("items", [])
            if items:
                stats = items[0].get("statistics", {})
                return {
                    "subscribers": int(stats.get("subscriberCount", 0)),
                    "total_views": int(stats.get("viewCount", 0)),
                    "video_count": int(stats.get("videoCount", 0)),
                }
        except Exception:
            pass
        return {"subscribers": 0, "total_views": 0, "video_count": 0}

    def get_recent_videos(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return metadata for the most recent uploads."""
        try:
            search = self._get("search", {
                "part": "snippet",
                "channelId": self._channel_id,
                "order": "date",
                "maxResults": limit,
                "type": "video",
            })
            return [
                {
                    "video_id": item["id"].get("videoId", ""),
                    "title": item["snippet"].get("title", ""),
                    "description": item["snippet"].get("description", ""),
                    "published_at": item["snippet"].get("publishedAt", ""),
                    "thumbnail": item["snippet"].get("thumbnails", {}).get("high", {}).get("url", ""),
                }
                for item in search.get("items", [])
            ]
        except Exception:
            return []

    def generate_video_metadata(
        self,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Return a structured metadata dict ready to use in a YouTube upload."""
        return {
            "title": title[:100],
            "description": description[:5000],
            "tags": ",".join((tags or [])[:500]),
            "categoryId": "22",  # People & Blogs — good default for content creators
        }

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected() or not self._channel_id:
            return
        for video in self.get_recent_videos():
            try:
                ts = datetime.fromisoformat(video["published_at"].rstrip("Z"))
            except Exception:
                ts = datetime.now()
            if since and ts < since:
                continue
            yield Document(
                doc_id=f"yt-{video['video_id']}",
                source="youtube",
                doc_type="video",
                content=video["description"],
                title=video["title"],
                timestamp=ts,
                url=f"https://youtube.com/watch?v={video['video_id']}",
            )
        self._status.last_sync = datetime.now()

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="youtube_channel_stats",
                description="Get YouTube channel stats: subscriber count, total views, video count.",
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
            ToolSpec(
                name="youtube_generate_metadata",
                description=(
                    "Generate optimised YouTube video metadata (title, description, tags) "
                    "for a given topic. Saves to Obsidian draft folder."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "Video topic or niche."},
                        "hook": {"type": "string", "description": "Opening hook sentence."},
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Target SEO keywords.",
                        },
                    },
                    "required": ["topic"],
                },
                category="publishing",
            ),
            ToolSpec(
                name="youtube_recent_videos",
                description="List the most recent YouTube videos on the channel with titles and publish dates.",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10, "description": "Number of videos."}
                    },
                    "required": [],
                },
                category="analytics",
            ),
        ]
