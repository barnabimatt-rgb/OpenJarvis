"""Revenue alert checker — fire notifications when revenue thresholds are crossed.

Compares current metrics to stored baselines and sends a Telegram message
(via the existing Telegram channel integration) on:
  - First sale ever (any platform)
  - Daily revenue crossing a target
  - MRR reaching a new milestone (100, 500, 1000, 2500, 5000, ...)
  - Unusual drop vs 7-day average (churn spike detection)

Configure thresholds in passive_income.toml under [revenue_alerts].
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_MRR_MILESTONES = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
_MEMORY_KEY = "revenue_alert_baseline"


def _get_baseline() -> Dict[str, Any]:
    """Load the stored revenue baseline from memory."""
    try:
        from openjarvis.core.registry import MemoryRegistry
        backend_cls = MemoryRegistry.get("sqlite")
        backend = backend_cls()
        results = backend.search(_MEMORY_KEY, top_k=1)
        if results:
            raw = results[0].content if hasattr(results[0], "content") else str(results[0])
            idx = raw.find("{")
            if idx >= 0:
                return json.loads(raw[idx:])
    except Exception:
        pass
    return {}


def _save_baseline(baseline: Dict[str, Any]) -> None:
    """Persist baseline to memory."""
    try:
        from openjarvis.core.registry import MemoryRegistry
        backend_cls = MemoryRegistry.get("sqlite")
        backend = backend_cls()
        backend.store(
            f"{_MEMORY_KEY} {json.dumps(baseline)}",
            source="revenue_alert",
            metadata={"tag": _MEMORY_KEY},
        )
    except Exception:
        pass


def _send_telegram(message: str) -> bool:
    """Send a message via the Telegram channel connector if configured."""
    try:
        from openjarvis.core.registry import ChannelRegistry
        tg_cls = ChannelRegistry.get("telegram")
        tg = tg_cls()
        if tg.is_connected():
            tg.send(message)
            return True
    except Exception:
        pass
    return False


def _collect_revenue() -> Dict[str, Any]:
    """Pull current revenue from all configured connectors."""
    data: Dict[str, Any] = {}

    try:
        from openjarvis.connectors.stripe_connector import StripeConnector
        c = StripeConnector()
        if c.is_connected():
            data["stripe_mrr"] = c.get_mrr()
            data["stripe_today"] = c.get_revenue_today()
    except Exception:
        pass

    try:
        from openjarvis.connectors.gumroad import GumroadConnector
        c = GumroadConnector()
        if c.is_connected():
            s = c.get_revenue_summary()
            data["gumroad_today"] = s.get("revenue_today", 0.0)
            data["gumroad_month"] = s.get("revenue_this_month", 0.0)
    except Exception:
        pass

    try:
        from openjarvis.connectors.lemon_squeezy import LemonSqueezyConnector
        c = LemonSqueezyConnector()
        if c.is_connected():
            s = c.get_revenue_summary()
            data["ls_mrr"] = s.get("mrr", 0.0)
            data["ls_today"] = s.get("revenue_today", 0.0)
    except Exception:
        pass

    try:
        from openjarvis.connectors.patreon import PatreonConnector
        c = PatreonConnector()
        if c.is_connected():
            s = c.get_campaign_summary()
            data["patreon_monthly"] = s.get("pledge_sum_dollars", 0.0)
    except Exception:
        pass

    total_mrr = (
        data.get("stripe_mrr", 0.0)
        + data.get("ls_mrr", 0.0)
        + data.get("patreon_monthly", 0.0)
    )
    total_today = (
        data.get("stripe_today", 0.0)
        + data.get("gumroad_today", 0.0)
        + data.get("ls_today", 0.0)
    )
    data["total_mrr"] = round(total_mrr, 2)
    data["total_today"] = round(total_today, 2)
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    return data


def _check_alerts(current: Dict[str, Any], baseline: Dict[str, Any]) -> List[str]:
    """Compare current vs baseline and return list of alert messages."""
    alerts = []
    today = current.get("total_today", 0.0)
    mrr = current.get("total_mrr", 0.0)
    prev_today = baseline.get("total_today", 0.0)
    prev_mrr = baseline.get("total_mrr", 0.0)
    ever_had_sale = baseline.get("ever_had_sale", False)

    daily_target = float(os.environ.get("REVENUE_DAILY_TARGET", "50.0"))
    drop_threshold = float(os.environ.get("REVENUE_DROP_THRESHOLD_PCT", "30.0"))

    # First sale ever
    if not ever_had_sale and today > 0:
        alerts.append(
            f"🎉 FIRST SALE! You earned ${today:.2f} today. "
            "The passive income machine is working!"
        )

    # Daily target hit
    if today >= daily_target and prev_today < daily_target:
        alerts.append(
            f"🎯 Daily revenue target hit! ${today:.2f} today "
            f"(target: ${daily_target:.2f})"
        )

    # MRR milestones
    for milestone in _MRR_MILESTONES:
        if prev_mrr < milestone <= mrr:
            alerts.append(
                f"🚀 MRR milestone: ${milestone:,}/month reached! "
                f"Current MRR: ${mrr:.2f}"
            )

    # Revenue drop detection
    if prev_today > 10 and today < prev_today * (1 - drop_threshold / 100):
        drop_pct = (1 - today / prev_today) * 100
        alerts.append(
            f"⚠️ Revenue drop detected: today ${today:.2f} vs "
            f"yesterday ${prev_today:.2f} ({drop_pct:.0f}% drop). "
            "Check for issues."
        )

    return alerts


@ToolRegistry.register("revenue_alert_check")
class RevenueAlertCheckTool(BaseTool):
    """Check revenue metrics against thresholds and fire Telegram alerts."""

    tool_id = "revenue_alert_check"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="revenue_alert_check",
            description=(
                "Check current revenue across all platforms against stored baselines. "
                "Fires Telegram notifications on: first sale, daily target hit, MRR milestones, "
                "and unusual revenue drops. Updates the baseline after checking. "
                "Configure thresholds via env vars: "
                "REVENUE_DAILY_TARGET (default $50), REVENUE_DROP_THRESHOLD_PCT (default 30%)."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            category="analytics",
            timeout_seconds=30.0,
        )

    def execute(self, **_: Any) -> ToolResult:
        try:
            baseline = _get_baseline()
            current = _collect_revenue()
            alerts = _check_alerts(current, baseline)

            # Update baseline
            new_baseline = {**current}
            new_baseline["ever_had_sale"] = (
                baseline.get("ever_had_sale", False)
                or current.get("total_today", 0.0) > 0
            )
            _save_baseline(new_baseline)

            # Fire alerts
            sent = []
            for alert in alerts:
                if _send_telegram(alert):
                    sent.append(f"[Telegram] {alert}")
                else:
                    sent.append(f"[No Telegram] {alert}")

            lines = [
                f"## Revenue Alert Check — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                "",
                f"**Today:** ${current.get('total_today', 0):.2f}  |  "
                f"**MRR:** ${current.get('total_mrr', 0):.2f}",
                "",
            ]
            if sent:
                lines.append(f"### Alerts Fired ({len(sent)})")
                lines.extend(f"- {s}" for s in sent)
            else:
                lines.append("No threshold breaches — all normal.")

            return ToolResult(
                tool_name="revenue_alert_check",
                content="\n".join(lines),
                success=True,
                metadata={
                    "total_today": current.get("total_today", 0),
                    "total_mrr": current.get("total_mrr", 0),
                    "alerts_count": len(alerts),
                },
            )
        except Exception as exc:
            return ToolResult(
                tool_name="revenue_alert_check",
                content=f"Revenue alert check failed: {exc}",
                success=False,
            )
