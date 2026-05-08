"""Patreon connector — track patron counts and monthly earnings.

Revenue model: Membership tiers — fans pay monthly for exclusive content.
Authentication: OAuth 2.0 Creator access token.
Set PATREON_ACCESS_TOKEN in ~/.openjarvis/cloud-keys.env.

Docs: https://docs.patreon.com/#apiv2-resources
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://www.patreon.com/api/oauth2/v2"


@ConnectorRegistry.register("patreon")
class PatreonConnector(BaseConnector):
    """Track Patreon patron count, tier breakdown, and monthly earnings."""

    connector_id = "patreon"
    display_name = "Patreon"
    auth_type = "oauth"

    def __init__(self, access_token: str = "") -> None:
        self._token = access_token or os.environ.get("PATREON_ACCESS_TOKEN", "")
        self._status = SyncStatus()

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def is_connected(self) -> bool:
        return bool(self._token)

    def disconnect(self) -> None:
        self._token = ""

    def get_campaign_summary(self) -> Dict[str, Any]:
        """Return patron count, pledge total, and tier breakdown."""
        try:
            resp = httpx.get(
                f"{_BASE}/campaigns",
                headers=self._headers(),
                params={
                    "fields[campaign]": "patron_count,pledge_sum,creation_count,currency",
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            campaigns = resp.json().get("data", [])
            if campaigns:
                attrs = campaigns[0].get("attributes", {})
                return {
                    "patron_count": attrs.get("patron_count", 0),
                    "pledge_sum_cents": attrs.get("pledge_sum", 0),
                    "pledge_sum_dollars": round(attrs.get("pledge_sum", 0) / 100, 2),
                    "currency": attrs.get("currency", "USD"),
                    "creation_count": attrs.get("creation_count", 0),
                }
        except Exception:
            pass
        return {"patron_count": 0, "pledge_sum_dollars": 0.0}

    def get_patrons(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent active patrons."""
        try:
            campaigns_resp = httpx.get(
                f"{_BASE}/campaigns", headers=self._headers(),
                params={"fields[campaign]": "patron_count"}, timeout=15.0,
            )
            campaigns_resp.raise_for_status()
            campaigns = campaigns_resp.json().get("data", [])
            if not campaigns:
                return []
            campaign_id = campaigns[0]["id"]
            resp = httpx.get(
                f"{_BASE}/campaigns/{campaign_id}/members",
                headers=self._headers(),
                params={
                    "fields[member]": "full_name,email,pledge_relationship_start,currently_entitled_amount_cents",
                    "page[count]": limit,
                },
                timeout=20.0,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception:
            return []

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected():
            return
        summary = self.get_campaign_summary()
        yield Document(
            doc_id=f"patreon-snapshot-{datetime.now().date()}",
            source="patreon",
            doc_type="membership_snapshot",
            content=(
                f"Patrons: {summary['patron_count']}  |  "
                f"Monthly earnings: ${summary['pledge_sum_dollars']:.2f}"
            ),
            title=f"Patreon Snapshot {datetime.now().date()}",
            timestamp=datetime.now(),
            metadata=summary,
        )
        self._status.last_sync = datetime.now()

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="patreon_summary",
                description=(
                    "Get Patreon campaign summary: total patrons, monthly pledge total, "
                    "and creation count."
                ),
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
        ]
