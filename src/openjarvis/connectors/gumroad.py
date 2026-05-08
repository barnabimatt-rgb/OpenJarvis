"""Gumroad connector — track digital product sales via the Gumroad API v2.

Set GUMROAD_ACCESS_TOKEN in ~/.openjarvis/cloud-keys.env.

Docs: https://app.gumroad.com/api
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterator, List, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.registry import ConnectorRegistry
from openjarvis.tools._stubs import ToolSpec

_BASE = "https://api.gumroad.com/v2"


@ConnectorRegistry.register("gumroad")
class GumroadConnector(BaseConnector):
    """Read digital product sales and revenue from Gumroad."""

    connector_id = "gumroad"
    display_name = "Gumroad Sales"
    auth_type = "api_key"

    def __init__(self, access_token: str = "") -> None:
        self._token = access_token or os.environ.get("GUMROAD_ACCESS_TOKEN", "")
        self._status = SyncStatus()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        p = {"access_token": self._token, **(params or {})}
        resp = httpx.get(f"{_BASE}/{path.lstrip('/')}", params=p, timeout=20.0)
        resp.raise_for_status()
        return resp.json()

    def is_connected(self) -> bool:
        return bool(self._token)

    def disconnect(self) -> None:
        self._token = ""

    # ------------------------------------------------------------------
    # Data methods
    # ------------------------------------------------------------------

    def get_products(self) -> List[Dict[str, Any]]:
        """Return all published Gumroad products."""
        try:
            return self._get("products").get("products", [])
        except Exception:
            return []

    def get_sales(self, *, after: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return recent sales, optionally filtered to after a date string (YYYY-MM-DD)."""
        params: Dict[str, Any] = {}
        if after:
            params["after"] = after
        try:
            return self._get("sales", params).get("sales", [])
        except Exception:
            return []

    def get_revenue_summary(self) -> Dict[str, Any]:
        """Return revenue totals: today, this month, all time."""
        try:
            all_sales = self.get_sales()
            now = datetime.now(timezone.utc)
            today_str = now.strftime("%Y-%m-%d")
            month_str = now.strftime("%Y-%m")

            total = 0.0
            today_total = 0.0
            month_total = 0.0

            for sale in all_sales:
                price = float(sale.get("price", 0)) / 100.0
                created = sale.get("created_at", "")
                total += price
                if created.startswith(today_str):
                    today_total += price
                if created.startswith(month_str):
                    month_total += price

            return {
                "revenue_today": round(today_total, 2),
                "revenue_this_month": round(month_total, 2),
                "revenue_all_time": round(total, 2),
                "total_sales": len(all_sales),
            }
        except Exception:
            return {
                "revenue_today": 0.0,
                "revenue_this_month": 0.0,
                "revenue_all_time": 0.0,
                "total_sales": 0,
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
            doc_id=f"gumroad-snapshot-{datetime.now().date()}",
            source="gumroad",
            doc_type="sales_snapshot",
            content=(
                f"Today: ${summary['revenue_today']:.2f}  |  "
                f"This month: ${summary['revenue_this_month']:.2f}  |  "
                f"All time: ${summary['revenue_all_time']:.2f}  |  "
                f"Total sales: {summary['total_sales']}"
            ),
            title=f"Gumroad Sales Snapshot {datetime.now().date()}",
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
                name="gumroad_sales_summary",
                description=(
                    "Get digital product sales summary from Gumroad: "
                    "revenue today, this month, all time, and total sale count."
                ),
                parameters={"type": "object", "properties": {}, "required": []},
                category="analytics",
            ),
        ]
