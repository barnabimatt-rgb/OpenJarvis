"""SEO keyword research tool — find low-competition, high-value keywords.

Uses free, public sources only — no paid APIs:
  - Google Autocomplete / Suggest API (json format, no key needed)
  - DuckDuckGo related searches (HTML scrape)
  - "People Also Ask" patterns via Google search snippet scraping
  - Alphabet soup expansion (seed + every letter a–z)

Output: ranked keyword suggestions with estimated difficulty signals.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class KeywordResult:
    keyword: str
    source: str
    estimated_difficulty: str  # "low" | "medium" | "high"
    content_type: str           # "informational" | "commercial" | "transactional"
    cpc_signal: str = ""        # Cheap/moderate/expensive — inferred from intent words
    serp_competition: int = 0   # 0–100, from DDG result density


# ---------------------------------------------------------------------------
# Intent and difficulty signals
# ---------------------------------------------------------------------------

_COMMERCIAL_SIGNALS = [
    "best", "top", "review", "vs", "versus", "comparison", "alternative",
    "cheap", "affordable", "price", "cost", "buy", "discount",
]
_TRANSACTIONAL_SIGNALS = [
    "buy", "purchase", "order", "download", "free trial", "sign up",
    "get started", "coupon", "promo",
]
_INFORMATIONAL_SIGNALS = [
    "how to", "what is", "why", "guide", "tutorial", "learn", "explain",
    "example", "tips", "ideas",
]
_HIGH_CPC_WORDS = [
    "insurance", "loan", "mortgage", "attorney", "lawyer", "credit", "hosting",
    "software", "saas", "crm", "erp", "cloud",
]
_LONG_TAIL_BONUS_WORDS = 4  # Keywords >= 4 words are typically lower competition


def _classify_intent(keyword: str) -> str:
    low = keyword.lower()
    for sig in _TRANSACTIONAL_SIGNALS:
        if sig in low:
            return "transactional"
    for sig in _COMMERCIAL_SIGNALS:
        if sig in low:
            return "commercial"
    return "informational"


def _estimate_cpc(keyword: str) -> str:
    low = keyword.lower()
    if any(hw in low for hw in _HIGH_CPC_WORDS):
        return "expensive ($5–$50 CPC)"
    if _classify_intent(keyword) in ("commercial", "transactional"):
        return "moderate ($1–$5 CPC)"
    return "cheap (<$1 CPC)"


def _difficulty(keyword: str, ddg_density: int) -> str:
    word_count = len(keyword.split())
    if word_count >= _LONG_TAIL_BONUS_WORDS and ddg_density < 8:
        return "low"
    elif ddg_density < 12:
        return "medium"
    return "high"


# ---------------------------------------------------------------------------
# Source: Google Autocomplete
# ---------------------------------------------------------------------------


def _google_suggest(seed: str, lang: str = "en") -> List[str]:
    """Return Google autocomplete suggestions for *seed*."""
    try:
        resp = httpx.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "firefox", "q": seed, "hl": lang},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8.0,
        )
        data = resp.json()
        suggestions = data[1] if len(data) > 1 else []
        return [s for s in suggestions if isinstance(s, str)]
    except Exception:
        return []


def _alphabet_soup(seed: str) -> List[str]:
    """Expand seed with every letter to uncover autocomplete long-tails."""
    results: List[str] = []
    for ch in string.ascii_lowercase:
        expanded = _google_suggest(f"{seed} {ch}")
        results.extend(expanded[:3])
    return list(dict.fromkeys(results))  # deduplicate, preserve order


def _question_suggest(seed: str) -> List[str]:
    """Prepend question words to find informational long-tails."""
    question_words = ["how to", "what is", "why", "when to", "can you", "is it"]
    results: List[str] = []
    for qw in question_words:
        results.extend(_google_suggest(f"{qw} {seed}")[:3])
    return results


# ---------------------------------------------------------------------------
# Source: DuckDuckGo related searches
# ---------------------------------------------------------------------------


def _ddg_related(seed: str) -> List[str]:
    try:
        headers = {"User-Agent": "openjarvis-seo/1.0"}
        resp = httpx.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(seed)}",
            headers=headers,
            timeout=10.0,
            follow_redirects=True,
        )
        text = resp.text
        # Extract "Searches related to" style links
        pattern = re.compile(r'class="result__a"[^>]*>([^<]{5,80})<')
        return [m.strip() for m in pattern.findall(text)[:10]]
    except Exception:
        return []


def _ddg_result_density(keyword: str) -> int:
    """Count result blocks in DDG HTML as a competition proxy."""
    try:
        headers = {"User-Agent": "openjarvis-seo/1.0"}
        resp = httpx.get(
            f"https://html.duckduckgo.com/html/?q={quote_plus(keyword)}",
            headers=headers,
            timeout=8.0,
            follow_redirects=True,
        )
        return resp.text.count('class="result__body"')
    except Exception:
        return 10  # Default to medium if can't check


# ---------------------------------------------------------------------------
# Main research function
# ---------------------------------------------------------------------------


def research_keywords(
    seed: str,
    *,
    top_k: int = 20,
    difficulty_filter: Optional[str] = None,
    intent_filter: Optional[str] = None,
    use_alphabet_soup: bool = False,
) -> List[KeywordResult]:
    """Gather and score keywords for *seed*.

    Parameters
    ----------
    seed:
        The root keyword or phrase to expand.
    top_k:
        Maximum results to return.
    difficulty_filter:
        If set, only return keywords with this difficulty ("low"/"medium"/"high").
    intent_filter:
        If set, only return keywords matching this intent type.
    use_alphabet_soup:
        Set True to run alphabet soup expansion (26× slower but much richer).
    """
    raw: List[str] = []

    # Google suggest — seed and question variants
    raw.extend(_google_suggest(seed))
    raw.extend(_question_suggest(seed))

    # DuckDuckGo related
    raw.extend(_ddg_related(seed))

    # Optional deep expansion
    if use_alphabet_soup:
        raw.extend(_alphabet_soup(seed))

    # Deduplicate
    seen: set = set()
    unique: List[str] = []
    for kw in raw:
        norm = kw.lower().strip()
        if norm and norm not in seen and norm != seed.lower():
            seen.add(norm)
            unique.append(kw.strip())

    results: List[KeywordResult] = []
    for kw in unique[:top_k * 2]:  # Over-fetch to allow filtering
        density = _ddg_result_density(kw)
        intent = _classify_intent(kw)
        diff = _difficulty(kw, density)

        if difficulty_filter and diff != difficulty_filter:
            continue
        if intent_filter and intent != intent_filter:
            continue

        results.append(KeywordResult(
            keyword=kw,
            source="google_suggest" if kw in _google_suggest(seed) else "expanded",
            estimated_difficulty=diff,
            content_type=intent,
            cpc_signal=_estimate_cpc(kw),
            serp_competition=density,
        ))

        if len(results) >= top_k:
            break

    # Sort: low-difficulty first, then by word count (longer = more specific)
    order = {"low": 0, "medium": 1, "high": 2}
    results.sort(key=lambda r: (order[r.estimated_difficulty], -len(r.keyword.split())))
    return results[:top_k]


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@ToolRegistry.register("seo_keywords")
class SeoKeywordsTool(BaseTool):
    """Find low-competition SEO keywords for content and blog posts."""

    tool_id = "seo_keywords"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="seo_keywords",
            description=(
                "Research SEO keywords for a topic using Google Autocomplete and "
                "DuckDuckGo. Returns keyword suggestions with estimated competition "
                "difficulty (low/medium/high), search intent classification "
                "(informational/commercial/transactional), and CPC signal. "
                "Best used before writing blog posts, newsletter subjects, or YouTube titles."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "seed": {
                        "type": "string",
                        "description": "Root keyword or phrase to expand (e.g. 'passive income ideas').",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of keywords to return.",
                        "default": 20,
                    },
                    "difficulty_filter": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Only return keywords of this difficulty level.",
                    },
                    "intent_filter": {
                        "type": "string",
                        "enum": ["informational", "commercial", "transactional"],
                        "description": "Only return keywords of this search intent.",
                    },
                    "use_alphabet_soup": {
                        "type": "boolean",
                        "description": "Run a–z expansion for deeper long-tail discovery (slower).",
                        "default": False,
                    },
                },
                "required": ["seed"],
            },
            category="research",
            timeout_seconds=90.0,
        )

    def execute(
        self,
        *,
        seed: str,
        top_k: int = 20,
        difficulty_filter: Optional[str] = None,
        intent_filter: Optional[str] = None,
        use_alphabet_soup: bool = False,
        **_: Any,
    ) -> ToolResult:
        if not seed.strip():
            return ToolResult(
                tool_name="seo_keywords",
                content="Error: seed parameter is required.",
                success=False,
            )
        try:
            keywords = research_keywords(
                seed,
                top_k=top_k,
                difficulty_filter=difficulty_filter,
                intent_filter=intent_filter,
                use_alphabet_soup=use_alphabet_soup,
            )
            if not keywords:
                return ToolResult(
                    tool_name="seo_keywords",
                    content=f"No keywords found for '{seed}'. Try a broader seed term.",
                    success=True,
                )
            lines = [f"## SEO Keywords for: {seed}\n"]
            lines.append(f"Found {len(keywords)} keyword suggestions.\n")
            diff_icons = {"low": "🟢", "medium": "🟡", "high": "🔴"}
            intent_icons = {"informational": "ℹ️", "commercial": "💰", "transactional": "🛒"}
            for i, k in enumerate(keywords, 1):
                diff_icon = diff_icons.get(k.estimated_difficulty, "")
                intent_icon = intent_icons.get(k.content_type, "")
                lines.append(
                    f"{i}. **{k.keyword}**  "
                    f"{diff_icon} {k.estimated_difficulty} difficulty · "
                    f"{intent_icon} {k.content_type} · {k.cpc_signal}"
                )
            return ToolResult(
                tool_name="seo_keywords",
                content="\n".join(lines),
                success=True,
                metadata={
                    "seed": seed,
                    "keywords": [
                        {
                            "keyword": k.keyword,
                            "difficulty": k.estimated_difficulty,
                            "intent": k.content_type,
                            "cpc_signal": k.cpc_signal,
                        }
                        for k in keywords
                    ],
                },
            )
        except Exception as exc:
            return ToolResult(
                tool_name="seo_keywords",
                content=f"SEO keyword research failed: {exc}",
                success=False,
            )
