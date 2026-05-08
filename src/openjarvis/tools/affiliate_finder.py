"""Affiliate program finder — locate monetizable affiliate programs for any niche.

Uses free, public-facing sources:
  - Google autocomplete (affiliate program discovery)
  - DuckDuckGo HTML search (no auth required)
  - Curated high-commission network list (Impact, ShareASale, CJ, PartnerStack)

Returns programs ranked by commission rate and relevance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# ---------------------------------------------------------------------------
# Curated high-value affiliate networks and programs (no auth lookup needed)
# ---------------------------------------------------------------------------

_NETWORKS: List[Dict[str, Any]] = [
    # SaaS / Developer tools
    {"name": "HubSpot", "commission": "30% recurring", "category": "crm saas marketing", "url": "hubspot.com/affiliates", "cookie_days": 90},
    {"name": "ConvertKit", "commission": "30% recurring", "category": "email marketing newsletter", "url": "convertkit.com/affiliates", "cookie_days": 60},
    {"name": "Beehiiv", "commission": "50% for 12 months", "category": "email newsletter", "url": "beehiiv.com/affiliates", "cookie_days": 30},
    {"name": "Ghost", "commission": "commission via partners", "category": "blog publishing cms", "url": "ghost.org/pricing", "cookie_days": 30},
    {"name": "Shopify", "commission": "$150 per referral", "category": "ecommerce shop store", "url": "shopify.com/affiliates", "cookie_days": 30},
    {"name": "Notion", "commission": "credit-based", "category": "productivity notes workspace", "url": "notion.so/refer", "cookie_days": 30},
    {"name": "Airtable", "commission": "credit-based", "category": "database spreadsheet productivity", "url": "airtable.com", "cookie_days": 30},
    {"name": "Webflow", "commission": "up to 50% recurring", "category": "web design nocode website builder", "url": "webflow.com/affiliates", "cookie_days": 90},
    {"name": "ClickFunnels", "commission": "40% recurring", "category": "funnel sales marketing", "url": "clickfunnels.com/affiliates", "cookie_days": 45},
    {"name": "Kajabi", "commission": "30% recurring", "category": "course online education membership", "url": "kajabi.com/affiliates", "cookie_days": 30},
    {"name": "Teachable", "commission": "30% recurring", "category": "course online education", "url": "teachable.com/affiliates", "cookie_days": 90},
    {"name": "Thinkific", "commission": "30% recurring", "category": "course online education", "url": "thinkific.com/affiliates", "cookie_days": 90},
    {"name": "Gumroad", "commission": "gift — no formal program", "category": "digital products ebook", "url": "gumroad.com", "cookie_days": 0},
    {"name": "Lemon Squeezy", "commission": "partner program", "category": "saas digital products subscription", "url": "lemonsqueezy.com", "cookie_days": 30},
    {"name": "Podia", "commission": "30% recurring", "category": "digital products course membership", "url": "podia.com/affiliates", "cookie_days": 30},
    # Hosting / Infrastructure
    {"name": "Cloudways", "commission": "$30–$125 per sale", "category": "hosting server cloud", "url": "cloudways.com/affiliates", "cookie_days": 90},
    {"name": "Kinsta", "commission": "$50–$500 + 10% recurring", "category": "hosting wordpress", "url": "kinsta.com/affiliates", "cookie_days": 60},
    {"name": "Digital Ocean", "commission": "$25 credit per referral", "category": "cloud hosting vps server", "url": "digitalocean.com/referral", "cookie_days": 30},
    {"name": "Vultr", "commission": "$35 credit per referral", "category": "cloud hosting vps", "url": "vultr.com/affiliates", "cookie_days": 30},
    # Finance / Investment
    {"name": "Coinbase", "commission": "$10 per referral", "category": "crypto bitcoin finance investment", "url": "coinbase.com/affiliates", "cookie_days": 30},
    {"name": "Robinhood", "commission": "free stock per referral", "category": "stocks investing finance", "url": "robinhood.com/affiliates", "cookie_days": 30},
    {"name": "Acorns", "commission": "$5 per referral", "category": "investing finance savings", "url": "acorns.com/affiliates", "cookie_days": 30},
    {"name": "Fundrise", "commission": "$50–$100 per referral", "category": "real estate investing passive income", "url": "fundrise.com/affiliates", "cookie_days": 30},
    # AI / Automation
    {"name": "Jasper AI", "commission": "30% recurring", "category": "ai writing content generation automation", "url": "jasper.ai/affiliates", "cookie_days": 45},
    {"name": "Copy.ai", "commission": "45% for first year", "category": "ai writing content copywriting", "url": "copy.ai/affiliates", "cookie_days": 60},
    {"name": "Descript", "commission": "15% recurring", "category": "video audio podcast editing ai", "url": "descript.com/affiliates", "cookie_days": 30},
    {"name": "Synthesia", "commission": "20% recurring", "category": "video ai avatar content creation", "url": "synthesia.io/affiliates", "cookie_days": 30},
    # General / Amazon
    {"name": "Amazon Associates", "commission": "1–10% by category", "category": "any product physical digital review", "url": "affiliate-program.amazon.com", "cookie_days": 24},
    # Health / Fitness
    {"name": "Noom", "commission": "up to $20 per sale", "category": "health fitness weight loss wellness", "url": "noom.com/affiliates", "cookie_days": 30},
    {"name": "Thrive Market", "commission": "$25–$40 per member", "category": "health organic food wellness", "url": "thrivemarket.com/affiliates", "cookie_days": 14},
    # Education / Career
    {"name": "Skillshare", "commission": "$7 per trial start", "category": "education learning skills online course", "url": "skillshare.com/affiliates", "cookie_days": 30},
    {"name": "Coursera", "commission": "up to 45%", "category": "education certificate degree online course", "url": "coursera.org/affiliates", "cookie_days": 30},
    {"name": "Udemy", "commission": "10–15%", "category": "education skills course learning", "url": "udemy.com/affiliates", "cookie_days": 7},
    # VPN / Security
    {"name": "NordVPN", "commission": "40% + 30% recurring", "category": "vpn security privacy", "url": "nordvpn.com/affiliates", "cookie_days": 30},
    {"name": "ExpressVPN", "commission": "$13–$36 per sale", "category": "vpn security privacy", "url": "expressvpn.com/affiliates", "cookie_days": 90},
    # Freelance / Business
    {"name": "Fiverr", "commission": "$15–$150 CPA", "category": "freelance marketplace services", "url": "fiverr.com/affiliates", "cookie_days": 30},
    {"name": "Toptal", "commission": "$1,000 per hire", "category": "freelance developer hiring talent", "url": "toptal.com/affiliates", "cookie_days": 30},
]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _keyword_overlap(text: str, keywords: List[str]) -> int:
    low = text.lower()
    return sum(1 for kw in keywords if kw in low)


def _score_program(program: Dict[str, Any], niche_keywords: List[str]) -> float:
    overlap = _keyword_overlap(program["category"], niche_keywords)
    if overlap == 0:
        return 0.0
    # Parse rough commission value
    comm_str = program["commission"].lower()
    comm_value = 0.0
    pct_match = re.search(r"(\d+(?:\.\d+)?)%", comm_str)
    dollar_match = re.search(r"\$(\d+)", comm_str)
    if pct_match:
        comm_value = float(pct_match.group(1))
    elif dollar_match:
        # Normalize dollar amounts: $100 ≈ 30% equivalent in scoring
        comm_value = min(float(dollar_match.group(1)) / 3.0, 100.0)
    recurring_bonus = 20.0 if "recurring" in comm_str else 0.0
    cookie_bonus = min(program.get("cookie_days", 0) / 90.0 * 10.0, 10.0)
    return (overlap * 20.0) + comm_value + recurring_bonus + cookie_bonus


# ---------------------------------------------------------------------------
# Web discovery (DuckDuckGo — no auth)
# ---------------------------------------------------------------------------


def _discover_via_ddg(niche: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search DuckDuckGo for affiliate programs in a niche."""
    results: List[Dict[str, Any]] = []
    try:
        headers = {"User-Agent": "openjarvis-affiliate-finder/1.0"}
        query = f"{niche} affiliate program high commission"
        resp = httpx.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
        )
        text = resp.text
        # Extract titles and snippets from DDG HTML result blocks
        title_pattern = re.compile(r'class="result__a"[^>]*>([^<]+)<')
        snippet_pattern = re.compile(r'class="result__snippet"[^>]*>([^<]{20,200})<')
        titles = title_pattern.findall(text)[:limit]
        snippets = snippet_pattern.findall(text)[:limit]
        for i, title in enumerate(titles):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append({
                "name": title.strip(),
                "commission": "see website",
                "category": niche.lower(),
                "url": "",
                "cookie_days": 30,
                "source": "web_search",
                "snippet": snippet.strip(),
            })
    except Exception:
        pass
    return results


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


def find_affiliate_programs(
    niche: str,
    *,
    top_k: int = 8,
    include_web_discovery: bool = True,
) -> List[Dict[str, Any]]:
    """Return ranked affiliate programs for *niche*."""
    niche_keywords = [w.lower() for w in re.split(r"[\s,/]+", niche) if len(w) > 2]

    # Score curated programs
    scored: List[Dict[str, Any]] = []
    for prog in _NETWORKS:
        score = _score_program(prog, niche_keywords)
        if score > 0:
            scored.append({**prog, "relevance_score": round(score, 1), "source": "curated"})

    # Sort by relevance
    scored.sort(key=lambda p: p["relevance_score"], reverse=True)
    curated_top = scored[:top_k]

    # Supplement with web discovery if not enough curated results
    web_results: List[Dict[str, Any]] = []
    if include_web_discovery and len(curated_top) < 4:
        web_results = _discover_via_ddg(niche, limit=top_k - len(curated_top))
        for r in web_results:
            r["relevance_score"] = 10.0

    return curated_top + web_results


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@ToolRegistry.register("affiliate_finder")
class AffinderTool(BaseTool):
    """Find affiliate programs for any niche, ranked by commission and relevance."""

    tool_id = "affiliate_finder"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="affiliate_finder",
            description=(
                "Find high-commission affiliate programs for a given niche or topic. "
                "Returns program names, commission rates, cookie windows, and sign-up URLs. "
                "Checks 35+ curated programs (SaaS, finance, AI, education, hosting) and "
                "supplements with live web discovery if needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "niche": {
                        "type": "string",
                        "description": "The niche or topic to find affiliate programs for (e.g. 'email marketing automation').",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of programs to return.",
                        "default": 8,
                    },
                },
                "required": ["niche"],
            },
            category="research",
            timeout_seconds=20.0,
        )

    def execute(self, *, niche: str, top_k: int = 8, **_: Any) -> ToolResult:
        if not niche.strip():
            return ToolResult(
                tool_name="affiliate_finder",
                content="Error: niche parameter is required.",
                success=False,
            )
        try:
            programs = find_affiliate_programs(niche, top_k=top_k)
            if not programs:
                return ToolResult(
                    tool_name="affiliate_finder",
                    content=f"No affiliate programs found for '{niche}'. Try a broader niche keyword.",
                    success=True,
                )
            lines = [f"## Affiliate Programs for: {niche}\n"]
            for i, p in enumerate(programs, 1):
                lines.append(f"### {i}. {p['name']}")
                lines.append(f"- **Commission:** {p['commission']}")
                lines.append(f"- **Cookie window:** {p.get('cookie_days', '?')} days")
                if p.get("url"):
                    lines.append(f"- **Sign up:** {p['url']}")
                if p.get("snippet"):
                    lines.append(f"- *{p['snippet'][:120]}*")
                lines.append(f"- Relevance score: {p.get('relevance_score', 0):.0f}")
                lines.append("")
            return ToolResult(
                tool_name="affiliate_finder",
                content="\n".join(lines),
                success=True,
                metadata={"programs": programs, "niche": niche},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="affiliate_finder",
                content=f"Affiliate finder failed: {exc}",
                success=False,
            )
