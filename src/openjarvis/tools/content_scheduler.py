"""Content scheduler — queue posts for platform-optimal publish times.

Stores a SQLite-backed queue of pending posts. Each post stores the connector
tool name and its arguments, to be fired by the OperativeAgent when the
scheduled time arrives.

Platform peak engagement windows (UTC):
  twitter    — 14:00, 17:00, 22:00  (9 AM, noon, 5 PM ET)
  linkedin   — 13:00–15:00 Tue–Thu
  reddit     — varies by subreddit; defaults to 14:00 weekdays
  devto      — 09:00 any day
  medium     — 14:00 any day
  beehiiv    — 13:00 Tue/Thu (newsletter day)
  ghost      — 09:00 any day (blog)
  youtube    — 17:00 weekdays, 15:00 weekends
  instagram  — 11:00 and 14:00
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_DB_PATH = Path(os.environ.get("OPENJARVIS_SCHEDULER_DB", str(Path.home() / ".openjarvis" / "scheduled_posts.db")))

# Peak hours per platform (UTC hour)
_PEAK_HOURS: Dict[str, List[int]] = {
    "twitter":   [14, 17, 22],
    "linkedin":  [13, 14],
    "reddit":    [14, 19],
    "devto":     [9, 14],
    "medium":    [14],
    "beehiiv":   [13],
    "ghost":     [9],
    "youtube":   [17],
    "instagram": [11, 14],
}

_PEAK_DAYS: Dict[str, List[int]] = {
    "linkedin": [1, 2, 3],  # Tue=1, Wed=2, Thu=3 (Monday=0)
    "beehiiv":  [1, 3],     # Tue, Thu
}


def _get_db() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            platform    TEXT NOT NULL,
            tool_name   TEXT NOT NULL,
            tool_args   TEXT NOT NULL,   -- JSON
            publish_at  TEXT NOT NULL,   -- ISO8601 UTC
            created_at  TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            fired_at    TEXT
        )
    """)
    conn.commit()
    return conn


def _next_optimal_time(platform: str) -> datetime:
    """Return the next upcoming peak time for a platform (UTC)."""
    now = datetime.now(timezone.utc)
    hours = _PEAK_HOURS.get(platform.lower(), [14])
    days = _PEAK_DAYS.get(platform.lower(), list(range(7)))

    # Look ahead up to 7 days
    for day_offset in range(7):
        from datetime import timedelta
        candidate_day = now + timedelta(days=day_offset)
        if candidate_day.weekday() not in days:
            continue
        for h in sorted(hours):
            candidate = candidate_day.replace(hour=h, minute=0, second=0, microsecond=0)
            if candidate > now:
                return candidate

    # Fallback: tomorrow at 14:00 UTC
    from datetime import timedelta
    tomorrow = now + timedelta(days=1)
    return tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# post_schedule tool
# ---------------------------------------------------------------------------


@ToolRegistry.register("post_schedule")
class PostScheduleTool(BaseTool):
    """Queue a post for automatic publishing at the platform's peak time."""

    tool_id = "post_schedule"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="post_schedule",
            description=(
                "Schedule a post to be published at the optimal engagement time for a platform. "
                "Stores the post in a local queue; the OperativeAgent fires it at the right moment. "
                "If publish_at is omitted, the next platform peak time is used automatically."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Target platform (twitter, linkedin, devto, medium, reddit, beehiiv, ghost, youtube).",
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "The publishing tool to call (e.g. 'twitter_post_thread', 'devto_publish').",
                    },
                    "tool_args": {
                        "type": "object",
                        "description": "Arguments to pass to the publishing tool.",
                    },
                    "publish_at": {
                        "type": "string",
                        "description": "ISO8601 UTC datetime to publish (e.g. '2025-05-10T14:00:00Z'). If omitted, uses next peak time.",
                    },
                },
                "required": ["platform", "tool_name", "tool_args"],
            },
            category="publishing",
        )

    def execute(
        self,
        *,
        platform: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        publish_at: Optional[str] = None,
        **_: Any,
    ) -> ToolResult:
        try:
            if publish_at:
                dt = datetime.fromisoformat(publish_at.rstrip("Z")).replace(tzinfo=timezone.utc)
            else:
                dt = _next_optimal_time(platform)

            now_iso = datetime.now(timezone.utc).isoformat()
            pub_iso = dt.isoformat()

            conn = _get_db()
            conn.execute(
                "INSERT INTO scheduled_posts (platform, tool_name, tool_args, publish_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (platform, tool_name, json.dumps(tool_args), pub_iso, now_iso),
            )
            conn.commit()
            conn.close()

            return ToolResult(
                tool_name="post_schedule",
                content=(
                    f"✅ Post queued for **{platform}** using `{tool_name}`.\n"
                    f"Scheduled for: **{dt.strftime('%A %Y-%m-%d %H:%M UTC')}**\n\n"
                    f"The OperativeAgent will fire this post at the scheduled time. "
                    f"Run post_queue_list to see all pending posts."
                ),
                success=True,
                metadata={"platform": platform, "publish_at": pub_iso, "tool_name": tool_name},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="post_schedule",
                content=f"Scheduling failed: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# post_queue_list tool
# ---------------------------------------------------------------------------


@ToolRegistry.register("post_queue_list")
class PostQueueListTool(BaseTool):
    """List all pending scheduled posts."""

    tool_id = "post_queue_list"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="post_queue_list",
            description="Show all pending (and recently fired) scheduled posts with their publish times.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "fired", "all"],
                        "description": "Filter by status. Default: 'pending'.",
                    },
                },
                "required": [],
            },
            category="publishing",
        )

    def execute(self, *, status: str = "pending", **_: Any) -> ToolResult:
        try:
            conn = _get_db()
            if status == "all":
                rows = conn.execute(
                    "SELECT id, platform, tool_name, publish_at, status FROM scheduled_posts ORDER BY publish_at"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, platform, tool_name, publish_at, status FROM scheduled_posts "
                    "WHERE status=? ORDER BY publish_at",
                    (status,),
                ).fetchall()
            conn.close()

            if not rows:
                return ToolResult(
                    tool_name="post_queue_list",
                    content=f"No {status} posts in the queue.",
                    success=True,
                )

            lines = [f"## Scheduled Posts ({status})\n"]
            for row in rows:
                rid, platform, tool_name, publish_at, st = row
                lines.append(f"- **#{rid}** [{st}] {platform} → `{tool_name}` at {publish_at[:16]} UTC")

            return ToolResult(
                tool_name="post_queue_list",
                content="\n".join(lines),
                success=True,
                metadata={"count": len(rows)},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="post_queue_list",
                content=f"Queue read failed: {exc}",
                success=False,
            )
