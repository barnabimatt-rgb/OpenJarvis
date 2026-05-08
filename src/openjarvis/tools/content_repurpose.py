"""Content repurposing tool — transform one piece of content into multiple platform formats.

Takes a source content piece (blog post, newsletter, raw notes) and generates:
  - Newsletter issue (Beehiiv / ConvertKit format)
  - Blog post (Ghost / Dev.to Markdown)
  - Twitter/X thread (10-tweet chain)
  - LinkedIn post (professional tone, 1,300 char limit)
  - YouTube video script (hook + talking points + CTA)
  - Reddit post (value-first, community-appropriate tone)
  - Dev.to article (technical framing, code-friendly)
  - Short-form hook (Instagram caption / TikTok opener)

This tool is a pure prompt-structuring utility — it does NOT call any LLM itself.
It reformats the inputs into a structured prompt that the orchestrating agent sends
to its own LLM, then captures the multi-format output.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# ---------------------------------------------------------------------------
# Platform format specs
# ---------------------------------------------------------------------------


@dataclass
class PlatformFormat:
    platform: str
    max_chars: Optional[int]
    tone: str
    structure_hint: str
    cta_hint: str


_FORMATS: List[PlatformFormat] = [
    PlatformFormat(
        platform="newsletter",
        max_chars=None,
        tone="conversational, personal, value-packed",
        structure_hint=(
            "Subject line → Preview text (1 sentence) → "
            "Hook paragraph (60 words) → "
            "3 insight sections (80 words each) → "
            "Single clear CTA → P.S. line"
        ),
        cta_hint="Subscribe / share with one friend",
    ),
    PlatformFormat(
        platform="blog_post",
        max_chars=None,
        tone="authoritative but accessible, SEO-optimised",
        structure_hint=(
            "SEO title (50–60 chars) → "
            "Meta description (150 chars) → "
            "Intro with hook + thesis (100 words) → "
            "5 H2 sections (150 words each) → "
            "Conclusion + CTA (80 words)"
        ),
        cta_hint="Subscribe to newsletter for more",
    ),
    PlatformFormat(
        platform="twitter_thread",
        max_chars=240,
        tone="punchy, curious, opinionated — each tweet standalone",
        structure_hint=(
            "Tweet 1: Bold hook or surprising stat → "
            "Tweet 2: Context / expand the hook → "
            "Tweets 3–8: One insight per tweet, numbered (3/ 4/ ...) → "
            "Tweet 9: Monetization / tool recommendation → "
            "Tweet 10: CTA — follow + subscribe link"
        ),
        cta_hint="Follow + subscribe to newsletter",
    ),
    PlatformFormat(
        platform="linkedin_post",
        max_chars=1300,
        tone="professional but human — first person, no jargon",
        structure_hint=(
            "Hook line (no emojis in first line) → "
            "1–2 short paragraphs of insight → "
            "3-bullet takeaway → "
            "Question to drive comments → "
            "Optional: hashtags (3 max)"
        ),
        cta_hint="Invite comment / connection",
    ),
    PlatformFormat(
        platform="youtube_script",
        max_chars=None,
        tone="energetic, direct to camera, clear transitions",
        structure_hint=(
            "Hook (0–15s): Bold claim or question → "
            "Intro (15–45s): Who this is for + what they'll learn → "
            "Section 1–4 (45s–4min each): talking points with examples → "
            "Mid-roll CTA (if >8 min): like + subscribe → "
            "Outro (60s): Summary + subscribe + next video"
        ),
        cta_hint="Like, subscribe, comment your question",
    ),
    PlatformFormat(
        platform="reddit_post",
        max_chars=None,
        tone="community-first, no self-promotion, add genuine value",
        structure_hint=(
            "Title: question or insight (no clickbait) → "
            "Body: context paragraph → "
            "Main insight / story → "
            "What you learned / results → "
            "Open-ended question to start discussion"
        ),
        cta_hint="Ask a question, invite discussion — NO direct links or sales",
    ),
    PlatformFormat(
        platform="devto_article",
        max_chars=None,
        tone="technical, practical, beginner-friendly explanations",
        structure_hint=(
            "Title: 'How to X' or 'N things about Y' → "
            "Tags: 4 relevant tags → "
            "Intro: problem + what reader will learn → "
            "Step-by-step or concept sections with code blocks → "
            "Takeaways section → "
            "CTA: follow + newsletter link"
        ),
        cta_hint="Follow on Dev.to + subscribe to newsletter",
    ),
    PlatformFormat(
        platform="short_form_hook",
        max_chars=150,
        tone="scroll-stopping, curiosity-driven, ultra-concise",
        structure_hint=(
            "Line 1: The bold claim or surprising fact → "
            "Line 2: Why most people get it wrong → "
            "Line 3: The simple fix / key insight"
        ),
        cta_hint="Link in bio",
    ),
]

_FORMAT_MAP: Dict[str, PlatformFormat] = {f.platform: f for f in _FORMATS}
_ALL_PLATFORMS = [f.platform for f in _FORMATS]


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


def build_repurpose_prompt(
    source_content: str,
    *,
    target_platforms: Optional[List[str]] = None,
    niche: str = "",
    target_audience: str = "",
    cta_url: str = "",
    author_voice: str = "",
) -> str:
    """Build a structured repurposing prompt for the agent's LLM."""
    platforms = target_platforms or _ALL_PLATFORMS
    invalid = [p for p in platforms if p not in _FORMAT_MAP]
    if invalid:
        platforms = [p for p in platforms if p in _FORMAT_MAP]

    audience_line = f"Target audience: {target_audience}" if target_audience else ""
    niche_line = f"Content niche: {niche}" if niche else ""
    cta_line = f"Primary CTA URL: {cta_url}" if cta_url else ""
    voice_line = f"Author voice/tone notes: {author_voice}" if author_voice else ""
    context_block = "\n".join(filter(None, [audience_line, niche_line, cta_line, voice_line]))

    format_instructions = []
    for pname in platforms:
        fmt = _FORMAT_MAP[pname]
        char_note = f" (max {fmt.max_chars} chars per unit)" if fmt.max_chars else ""
        format_instructions.append(
            f"## {pname.upper().replace('_', ' ')}{char_note}\n"
            f"Tone: {fmt.tone}\n"
            f"Structure: {fmt.structure_hint}\n"
            f"CTA hint: {fmt.cta_hint}\n"
        )

    prompt = textwrap.dedent(f"""
        You are an expert content repurposer. Take the SOURCE CONTENT below and rewrite it
        into each of the requested platform formats. Keep the core insights intact but adapt
        tone, length, and structure to match each platform's audience and conventions.

        Each section MUST be clearly delimited with the header shown (e.g. ## NEWSLETTER).
        Do not skip any requested format. Write complete, publish-ready copy for each.

        {"--- CONTEXT ---" if context_block else ""}
        {context_block}

        --- SOURCE CONTENT ---
        {source_content.strip()}

        --- OUTPUT FORMATS REQUIRED ---
        {"".join(format_instructions)}
        Write each format in full below, delimited by its header.
    """).strip()

    return prompt


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@ToolRegistry.register("content_repurpose")
class ContentRepurposeTool(BaseTool):
    """Repurpose one content piece into multiple platform-optimised formats."""

    tool_id = "content_repurpose"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="content_repurpose",
            description=(
                "Transform a blog post, newsletter, or notes into multiple ready-to-publish "
                "formats: newsletter, blog post, Twitter thread (10 tweets), LinkedIn post, "
                "YouTube script, Reddit post, Dev.to article, and short-form hook. "
                "Returns a structured prompt to pass to the LLM, plus platform metadata."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "source_content": {
                        "type": "string",
                        "description": "The source content to repurpose (blog post, newsletter draft, raw notes, etc.).",
                    },
                    "target_platforms": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": _ALL_PLATFORMS,
                        },
                        "description": (
                            "Platforms to generate content for. "
                            f"Defaults to all: {', '.join(_ALL_PLATFORMS)}."
                        ),
                    },
                    "niche": {
                        "type": "string",
                        "description": "Content niche or topic (helps calibrate tone and examples).",
                    },
                    "target_audience": {
                        "type": "string",
                        "description": "Who the content is for (e.g. 'indie hackers', 'solopreneurs').",
                    },
                    "cta_url": {
                        "type": "string",
                        "description": "Primary CTA URL to weave into each format (newsletter subscribe link, product URL, etc.).",
                    },
                    "author_voice": {
                        "type": "string",
                        "description": "Notes on desired voice (e.g. 'direct, no fluff, first person, occasional dry humour').",
                    },
                },
                "required": ["source_content"],
            },
            category="publishing",
            timeout_seconds=10.0,
        )

    def execute(
        self,
        *,
        source_content: str,
        target_platforms: Optional[List[str]] = None,
        niche: str = "",
        target_audience: str = "",
        cta_url: str = "",
        author_voice: str = "",
        **_: Any,
    ) -> ToolResult:
        if not source_content.strip():
            return ToolResult(
                tool_name="content_repurpose",
                content="Error: source_content is required.",
                success=False,
            )

        platforms = target_platforms or _ALL_PLATFORMS
        valid_platforms = [p for p in platforms if p in _FORMAT_MAP]
        invalid_platforms = [p for p in platforms if p not in _FORMAT_MAP]

        prompt = build_repurpose_prompt(
            source_content,
            target_platforms=valid_platforms,
            niche=niche,
            target_audience=target_audience,
            cta_url=cta_url,
            author_voice=author_voice,
        )

        notes = []
        if invalid_platforms:
            notes.append(f"Skipped unknown platforms: {', '.join(invalid_platforms)}")

        summary = (
            f"Repurposing prompt built for {len(valid_platforms)} platforms: "
            f"{', '.join(valid_platforms)}.\n\n"
            "Pass the prompt below to your LLM to generate all formats:\n\n"
            "---\n\n"
            f"{prompt}"
        )
        if notes:
            summary += f"\n\n**Notes:** {' | '.join(notes)}"

        return ToolResult(
            tool_name="content_repurpose",
            content=summary,
            success=True,
            metadata={
                "platforms": valid_platforms,
                "prompt_length": len(prompt),
                "niche": niche,
                "cta_url": cta_url,
            },
        )
