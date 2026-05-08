"""CAPTCHA solving tool — 2Captcha API integration with manual fallback.

Supports reCAPTCHA v2, reCAPTCHA v3, and hCaptcha.
Auth: TWOCAPTCHA_API_KEY in ~/.openjarvis/cloud-keys.env (~$3 per 1,000 solves).

When no API key is configured, takes a screenshot, saves it to Obsidian,
and returns a clear message so the user can solve it in the visible browser.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_2CAPTCHA_BASE = "https://2captcha.com"
_ANTICAPTCHA_BASE = "https://api.anti-captcha.com"


def _get_api_key() -> str:
    return os.environ.get("TWOCAPTCHA_API_KEY", "")


# ---------------------------------------------------------------------------
# 2Captcha helpers
# ---------------------------------------------------------------------------


def _submit_recaptcha_v2(api_key: str, site_key: str, page_url: str) -> str:
    """Submit a reCAPTCHA v2 solve request. Returns task ID."""
    resp = httpx.post(
        f"{_2CAPTCHA_BASE}/in.php",
        data={
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 1:
        raise RuntimeError(f"2Captcha submit error: {data.get('request')}")
    return str(data["request"])


def _submit_recaptcha_v3(api_key: str, site_key: str, page_url: str, action: str = "submit") -> str:
    resp = httpx.post(
        f"{_2CAPTCHA_BASE}/in.php",
        data={
            "key": api_key,
            "method": "userrecaptcha",
            "version": "v3",
            "googlekey": site_key,
            "pageurl": page_url,
            "action": action,
            "min_score": 0.7,
            "json": 1,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 1:
        raise RuntimeError(f"2Captcha v3 submit error: {data.get('request')}")
    return str(data["request"])


def _submit_hcaptcha(api_key: str, site_key: str, page_url: str) -> str:
    resp = httpx.post(
        f"{_2CAPTCHA_BASE}/in.php",
        data={
            "key": api_key,
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
            "json": 1,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != 1:
        raise RuntimeError(f"2Captcha hCaptcha submit error: {data.get('request')}")
    return str(data["request"])


def _poll_result(api_key: str, task_id: str, *, max_wait: int = 120) -> str:
    """Poll for CAPTCHA solution. Returns token string."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        time.sleep(5)
        resp = httpx.get(
            f"{_2CAPTCHA_BASE}/res.php",
            params={"key": api_key, "action": "get", "id": task_id, "json": 1},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 1:
            return str(data["request"])
        if data.get("request") not in ("CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"):
            raise RuntimeError(f"2Captcha poll error: {data.get('request')}")
    raise TimeoutError(f"CAPTCHA not solved within {max_wait}s")


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@ToolRegistry.register("captcha_solve")
class CaptchaSolveTool(BaseTool):
    """Solve reCAPTCHA or hCaptcha using 2Captcha API."""

    tool_id = "captcha_solve"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="captcha_solve",
            description=(
                "Solve a CAPTCHA (reCAPTCHA v2/v3 or hCaptcha) using the 2Captcha service. "
                "Requires TWOCAPTCHA_API_KEY in cloud-keys.env (~$3/1000 solves at 2captcha.com). "
                "Falls back to a manual solve prompt if no key is configured. "
                "Returns the solved token to inject into the page."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "page_url": {
                        "type": "string",
                        "description": "URL of the page with the CAPTCHA.",
                    },
                    "site_key": {
                        "type": "string",
                        "description": "The CAPTCHA site key (data-sitekey attribute on the CAPTCHA element).",
                    },
                    "captcha_type": {
                        "type": "string",
                        "enum": ["recaptcha_v2", "recaptcha_v3", "hcaptcha"],
                        "description": "Type of CAPTCHA. Default: recaptcha_v2.",
                    },
                    "action": {
                        "type": "string",
                        "description": "reCAPTCHA v3 action name (e.g. 'submit', 'login'). Default: 'submit'.",
                    },
                },
                "required": ["page_url", "site_key"],
            },
            category="browser",
            timeout_seconds=150.0,
        )

    def execute(
        self,
        *,
        page_url: str,
        site_key: str,
        captcha_type: str = "recaptcha_v2",
        action: str = "submit",
        **_: Any,
    ) -> ToolResult:
        api_key = _get_api_key()

        if not api_key:
            # No solver key — instruct manual resolution
            try:
                from openjarvis.tools.browser import _active_session
                import base64
                screenshot_bytes = _active_session.page.screenshot()
                b64 = base64.b64encode(screenshot_bytes).decode()
            except Exception:
                b64 = ""

            msg = (
                "⚠️ CAPTCHA detected but TWOCAPTCHA_API_KEY is not configured.\n\n"
                "Options:\n"
                "1. Get a key at 2captcha.com (~$3/1000 solves), add TWOCAPTCHA_API_KEY "
                "to ~/.openjarvis/cloud-keys.env, then retry.\n"
                "2. Solve the CAPTCHA manually in the visible browser window, "
                "then continue the signup flow.\n\n"
                f"Page: {page_url}  |  Site key: {site_key}"
            )
            return ToolResult(
                tool_name="captcha_solve",
                content=msg,
                success=False,
                metadata={"screenshot_base64": b64, "needs_manual": True},
            )

        try:
            if captcha_type == "recaptcha_v3":
                task_id = _submit_recaptcha_v3(api_key, site_key, page_url, action)
            elif captcha_type == "hcaptcha":
                task_id = _submit_hcaptcha(api_key, site_key, page_url)
            else:
                task_id = _submit_recaptcha_v2(api_key, site_key, page_url)

            token = _poll_result(api_key, task_id)

            return ToolResult(
                tool_name="captcha_solve",
                content=(
                    f"✅ CAPTCHA solved.\n\n"
                    f"Token (inject into g-recaptcha-response or h-captcha-response field):\n"
                    f"{token[:80]}..."
                ),
                success=True,
                metadata={"token": token, "task_id": task_id, "captcha_type": captcha_type},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="captcha_solve",
                content=f"CAPTCHA solve failed: {exc}",
                success=False,
            )
