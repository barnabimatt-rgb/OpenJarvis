"""Platform signup orchestrator — automated account creation via browser.

Uses the existing Playwright browser tools (browser_navigate, browser_click,
browser_type, browser_extract) to walk through each platform's signup flow,
extract the resulting API key, and persist it to ~/.openjarvis/cloud-keys.env.

Design principles:
  - Always uses headed=True (visible browser) so the user can see progress
    and intervene if something unexpected happens
  - Pauses and asks for manual help when CAPTCHA is detected and no solver key
  - Never stores passwords in memory or logs — only the resulting API key
  - Works for creating ONE real account per platform (not mass account creation)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# ---------------------------------------------------------------------------
# Platform flow definitions
# ---------------------------------------------------------------------------


@dataclass
class SignupFlow:
    """Describes how to sign up for one platform and retrieve its API key."""
    name: str
    signup_url: str
    email_selector: str
    password_selector: str
    submit_selector: str
    env_var_name: str                        # key to write to cloud-keys.env
    name_selector: str = ""
    username_selector: str = ""
    api_key_url: str = ""                    # navigate here after signup to get key
    api_key_selector: str = ""               # CSS selector for the key text
    api_key_create_selector: str = ""        # click this to generate a new key
    verify_email_domain: str = ""            # domain to watch for verification email
    has_captcha: bool = False
    post_signup_wait_seconds: int = 3
    notes: str = ""


_PLATFORMS: Dict[str, SignupFlow] = {
    "devto": SignupFlow(
        name="Dev.to",
        signup_url="https://dev.to/enter?state=new-user",
        email_selector="input#user_email",
        password_selector="input#user_password",
        name_selector="input#user_name",
        submit_selector="button[type='submit']",
        api_key_url="https://dev.to/settings/extensions",
        api_key_create_selector="button#api-key-gen-btn",
        api_key_selector="p#api-key",
        env_var_name="DEVTO_API_KEY",
        verify_email_domain="dev.to",
        notes="Click 'Generate API Key' on the Extensions settings page.",
    ),
    "convertkit": SignupFlow(
        name="ConvertKit / Kit",
        signup_url="https://app.kit.com/users/signup",
        email_selector="input[name='user[email]']",
        password_selector="input[name='user[password]']",
        name_selector="input[name='user[first_name]']",
        submit_selector="button[type='submit']",
        api_key_url="https://app.kit.com/account_settings/advanced_settings",
        api_key_selector="input#settings_api_key",
        env_var_name="CONVERTKIT_API_KEY",
        verify_email_domain="kit.com",
    ),
    "beehiiv": SignupFlow(
        name="Beehiiv",
        signup_url="https://app.beehiiv.com/register",
        email_selector="input[name='email']",
        password_selector="input[name='password']",
        name_selector="input[name='full_name']",
        submit_selector="button[type='submit']",
        api_key_url="https://app.beehiiv.com/settings/integrations/api",
        api_key_create_selector="button[data-testid='generate-api-key']",
        api_key_selector="code[data-testid='api-key']",
        env_var_name="BEEHIIV_API_KEY",
        verify_email_domain="beehiiv.com",
        notes="Navigate to Settings → Integrations → API to generate a key.",
    ),
    "gumroad": SignupFlow(
        name="Gumroad",
        signup_url="https://app.gumroad.com/signup",
        email_selector="input[name='email']",
        password_selector="input[name='password']",
        submit_selector="button[type='submit']",
        api_key_url="https://app.gumroad.com/settings/advanced",
        api_key_create_selector="button.generate-access-token",
        api_key_selector="input#access_token",
        env_var_name="GUMROAD_ACCESS_TOKEN",
        verify_email_domain="gumroad.com",
    ),
    "lemon_squeezy": SignupFlow(
        name="Lemon Squeezy",
        signup_url="https://app.lemonsqueezy.com/register",
        email_selector="input[name='email']",
        password_selector="input[name='password']",
        name_selector="input[name='name']",
        submit_selector="button[type='submit']",
        api_key_url="https://app.lemonsqueezy.com/settings/api",
        api_key_create_selector="button[data-test='create-api-key']",
        api_key_selector="input[data-test='api-key-value']",
        env_var_name="LEMON_SQUEEZY_API_KEY",
        verify_email_domain="lemonsqueezy.com",
    ),
    "patreon": SignupFlow(
        name="Patreon",
        signup_url="https://www.patreon.com/signup",
        email_selector="input[name='email']",
        password_selector="input[name='password']",
        name_selector="input[name='full_name']",
        submit_selector="button[type='submit']",
        api_key_url="https://www.patreon.com/portal/registration/register-clients",
        api_key_selector="input[name='client_secret']",
        env_var_name="PATREON_ACCESS_TOKEN",
        verify_email_domain="patreon.com",
        has_captcha=True,
        notes="Patreon uses reCAPTCHA. May require manual solve.",
    ),
    "medium": SignupFlow(
        name="Medium",
        signup_url="https://medium.com/m/signin",
        email_selector="input[name='email']",
        password_selector="",  # Medium uses passwordless email link
        submit_selector="button[type='submit']",
        api_key_url="https://medium.com/me/settings/security",
        api_key_create_selector="button.integration-token",
        api_key_selector="input.integration-token-input",
        env_var_name="MEDIUM_INTEGRATION_TOKEN",
        verify_email_domain="medium.com",
        notes="Medium uses email magic link — check email after submitting.",
    ),
    "reddit": SignupFlow(
        name="Reddit",
        signup_url="https://www.reddit.com/register/",
        email_selector="input[name='email']",
        password_selector="input[name='password']",
        username_selector="input[name='username']",
        submit_selector="button[type='submit']",
        api_key_url="https://www.reddit.com/prefs/apps/",
        api_key_create_selector="button.create-app",
        api_key_selector="",  # must manually create a "script" type app
        env_var_name="REDDIT_CLIENT_ID",
        verify_email_domain="reddit.com",
        has_captcha=True,
        notes=(
            "After signup, go to reddit.com/prefs/apps → Create App (script type). "
            "The client_id is shown under the app name; secret is below."
        ),
    ),
    "twitter": SignupFlow(
        name="Twitter / X",
        signup_url="https://twitter.com/i/flow/signup",
        email_selector="input[autocomplete='email']",
        password_selector="input[type='password']",
        name_selector="input[autocomplete='name']",
        submit_selector="div[data-testid='LoginForm_Login_Button']",
        api_key_url="https://developer.twitter.com/en/portal/dashboard",
        api_key_selector="",
        env_var_name="TWITTER_API_KEY",
        verify_email_domain="twitter.com",
        has_captcha=True,
        notes=(
            "Twitter requires a developer account approval (developer.twitter.com). "
            "After signup, apply for developer access and create an app for API keys."
        ),
    ),
    "linkedin": SignupFlow(
        name="LinkedIn",
        signup_url="https://www.linkedin.com/signup",
        email_selector="input#email-address",
        password_selector="input#password",
        name_selector="input#first-name",
        submit_selector="button[data-id='sign-up-btn']",
        api_key_url="https://www.linkedin.com/developers/apps",
        api_key_create_selector="a.create-app-btn",
        api_key_selector="",
        env_var_name="LINKEDIN_ACCESS_TOKEN",
        verify_email_domain="linkedin.com",
        has_captcha=True,
        notes=(
            "LinkedIn requires creating an app at linkedin.com/developers and "
            "completing OAuth. The access token is obtained via OAuth 2.0 flow."
        ),
    ),
    "stripe": SignupFlow(
        name="Stripe",
        signup_url="https://dashboard.stripe.com/register",
        email_selector="input[name='email']",
        password_selector="input[name='password']",
        name_selector="input[name='full_name']",
        submit_selector="button[type='submit']",
        api_key_url="https://dashboard.stripe.com/apikeys",
        api_key_selector="",  # keys are revealed via button click, complex flow
        env_var_name="STRIPE_SECRET_KEY",
        verify_email_domain="stripe.com",
        notes=(
            "Stripe shows test keys immediately. Restricted read-only key recommended. "
            "Navigate to Developers → API keys → Create restricted key."
        ),
    ),
    "ghost": SignupFlow(
        name="Ghost",
        signup_url="https://account.ghost.org/signup/",
        email_selector="input[name='email']",
        password_selector="input[name='password']",
        name_selector="input[name='name']",
        submit_selector="button[type='submit']",
        api_key_url="",  # self-hosted — admin key is in Ghost Admin → Integrations
        api_key_selector="",
        env_var_name="GHOST_ADMIN_API_KEY",
        verify_email_domain="ghost.org",
        notes=(
            "Ghost Pro (ghost.org) or self-hosted. Admin API key is found at "
            "Ghost Admin → Settings → Integrations → Add Custom Integration."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Helper: detect CAPTCHA presence on page
# ---------------------------------------------------------------------------


def _has_captcha(page_text: str) -> bool:
    signals = ["recaptcha", "hcaptcha", "cf-turnstile", "captcha", "i'm not a robot"]
    lower = page_text.lower()
    return any(s in lower for s in signals)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@ToolRegistry.register("platform_signup")
class PlatformSignupTool(BaseTool):
    """Automate account creation for a passive income platform via visible browser."""

    tool_id = "platform_signup"
    is_local = False

    @property
    def spec(self) -> ToolSpec:
        platform_list = ", ".join(sorted(_PLATFORMS.keys()))
        return ToolSpec(
            name="platform_signup",
            description=(
                "Open a visible browser window and automate signing up for a passive "
                "income platform. Fills the signup form, handles email verification "
                "(via email_verify_code), extracts the resulting API key, and saves it "
                "to ~/.openjarvis/cloud-keys.env via credential_save. "
                f"Supported platforms: {platform_list}."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": f"Platform to sign up for. One of: {platform_list}.",
                        "enum": sorted(_PLATFORMS.keys()),
                    },
                    "email": {
                        "type": "string",
                        "description": "Email address to use for signup.",
                    },
                    "password": {
                        "type": "string",
                        "description": "Password to use. Should be unique and strong.",
                    },
                    "full_name": {
                        "type": "string",
                        "description": "Full name for the account.",
                    },
                    "username": {
                        "type": "string",
                        "description": "Username (required for Reddit, Twitter).",
                    },
                    "manual_captcha_token": {
                        "type": "string",
                        "description": "If the agent paused for a CAPTCHA, paste the solved token here to resume.",
                    },
                },
                "required": ["platform", "email", "password"],
            },
            category="browser",
            requires_confirmation=True,
            timeout_seconds=300.0,
        )

    def execute(
        self,
        *,
        platform: str,
        email: str,
        password: str,
        full_name: str = "",
        username: str = "",
        manual_captcha_token: str = "",
        **_: Any,
    ) -> ToolResult:
        if platform not in _PLATFORMS:
            available = ", ".join(sorted(_PLATFORMS.keys()))
            return ToolResult(
                tool_name="platform_signup",
                content=f"Unknown platform '{platform}'. Available: {available}",
                success=False,
            )

        flow = _PLATFORMS[platform]

        try:
            from openjarvis.tools.browser import _get_session
        except ImportError:
            return ToolResult(
                tool_name="platform_signup",
                content="Browser tools not available. Install with: uv sync --extra browser",
                success=False,
            )

        try:
            session = _get_session(headed=True)
            page = session.page

            # --- Step 1: Navigate to signup ---
            page.goto(flow.signup_url, wait_until="load")
            time.sleep(2)

            page_text = page.inner_text("body")

            # --- Step 2: CAPTCHA check before filling ---
            if _has_captcha(page_text) and not manual_captcha_token:
                return ToolResult(
                    tool_name="platform_signup",
                    content=(
                        f"⚠️ CAPTCHA detected on {flow.name} signup page.\n\n"
                        "Options:\n"
                        "1. Use captcha_solve tool with the site key from this page\n"
                        "2. Solve it manually in the visible browser window, "
                        "then call platform_signup again with manual_captcha_token=<token>\n\n"
                        f"Notes: {flow.notes}"
                    ),
                    success=False,
                    metadata={"captcha_detected": True, "platform": platform},
                )

            # --- Step 3: Fill form fields ---
            if flow.email_selector:
                try:
                    page.fill(flow.email_selector, email)
                except Exception:
                    pass

            if flow.name_selector and full_name:
                try:
                    page.fill(flow.name_selector, full_name)
                except Exception:
                    pass

            if flow.username_selector and username:
                try:
                    page.fill(flow.username_selector, username)
                except Exception:
                    pass

            if flow.password_selector and password:
                try:
                    page.fill(flow.password_selector, password)
                except Exception:
                    pass

            time.sleep(1)

            # --- Step 4: Submit ---
            try:
                page.click(flow.submit_selector)
            except Exception as exc:
                return ToolResult(
                    tool_name="platform_signup",
                    content=(
                        f"Could not click submit on {flow.name}: {exc}\n"
                        "The signup form may have changed. Check the browser window and complete manually."
                    ),
                    success=False,
                )

            time.sleep(flow.post_signup_wait_seconds)

            # --- Step 5: Check for email verification ---
            notes_out = f"\n\nNotes: {flow.notes}" if flow.notes else ""
            if flow.verify_email_domain:
                current_url = page.url
                page_text_after = page.inner_text("body")
                needs_verify = any(
                    w in page_text_after.lower()
                    for w in ["verify", "confirm", "check your email", "activation"]
                )
                if needs_verify:
                    return ToolResult(
                        tool_name="platform_signup",
                        content=(
                            f"✉️ {flow.name} signup submitted. Email verification required.\n\n"
                            f"Run: email_verify_code(from_domain=\"{flow.verify_email_domain}\")\n"
                            f"Then navigate the browser to complete verification.\n"
                            f"Current page: {current_url}{notes_out}"
                        ),
                        success=True,
                        metadata={"step": "email_verification_needed", "platform": platform},
                    )

            # --- Step 6: Navigate to API key page ---
            if flow.api_key_url:
                page.goto(flow.api_key_url, wait_until="load")
                time.sleep(2)

                # Click "generate" or "create" button if present
                if flow.api_key_create_selector:
                    try:
                        page.click(flow.api_key_create_selector)
                        time.sleep(2)
                    except Exception:
                        pass

                # Extract key
                api_key = ""
                if flow.api_key_selector:
                    try:
                        elem = page.query_selector(flow.api_key_selector)
                        if elem:
                            api_key = (
                                elem.get_attribute("value")
                                or elem.inner_text()
                                or ""
                            ).strip()
                    except Exception:
                        pass

                if api_key:
                    return ToolResult(
                        tool_name="platform_signup",
                        content=(
                            f"✅ {flow.name} signup complete!\n\n"
                            f"API key extracted. Now run:\n"
                            f"credential_save(env_var=\"{flow.env_var_name}\", value=\"{api_key}\")\n"
                            f"to save it to cloud-keys.env.{notes_out}"
                        ),
                        success=True,
                        metadata={
                            "platform": platform,
                            "env_var": flow.env_var_name,
                            "api_key": api_key,
                            "step": "complete",
                        },
                    )
                else:
                    current_url = page.url
                    return ToolResult(
                        tool_name="platform_signup",
                        content=(
                            f"✅ {flow.name} signup submitted. Navigated to API key page.\n\n"
                            f"Could not auto-extract the API key — the browser is open at:\n"
                            f"{current_url}\n\n"
                            f"Copy the API key from the page, then run:\n"
                            f"credential_save(env_var=\"{flow.env_var_name}\", value=\"<your_key>\")"
                            f"{notes_out}"
                        ),
                        success=True,
                        metadata={"platform": platform, "step": "manual_key_copy"},
                    )

            # No api_key_url — return guidance
            return ToolResult(
                tool_name="platform_signup",
                content=(
                    f"✅ {flow.name} signup submitted.\n\n"
                    f"The browser is open. Complete any remaining steps manually, "
                    f"then retrieve the API key and run:\n"
                    f"credential_save(env_var=\"{flow.env_var_name}\", value=\"<your_key>\")"
                    f"{notes_out}"
                ),
                success=True,
                metadata={"platform": platform, "step": "manual_completion"},
            )

        except Exception as exc:
            return ToolResult(
                tool_name="platform_signup",
                content=f"Signup error for {flow.name}: {exc}",
                success=False,
            )
