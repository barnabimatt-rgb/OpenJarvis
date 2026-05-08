"""UTM link tracker — generate trackable affiliate / campaign links.

Creates UTM-tagged URLs for content campaigns so you can attribute traffic
back to specific platform posts. Optionally shortens via bit.ly.

Stores all generated links in memory so the agent can reference them later
for attribution analysis.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs, urlencode

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_BITLY_API = "https://api-ssl.bitly.com/v4/shorten"


def _build_utm_url(
    base_url: str,
    *,
    source: str,
    medium: str,
    campaign: str,
    content: str = "",
    term: str = "",
) -> str:
    """Append UTM parameters to a URL, preserving any existing query params."""
    parsed = urlparse(base_url)
    existing = parse_qs(parsed.query, keep_blank_values=True)

    utm: Dict[str, str] = {
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": re.sub(r"[^a-z0-9_-]", "-", campaign.lower()),
    }
    if content:
        utm["utm_content"] = re.sub(r"[^a-z0-9_-]", "-", content.lower())
    if term:
        utm["utm_term"] = re.sub(r"[^a-z0-9_-]", "-", term.lower())

    # Merge: UTM params override existing ones with same name
    merged = {k: v[0] if isinstance(v, list) else v for k, v in existing.items()}
    merged.update(utm)

    new_query = urlencode(merged)
    return urlunparse(parsed._replace(query=new_query))


def _shorten_bitly(long_url: str, token: str) -> Optional[str]:
    """Shorten a URL via bit.ly. Returns short URL or None on failure."""
    try:
        resp = httpx.post(
            _BITLY_API,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"long_url": long_url},
            timeout=10.0,
        )
        if resp.status_code in (200, 201):
            return resp.json().get("link")
    except Exception:
        pass
    return None


def _store_link(link_data: Dict[str, Any]) -> None:
    """Persist UTM link to memory backend if available."""
    try:
        from openjarvis.core.registry import MemoryRegistry
        backend = MemoryRegistry.get("sqlite")()
        backend.store(
            f"UTM link: {link_data['utm_url']}",
            source="link_tracker",
            metadata={"tag": "utm_links", **link_data},
        )
    except Exception:
        pass


@ToolRegistry.register("utm_link")
class UTMLinkTool(BaseTool):
    """Generate UTM-tracked affiliate / campaign links."""

    tool_id = "utm_link"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="utm_link",
            description=(
                "Generate a UTM-tagged URL for tracking traffic from a specific platform post. "
                "Appends utm_source, utm_medium, utm_campaign (and optionally utm_content/utm_term). "
                "Optionally shortens via bit.ly if BITLY_ACCESS_TOKEN is set in cloud-keys.env. "
                "Stores all links in memory for later attribution analysis."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The destination URL (e.g. your blog post, affiliate link, newsletter signup).",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform where you're posting (e.g. 'twitter', 'reddit', 'linkedin', 'devto').",
                    },
                    "campaign": {
                        "type": "string",
                        "description": "Campaign name — usually the niche or content series (e.g. 'ai-automation').",
                    },
                    "medium": {
                        "type": "string",
                        "description": "Traffic medium: 'social', 'email', 'cpc', 'organic'. Default: 'social'.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content variant identifier, e.g. post slug or thread number.",
                    },
                },
                "required": ["url", "platform", "campaign"],
            },
            category="analytics",
        )

    def execute(
        self,
        *,
        url: str,
        platform: str,
        campaign: str,
        medium: str = "social",
        content: str = "",
        **_: Any,
    ) -> ToolResult:
        if not url.startswith("http"):
            return ToolResult(
                tool_name="utm_link",
                content="url must start with http:// or https://",
                success=False,
            )

        utm_url = _build_utm_url(
            url,
            source=platform.lower(),
            medium=medium,
            campaign=campaign,
            content=content,
        )

        short_url = None
        bitly_token = os.environ.get("BITLY_ACCESS_TOKEN", "")
        if bitly_token:
            short_url = _shorten_bitly(utm_url, bitly_token)

        link_data = {
            "original_url": url,
            "utm_url": utm_url,
            "short_url": short_url,
            "platform": platform,
            "campaign": campaign,
            "medium": medium,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _store_link(link_data)

        display_url = short_url or utm_url
        lines = [
            f"✅ Tracked link generated for **{platform}** / **{campaign}**\n",
            f"**Use this URL in your post:**",
            f"`{display_url}`",
            "",
        ]
        if short_url:
            lines.append(f"Full UTM URL: `{utm_url}`")
        else:
            lines.append("*(Add BITLY_ACCESS_TOKEN to cloud-keys.env for shorter links)*")

        return ToolResult(
            tool_name="utm_link",
            content="\n".join(lines),
            success=True,
            metadata=link_data,
        )
