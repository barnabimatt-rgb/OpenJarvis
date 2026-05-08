"""Twitter/X connector — post tweets and threads via the Twitter API v2.

Authentication: OAuth 1.0a (write access).
Set in ~/.openjarvis/cloud-keys.env:
  TWITTER_API_KEY
  TWITTER_API_SECRET
  TWITTER_ACCESS_TOKEN
  TWITTER_ACCESS_SECRET

Free tier allows 1,500 tweets/month — sufficient for daily posting.
Docs: https://developer.twitter.com/en/docs/twitter-api
"""

from __future__ import annotations

import os
import time
import hmac
import hashlib
import base64
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional
from urllib.parse import quote

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_TWEET_URL = "https://api.twitter.com/2/tweets"
_MAX_TWEET_LEN = 280


def _oauth1_header(
    method: str,
    url: str,
    api_key: str,
    api_secret: str,
    access_token: str,
    access_secret: str,
    extra_params: Optional[Dict[str, str]] = None,
) -> str:
    """Build an OAuth 1.0a Authorization header."""
    nonce = uuid.uuid4().hex
    ts = str(int(time.time()))

    oauth_params: Dict[str, str] = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": nonce,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": ts,
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }
    all_params = {**oauth_params, **(extra_params or {})}
    param_str = "&".join(
        f"{quote(k, safe='')}={quote(str(v), safe='')}"
        for k, v in sorted(all_params.items())
    )
    base_string = "&".join([
        method.upper(),
        quote(url, safe=""),
        quote(param_str, safe=""),
    ])
    signing_key = f"{quote(api_secret, safe='')}&{quote(access_secret, safe='')}"
    sig = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params["oauth_signature"] = sig

    header_parts = ", ".join(
        f'{quote(k, safe="")}="{quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )
    return f"OAuth {header_parts}"


@ConnectorRegistry.register("twitter")
class TwitterConnector(BaseConnector):
    """Post tweets and threads to Twitter/X and retrieve basic engagement metrics."""

    connector_id = "twitter"
    display_name = "Twitter / X"
    auth_type = "oauth"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        access_token: str = "",
        access_secret: str = "",
    ) -> None:
        self._api_key = api_key or os.environ.get("TWITTER_API_KEY", "")
        self._api_secret = api_secret or os.environ.get("TWITTER_API_SECRET", "")
        self._access_token = access_token or os.environ.get("TWITTER_ACCESS_TOKEN", "")
        self._access_secret = access_secret or os.environ.get("TWITTER_ACCESS_SECRET", "")
        self._status = SyncStatus()

    def is_connected(self) -> bool:
        return all([self._api_key, self._api_secret, self._access_token, self._access_secret])

    def disconnect(self) -> None:
        self._api_key = self._api_secret = self._access_token = self._access_secret = ""

    def _post_tweet(self, text: str, reply_to: Optional[str] = None) -> Dict[str, Any]:
        """Internal: post a single tweet, optionally as a reply."""
        body: Dict[str, Any] = {"text": text[:_MAX_TWEET_LEN]}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}

        auth = _oauth1_header(
            "POST", _TWEET_URL,
            self._api_key, self._api_secret,
            self._access_token, self._access_secret,
        )
        resp = httpx.post(
            _TWEET_URL,
            headers={"Authorization": auth, "Content-Type": "application/json"},
            json=body,
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", {})

    def post_tweet(self, text: str) -> Dict[str, Any]:
        """Post a single tweet. Returns tweet id and text."""
        return self._post_tweet(text)

    def post_thread(self, tweets: List[str]) -> List[Dict[str, Any]]:
        """Post a reply-chained thread. Returns list of tweet data dicts."""
        results: List[Dict[str, Any]] = []
        reply_to: Optional[str] = None
        for text in tweets:
            result = self._post_tweet(text, reply_to=reply_to)
            results.append(result)
            reply_to = result.get("id")
            if reply_to:
                time.sleep(1.0)  # brief pause between replies
        return results

    def get_tweet_metrics(self, tweet_id: str) -> Dict[str, Any]:
        """Return public metrics for a tweet (impressions, likes, retweets)."""
        try:
            auth = _oauth1_header(
                "GET",
                f"https://api.twitter.com/2/tweets/{tweet_id}",
                self._api_key, self._api_secret,
                self._access_token, self._access_secret,
            )
            resp = httpx.get(
                f"https://api.twitter.com/2/tweets/{tweet_id}",
                headers={"Authorization": auth},
                params={"tweet.fields": "public_metrics"},
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("public_metrics", {})
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # BaseConnector — sync not meaningful for write-only connector
    # ------------------------------------------------------------------

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        return iter([])

    def sync_status(self) -> SyncStatus:
        return self._status

    # ------------------------------------------------------------------
    # MCP tools
    # ------------------------------------------------------------------

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="twitter_post_tweet",
                description="Post a single tweet (max 280 characters) to Twitter/X.",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Tweet text (max 280 characters).",
                        }
                    },
                    "required": ["text"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="twitter_post_thread",
                description=(
                    "Post a reply-chained Twitter/X thread. "
                    "Each string in the list becomes one tweet."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "tweets": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Ordered list of tweet texts (each max 280 chars).",
                        }
                    },
                    "required": ["tweets"],
                },
                category="publishing",
                requires_confirmation=True,
            ),
            ToolSpec(
                name="twitter_get_metrics",
                description="Get engagement metrics (impressions, likes, retweets) for a tweet.",
                parameters={
                    "type": "object",
                    "properties": {
                        "tweet_id": {"type": "string", "description": "Tweet ID to look up."}
                    },
                    "required": ["tweet_id"],
                },
                category="analytics",
            ),
        ]
