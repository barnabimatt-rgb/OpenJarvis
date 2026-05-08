"""Analytics aggregator — unified dashboard across all passive income platforms.

Pulls live stats from every configured connector in parallel. Any connector
that is not configured (no API key) is silently skipped and marked as
"not connected" in the output.
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _safe_call(label: str, fn) -> Tuple[str, Optional[dict], Optional[str]]:
    """Run fn(), return (label, result_dict, error_message)."""
    try:
        return label, fn(), None
    except Exception as exc:
        return label, None, str(exc)


def _fetch_all() -> Dict[str, Any]:
    """Fetch stats from all connectors concurrently. Missing keys → skip gracefully."""
    tasks = {}

    # ---- Revenue ----
    try:
        from openjarvis.connectors.stripe_connector import StripeConnector
        c = StripeConnector()
        if c.is_connected():
            tasks["stripe"] = lambda: {
                "mrr": c.get_mrr(),
                "revenue_today": c.get_revenue_today(),
                "new_customers_7d": c.get_new_customers(days=7),
            }
    except Exception:
        pass

    try:
        from openjarvis.connectors.gumroad import GumroadConnector
        c = GumroadConnector()
        if c.is_connected():
            tasks["gumroad"] = lambda: c.get_revenue_summary()
    except Exception:
        pass

    try:
        from openjarvis.connectors.lemon_squeezy import LemonSqueezyConnector
        c = LemonSqueezyConnector()
        if c.is_connected():
            tasks["lemon_squeezy"] = lambda: c.get_revenue_summary()
    except Exception:
        pass

    try:
        from openjarvis.connectors.patreon import PatreonConnector
        c = PatreonConnector()
        if c.is_connected():
            tasks["patreon"] = lambda: c.get_campaign_summary()
    except Exception:
        pass

    # ---- Email / Newsletter ----
    try:
        from openjarvis.connectors.beehiiv import BeehiivConnector
        c = BeehiivConnector()
        if c.is_connected():
            pubs = c.get_publications()
            if pubs:
                pub_id = pubs[0].get("id", "")
                tasks["beehiiv"] = lambda: {
                    "subscribers": c.get_subscriber_count(pub_id),
                    "publication": pubs[0].get("name", ""),
                }
    except Exception:
        pass

    try:
        from openjarvis.connectors.convertkit import ConvertKitConnector
        c = ConvertKitConnector()
        if c.is_connected():
            tasks["convertkit"] = lambda: {
                "subscribers": c.get_subscriber_count(),
                "recent_broadcasts": len(c.get_broadcasts()),
            }
    except Exception:
        pass

    # ---- Publishing ----
    try:
        from openjarvis.connectors.youtube import YouTubeConnector
        c = YouTubeConnector()
        if c.is_connected():
            tasks["youtube"] = lambda: c.get_channel_stats()
    except Exception:
        pass

    try:
        from openjarvis.connectors.devto import DevToConnector
        c = DevToConnector()
        if c.is_connected():
            articles = c.get_articles(per_page=5)
            tasks["devto"] = lambda: {
                "article_count": len(articles),
                "total_reactions": sum(a.get("public_reactions_count", 0) for a in articles),
                "total_views": sum(a.get("page_views_count", 0) for a in articles),
            }
    except Exception:
        pass

    try:
        from openjarvis.connectors.twitter import TwitterConnector
        c = TwitterConnector()
        if c.is_connected():
            tasks["twitter"] = lambda: {"status": "connected"}
    except Exception:
        pass

    # Execute all tasks concurrently
    results: Dict[str, Any] = {}
    if not tasks:
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks), 8)) as pool:
        futures = {pool.submit(_safe_call, label, fn): label for label, fn in tasks.items()}
        for future in concurrent.futures.as_completed(futures, timeout=30):
            label, data, err = future.result()
            if err:
                results[label] = {"error": err}
            elif data is not None:
                results[label] = data

    return results


def _format_dashboard(data: Dict[str, Any]) -> str:
    if not data:
        return "No platforms connected. Add API keys to ~/.openjarvis/cloud-keys.env."

    lines = [f"## Analytics Dashboard — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"]

    # Revenue section
    revenue_lines = []
    stripe = data.get("stripe", {})
    gumroad = data.get("gumroad", {})
    ls = data.get("lemon_squeezy", {})
    patreon = data.get("patreon", {})

    if stripe and "error" not in stripe:
        revenue_lines.append(f"| Stripe    | MRR: ${stripe.get('mrr', 0):.2f} | Today: ${stripe.get('revenue_today', 0):.2f} | New customers (7d): {stripe.get('new_customers_7d', 0)} |")
    if gumroad and "error" not in gumroad:
        revenue_lines.append(f"| Gumroad   | All time: ${gumroad.get('revenue_all_time', 0):.2f} | This month: ${gumroad.get('revenue_this_month', 0):.2f} | Today: ${gumroad.get('revenue_today', 0):.2f} |")
    if ls and "error" not in ls:
        revenue_lines.append(f"| Lemon 🍋  | MRR: ${ls.get('mrr', 0):.2f} | Active subs: {ls.get('active_subscriptions', 0)} | Today: ${ls.get('revenue_today', 0):.2f} |")
    if patreon and "error" not in patreon:
        revenue_lines.append(f"| Patreon   | Patrons: {patreon.get('patron_count', 0)} | Monthly: ${patreon.get('pledge_sum_dollars', 0):.2f} | Currency: {patreon.get('currency', 'USD')} |")

    if revenue_lines:
        lines.append("### 💰 Revenue\n| Platform | Metric 1 | Metric 2 | Metric 3 |")
        lines.append("|----------|----------|----------|----------|")
        lines.extend(revenue_lines)
        lines.append("")

    # Audience section
    audience_lines = []
    beehiiv = data.get("beehiiv", {})
    ck = data.get("convertkit", {})
    yt = data.get("youtube", {})

    if beehiiv and "error" not in beehiiv:
        pub = beehiiv.get("publication", "newsletter")
        audience_lines.append(f"| Beehiiv ({pub[:20]}) | Subscribers: {beehiiv.get('subscribers', 0):,} | — | — |")
    if ck and "error" not in ck:
        audience_lines.append(f"| ConvertKit | Subscribers: {ck.get('subscribers', 0):,} | Broadcasts: {ck.get('recent_broadcasts', 0)} | — |")
    if yt and "error" not in yt:
        audience_lines.append(
            f"| YouTube | Subscribers: {yt.get('subscriberCount', 0):,} | Views: {yt.get('viewCount', 0):,} | Videos: {yt.get('videoCount', 0)} |"
        )

    if audience_lines:
        lines.append("### 👥 Audience\n| Platform | Metric 1 | Metric 2 | Metric 3 |")
        lines.append("|----------|----------|----------|----------|")
        lines.extend(audience_lines)
        lines.append("")

    # Content section
    content_lines = []
    devto = data.get("devto", {})
    twitter = data.get("twitter", {})

    if devto and "error" not in devto:
        content_lines.append(f"| Dev.to | Articles: {devto.get('article_count', 0)} | Reactions: {devto.get('total_reactions', 0)} | Views: {devto.get('total_views', 0)} |")
    if twitter and "error" not in twitter:
        content_lines.append("| Twitter/X | Connected | — | — |")

    if content_lines:
        lines.append("### 📝 Content\n| Platform | Metric 1 | Metric 2 | Metric 3 |")
        lines.append("|----------|----------|----------|----------|")
        lines.extend(content_lines)
        lines.append("")

    # Errors
    errors = [(k, v["error"]) for k, v in data.items() if isinstance(v, dict) and "error" in v]
    if errors:
        lines.append("### ⚠️ Errors")
        for k, e in errors:
            lines.append(f"- {k}: {e[:120]}")

    return "\n".join(lines)


@ToolRegistry.register("analytics_summary")
class AnalyticsSummaryTool(BaseTool):
    """Pull a unified analytics dashboard from all connected platforms."""

    tool_id = "analytics_summary"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="analytics_summary",
            description=(
                "Fetch live stats from all configured passive income platforms in parallel "
                "and return a single Markdown dashboard. Covers: Stripe MRR, Gumroad sales, "
                "Lemon Squeezy subscriptions, Patreon patrons, Beehiiv/ConvertKit subscribers, "
                "YouTube channel stats, Dev.to article performance. "
                "Any platform without a configured API key is skipped silently."
            ),
            parameters={"type": "object", "properties": {}, "required": []},
            category="analytics",
            timeout_seconds=35.0,
        )

    def execute(self, **_: Any) -> ToolResult:
        try:
            data = _fetch_all()
            dashboard = _format_dashboard(data)
            return ToolResult(
                tool_name="analytics_summary",
                content=dashboard,
                success=True,
                metadata={"platforms_queried": list(data.keys())},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="analytics_summary",
                content=f"Analytics aggregation failed: {exc}",
                success=False,
            )
