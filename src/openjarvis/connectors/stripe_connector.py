"""Stripe revenue connector — read-only revenue metrics via the Stripe API.

Use a restricted API key with read-only permissions (never a full secret key).
Set STRIPE_SECRET_KEY in ~/.openjarvis/cloud-keys.env.

Docs: https://stripe.com/docs/api
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://api.stripe.com/v1"


@ConnectorRegistry.register("stripe")
class StripeConnector(BaseConnector):
    """Read revenue, MRR, and customer metrics from Stripe."""

    connector_id = "stripe"
    display_name = "Stripe Revenue"
    auth_type = "api_key"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key or os.environ.get("STRIPE_SECRET_KEY", "")
        self._status = SyncStatus()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resp = httpx.get(
            f"{_BASE}/{path.lstrip('/')}",
            auth=(self._api_key, ""),
            params=params or {},
            timeout=20.0,
        )
        resp.raise_for_status()
        return resp.json()

    def is_connected(self) -> bool:
        return bool(self._api_key)

    def disconnect(self) -> None:
        self._api_key = ""

    # ------------------------------------------------------------------
    # Revenue helpers
    # ------------------------------------------------------------------

    def get_mrr(self) -> float:
        """Estimate MRR from active subscriptions (sum of monthly-normalised amounts)."""
        try:
            data = self._get("subscriptions", {"status": "active", "limit": 100})
            mrr = 0.0
            for sub in data.get("data", []):
                for item in sub.get("items", {}).get("data", []):
                    price = item.get("price", {})
                    unit = price.get("unit_amount", 0) or 0
                    currency_div = 100.0
                    interval = price.get("recurring", {}).get("interval", "month")
                    interval_count = price.get("recurring", {}).get("interval_count", 1) or 1
                    qty = item.get("quantity", 1) or 1
                    monthly = unit / currency_div * qty
                    if interval == "year":
                        monthly = monthly / (12 * interval_count)
                    elif interval == "week":
                        monthly = monthly * (4.33 / interval_count)
                    mrr += monthly
            return round(mrr, 2)
        except Exception:
            return 0.0

    def get_revenue_today(self) -> float:
        """Return total charges captured today (UTC)."""
        try:
            today_start = int(
                datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
            )
            data = self._get("charges", {
                "created[gte]": today_start,
                "limit": 100,
                "paid": "true",
            })
            total = sum(c.get("amount", 0) for c in data.get("data", [])) / 100.0
            return round(total, 2)
        except Exception:
            return 0.0

    def get_new_customers(self, days: int = 7) -> int:
        """Count new customers in the last N days."""
        try:
            since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
            data = self._get("customers", {"created[gte]": since, "limit": 100})
            return len(data.get("data", []))
        except Exception:
            return 0

    def get_revenue_summary(self) -> Dict[str, Any]:
        """Return a combined revenue snapshot."""
        return {
            "mrr": self.get_mrr(),
            "revenue_today": self.get_revenue_today(),
            "new_customers_7d": self.get_new_customers(days=7),
        }

    # ------------------------------------------------------------------
    # BaseConnector
    # ------------------------------------------------------------------

    def sync(
        self, *, since: Optional[datetime] = None, cursor: Optional[str] = None
    ) -> Iterator[Document]:
        if not self.is_connected():
            return
        summary = self.get_revenue_summary()
        yield Document(
            doc_id=f"stripe-snapshot-{datetime.now().date()}",
            source="stripe",
            doc_type="revenue_snapshot",
            content=(
                f"MRR: ${summary['mrr']:.2f}  |  "
                f"Revenue today: ${summary['revenue_today']:.2f}  |  "
                f"New customers (7d): {summary['new_customers_7d']}"
            ),
            title=f"Stripe Revenue Snapshot {datetime.now().date()}",
            timestamp=datetime.now(),
            metadata=summary,
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
                name="stripe_revenue_summary",
                description=(
                    "Get a revenue snapshot from Stripe: MRR, today's revenue, "
                    "and new customers in the last 7 days."
                ),
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
        ]
