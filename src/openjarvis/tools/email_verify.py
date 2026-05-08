"""Email verification code extractor — poll Gmail for platform signup emails.

Uses the existing Gmail connector to watch for verification emails from a
given domain, then extracts either a 6-digit code or a verification link.

Falls back gracefully if Gmail is not configured — prompts user to supply
the code manually.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_CODE_PATTERN = re.compile(r"\b(\d{4,8})\b")
_LINK_PATTERN = re.compile(r"https?://[^\s\"'<>]{20,500}")


def _extract_code_or_link(body: str) -> Optional[str]:
    """Return the first verification code or link found in email body."""
    # Prefer numeric code (4-8 digits)
    for match in _CODE_PATTERN.finditer(body):
        candidate = match.group(1)
        # Filter out years and common non-code numbers
        if not re.match(r"^(19|20)\d{2}$", candidate):
            return candidate
    # Fall back to link
    for match in _LINK_PATTERN.finditer(body):
        link = match.group(0)
        # Only return links that look like verification URLs
        verify_words = ["verify", "confirm", "activate", "validate", "auth", "token", "click"]
        if any(w in link.lower() for w in verify_words):
            return link
    return None


def _get_gmail_messages(from_domain: str, subject_hint: str, since_ts: float) -> list:
    """Attempt to fetch new messages from Gmail containing a verification email."""
    try:
        from openjarvis.core.registry import ConnectorRegistry
        gmail_cls = ConnectorRegistry.get("gmail")
        connector = gmail_cls()
        if not connector.is_connected():
            return []
        # Use the sync() method to get recent documents
        docs = list(connector.sync(since=datetime.fromtimestamp(since_ts, tz=timezone.utc)))
        matches = []
        for doc in docs:
            content_lower = doc.content.lower()
            title_lower = doc.title.lower()
            if from_domain.lower() in content_lower or from_domain.lower() in title_lower:
                if subject_hint.lower() in title_lower or subject_hint.lower() in content_lower:
                    matches.append(doc)
        return matches
    except Exception:
        return []


@ToolRegistry.register("email_verify_code")
class EmailVerifyCodeTool(BaseTool):
    """Poll Gmail for a platform verification email and extract the code or link."""

    tool_id = "email_verify_code"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="email_verify_code",
            description=(
                "Wait for a verification email from a platform domain and extract "
                "the numeric code or verification link. Uses the Gmail connector "
                "(requires GMAIL OAuth). Falls back to manual prompt if Gmail is "
                "not configured. Use this after platform_signup reports email verification needed."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "from_domain": {
                        "type": "string",
                        "description": "Domain to watch for (e.g. 'beehiiv.com', 'dev.to').",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "How long to wait for the email. Default: 120 seconds.",
                        "default": 120,
                    },
                    "subject_hint": {
                        "type": "string",
                        "description": "Word to look for in the subject (e.g. 'verify', 'confirm'). Default: 'verify'.",
                        "default": "verify",
                    },
                },
                "required": ["from_domain"],
            },
            category="browser",
            timeout_seconds=150.0,
        )

    def execute(
        self,
        *,
        from_domain: str,
        timeout_seconds: int = 120,
        subject_hint: str = "verify",
        **_: Any,
    ) -> ToolResult:
        if not from_domain.strip():
            return ToolResult(
                tool_name="email_verify_code",
                content="from_domain is required.",
                success=False,
            )

        since_ts = time.time() - 30  # look back 30s to catch emails sent just before call
        deadline = time.time() + timeout_seconds
        poll_interval = 8

        while time.time() < deadline:
            docs = _get_gmail_messages(from_domain, subject_hint, since_ts)
            for doc in docs:
                code_or_link = _extract_code_or_link(doc.content)
                if code_or_link:
                    is_link = code_or_link.startswith("http")
                    kind = "verification link" if is_link else "verification code"
                    return ToolResult(
                        tool_name="email_verify_code",
                        content=(
                            f"✅ Found {kind} from {from_domain}:\n\n"
                            f"{code_or_link}\n\n"
                            f"Email subject: {doc.title}"
                        ),
                        success=True,
                        metadata={
                            "code_or_link": code_or_link,
                            "is_link": is_link,
                            "from_domain": from_domain,
                            "email_title": doc.title,
                        },
                    )
            time.sleep(poll_interval)

        # Timed out — prompt manual
        return ToolResult(
            tool_name="email_verify_code",
            content=(
                f"⏰ No verification email from {from_domain} found within {timeout_seconds}s.\n\n"
                "Possible reasons:\n"
                "- Gmail connector not configured (add GMAIL OAuth credentials)\n"
                "- Email went to spam — check your inbox manually\n"
                "- Platform used a different domain\n\n"
                "Check your email inbox manually and supply the code or link when ready."
            ),
            success=False,
            metadata={"timed_out": True, "from_domain": from_domain},
        )
