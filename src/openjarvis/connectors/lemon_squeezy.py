"""Lemon Squeezy connector — track SaaS subscriptions and digital product sales.

Revenue model: SaaS subscriptions, one-time digital products, pay-what-you-want.
Better than Gumroad for subscription-based products and SaaS.
Authentication: API key.
Set LEMON_SQUEEZY_API_KEY in ~/.openjarvis/cloud-keys.env.

Docs: https://docs.lemonsqueezy.com/api
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://api.lemonsqueezy.com/v1"


@ConnectorRegistry.register("lemon_squeezy")
class LemonSqueezyConnector(BaseConnector):
    """Track SaaS revenue and product sales via Lemon Squeezy."""

    connector_id = "lemon_squeezy"
    display_name = "Lemon Squeezy"
    auth_type = "api_key"

    def __init__(self, api_key: str = "") -> None:
        self._key = api_key or os.environ.get("LEMON_SQUEEZY_API_KEY", "")
        self._status = SyncStatus()

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._key}", "Accept": "application/vnd.api+json"}

    def is_connected(self) -> bool:
        return bool(self._key)

    def disconnect(self) -> None:
        self._key = ""

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resp = httpx.get(
            f"{_BASE}/{path.lstrip('/')}",
            headers=self._headers(),
            params=params or {},
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json()

    def get_stores(self) -> List[Dict[str, Any]]:
        """Return all Lemon Squeezy stores."""
        try:
            return self._get("stores").get("data", [])
        except Exception:
            return []

    def get_products(self) -> List[Dict[str, Any]]:
        """Return all products with pricing info."""
        try:
            return self._get("products").get("data", [])
        except Exception:
            return []

    def get_orders(self, *, page: int = 1) -> List[Dict[str, Any]]:
        """Return recent orders."""
        try:
            return self._get("orders", {"page[number]": page, "page[size]": 50}).get("data", [])
        except Exception:
            return []

    def get_subscriptions(self) -> List[Dict[str, Any]]:
        """Return active subscriptions."""
        try:
            return self._get("subscriptions", {"filter[status]": "active"}).get("data", [])
        except Exception:
            return []

    def get_revenue_summary(self) -> Dict[str, Any]:
        """Return total revenue, MRR from subscriptions, and order count."""
        orders = self.get_orders()
        subs = self.get_subscriptions()

        total_revenue = sum(
            float(o.get("attributes", {}).get("total", 0)) / 100
            for o in orders
        )
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_revenue = sum(
            float(o.get("attributes", {}).get("total", 0)) / 100
            for o in orders
            if o.get("attributes", {}).get("created_at", "").startswith(today_str)
        )
        mrr = sum(
            float(s.get("attributes", {}).get("total", 0)) / 100
            for s in subs
        )

        return {
            "mrr": round(mrr, 2),
            "revenue_today": round(today_revenue, 2),
            "revenue_all_time": round(total_revenue, 2),
            "active_subscriptions": len(subs),
            "total_orders": len(orders),
        }

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected():
            return
        summary = self.get_revenue_summary()
        yield Document(
            doc_id=f"ls-snapshot-{datetime.now().date()}",
            source="lemon_squeezy",
            doc_type="revenue_snapshot",
            content=(
                f"MRR: ${summary['mrr']:.2f}  |  "
                f"Today: ${summary['revenue_today']:.2f}  |  "
                f"Active subs: {summary['active_subscriptions']}  |  "
                f"Total orders: {summary['total_orders']}"
            ),
            title=f"Lemon Squeezy Snapshot {datetime.now().date()}",
            timestamp=datetime.now(),
            metadata=summary,
        )
        self._status.last_sync = datetime.now()

    def sync_status(self) -> SyncStatus:
        return self._status

    def mcp_tools(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="lemon_squeezy_revenue",
                description=(
                    "Get Lemon Squeezy revenue summary: MRR, today's revenue, "
                    "active subscriptions, and total orders."
                ),
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
        ]
