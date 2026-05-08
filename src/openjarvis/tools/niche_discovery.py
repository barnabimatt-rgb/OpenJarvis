"""Niche discovery tool — find undersaturated, fast-growing topics with income potential.

Queries free, no-auth sources (Google Trends RSS, HackerNews, Reddit trending,
Product Hunt RSS) and scores each emerging topic on three axes:

  growth_velocity  — how fast interest is rising
  low_competition  — inverse of estimated existing content volume
  monetization     — presence of affiliate/SaaS/ad-friendly signals

Final score (0–100) = growth*0.4 + competition*0.3 + monetization*0.3
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, List, Optional
from urllib.parse import quote_plus

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# ---------------------------------------------------------------------------
# Monetization keyword signals
# ---------------------------------------------------------------------------

_MONEY_SIGNALS = [
    "software", "saas", "tool", "app", "platform", "service", "course",
    "template", "plugin", "extension", "api", "automation", "ai", "affiliate",
    "subscribe", "premium", "pro", "marketplace", "freelance", "agency",
    "consulting", "audit", "coaching", "community", "newsletter", "ebook",
]

# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class NicheResult:
    """A scored niche opportunity."""

    topic: str
    score: float               # 0–100
    growth_score: float        # 0–100
    competition_score: float   # 0–100
    monetization_score: float  # 0–100
    rationale: str
    content_angles: List[str] = field(default_factory=list)
    source: str = ""


# ---------------------------------------------------------------------------
# Source scrapers (all free, no auth)
# ---------------------------------------------------------------------------


def _fetch_google_trends_rss(geo: str = "US") -> List[str]:
    """Return topic strings from the Google Trends daily trending RSS feed."""
    url = f"https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"
    try:
        resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        topics: List[str] = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            if title:
                topics.append(title.strip())
        return topics[:20]
    except Exception:
        return []


def _fetch_hackernews_topics(limit: int = 15) -> List[str]:
    """Return titles from the top HN stories."""
    try:
        resp = httpx.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15.0
        )
        ids = resp.json()[:limit]
        topics: List[str] = []
        for sid in ids:
            item_resp = httpx.get(
                f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=10.0
            )
            item = item_resp.json()
            if item and item.get("title"):
                topics.append(item["title"])
        return topics
    except Exception:
        return []


def _fetch_reddit_trending() -> List[str]:
    """Return display names of trending subreddits (no auth required)."""
    try:
        headers = {"User-Agent": "openjarvis-niche-discovery/1.0"}
        resp = httpx.get(
            "https://www.reddit.com/r/trendingsubreddits/.json?limit=10",
            headers=headers,
            timeout=15.0,
            follow_redirects=True,
        )
        resp.raise_for_status()
        data = resp.json()
        posts = data.get("data", {}).get("children", [])
        topics: List[str] = []
        for post in posts:
            title = post.get("data", {}).get("title", "")
            if title:
                # Strip the "Trending subreddits for..." prefix
                clean = re.sub(r"^Trending subreddits for [^:]+:\s*", "", title)
                for part in re.split(r"[,/]", clean):
                    t = part.strip(" /r").strip()
                    if t and not t.startswith("r/"):
                        topics.append(t)
        return topics[:15]
    except Exception:
        return []


def _fetch_producthunt_rss() -> List[str]:
    """Return product names from the Product Hunt RSS feed."""
    try:
        resp = httpx.get(
            "https://www.producthunt.com/feed", timeout=15.0, follow_redirects=True
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        topics: List[str] = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            if title:
                topics.append(title.strip())
        return topics[:15]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _estimate_competition(topic: str) -> float:
    """Estimate low-competition score (0–100) via DuckDuckGo result count heuristic.

    We check how many characters appear in the result count string from a
    DDG HTML response — a rough but zero-cost proxy for content saturation.
    Fewer results → higher competition score (more opportunity).
    """
    try:
        headers = {"User-Agent": "openjarvis-niche-discovery/1.0"}
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(topic)}"
        resp = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        text = resp.text
        # DDG doesn't expose exact counts but result density in HTML is a signal
        result_blocks = text.count('class="result__body"')
        # Fewer result blocks → less competition → higher score
        if result_blocks == 0:
            return 90.0
        elif result_blocks < 4:
            return 75.0
        elif result_blocks < 8:
            return 55.0
        elif result_blocks < 12:
            return 35.0
        else:
            return 20.0
    except Exception:
        return 50.0


def _monetization_score(topic: str) -> float:
    """Score monetization potential based on keyword overlap (0–100)."""
    lowered = topic.lower()
    hits = sum(1 for kw in _MONEY_SIGNALS if kw in lowered)
    # Also reward multi-word topics (more specific = more monetizable)
    word_count_bonus = min(len(topic.split()), 5) * 3
    raw = hits * 15 + word_count_bonus
    return min(raw, 100.0)


def _growth_score(topic: str, trends_topics: List[str]) -> float:
    """Estimate growth velocity (0–100).

    Topics that appear in Google Trends get a high base. HN/Reddit/PH topics
    get medium scores. Position in the list amplifies the score.
    """
    lower = topic.lower()
    for i, t in enumerate(trends_topics):
        if lower in t.lower() or t.lower() in lower:
            # Earlier position = more trending
            position_bonus = max(0, 20 - i)
            return min(70.0 + position_bonus, 100.0)
    return 45.0  # Still potentially interesting if from other sources


def _deduplicate(topics: List[str]) -> List[str]:
    """Remove near-duplicate topics (case-insensitive, word-overlap)."""
    seen: List[str] = []
    for t in topics:
        lower = t.lower()
        if not any(lower == s.lower() or lower in s.lower() or s.lower() in lower for s in seen):
            seen.append(t)
    return seen


def _generate_angles(topic: str) -> List[str]:
    """Generate three default content angles for a topic."""
    return [
        f"The beginner's guide to {topic}",
        f"Why {topic} is the next big opportunity in 2025",
        f"5 tools for {topic} that nobody is talking about",
    ]


# ---------------------------------------------------------------------------
# Main discovery function
# ---------------------------------------------------------------------------


def discover_niches(top_k: int = 5, min_score: float = 40.0) -> List[NicheResult]:
    """Fetch trending sources, score each topic, return top results."""
    # Gather from all sources
    trends = _fetch_google_trends_rss()
    hn = _fetch_hackernews_topics()
    reddit = _fetch_reddit_trending()
    ph = _fetch_producthunt_rss()

    all_topics = _deduplicate(trends + hn + reddit + ph)

    results: List[NicheResult] = []
    for topic in all_topics[:40]:  # Cap at 40 to keep latency reasonable
        g = _growth_score(topic, trends)
        c = _estimate_competition(topic)
        m = _monetization_score(topic)
        score = round(g * 0.4 + c * 0.3 + m * 0.3, 1)

        if score < min_score:
            continue

        source = "google_trends" if any(topic.lower() in t.lower() for t in trends) else \
                 "hackernews" if any(topic.lower() in t.lower() for t in hn) else \
                 "reddit" if any(topic.lower() in t.lower() for t in reddit) else "producthunt"

        results.append(NicheResult(
            topic=topic,
            score=score,
            growth_score=g,
            competition_score=c,
            monetization_score=m,
            rationale=(
                f"Growth: {g:.0f}/100 · Competition opportunity: {c:.0f}/100 · "
                f"Monetization potential: {m:.0f}/100. Source: {source}."
            ),
            content_angles=_generate_angles(topic),
            source=source,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@ToolRegistry.register("niche_discovery")
class NicheDiscoveryTool(BaseTool):
    """Discover undersaturated, fast-growing niches with passive income potential."""

    tool_id = "niche_discovery"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="niche_discovery",
            description=(
                "Scan Google Trends, HackerNews, Reddit, and Product Hunt to find "
                "undersaturated, fast-growing niches ranked by income potential. "
                "Returns topics with scores, rationale, and ready-made content angles."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top niches to return.",
                        "default": 5,
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum composite score (0–100) to include.",
                        "default": 40.0,
                    },
                },
                "required": [],
            },
            category="research",
            timeout_seconds=60.0,
            metadata={"sources": ["google_trends", "hackernews", "reddit", "producthunt"]},
        )

    def execute(self, *, top_k: int = 5, min_score: float = 40.0, **_: Any) -> ToolResult:
        try:
            results = discover_niches(top_k=top_k, min_score=min_score)
            if not results:
                return ToolResult(
                    tool_name="niche_discovery",
                    content="No niches found above the minimum score threshold. Try lowering min_score.",
                    success=True,
                )

            lines = [f"## Top {len(results)} Niche Opportunities\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"### {i}. {r.topic}  (score: {r.score}/100)")
                lines.append(f"**{r.rationale}**")
                lines.append("\nContent angles:")
                for angle in r.content_angles:
                    lines.append(f"- {angle}")
                lines.append("")

            return ToolResult(
                tool_name="niche_discovery",
                content="\n".join(lines),
                success=True,
                metadata={"niches": [
                    {"topic": r.topic, "score": r.score, "source": r.source}
                    for r in results
                ]},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="niche_discovery",
                content=f"Niche discovery failed: {exc}",
                success=False,
            )
