"""Credential store — persist API keys to cloud-keys.env and reload the live server.

Provides two tools:
  credential_save — append/update a KEY=value entry in cloud-keys.env and
                    POST /v1/cloud/reload so the running server picks it up instantly
  credential_get  — read the current value of a named key from cloud-keys.env

Security notes:
  - credential_get returns the actual value so agents can verify persistence.
    Only use in trusted agent contexts.
  - credential_save logs the key NAME (never the value) to Obsidian for audit.
  - The file is written with mode 0o600 (owner-readable only).
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

import httpx

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_KEYS_FILE = Path.home() / ".openjarvis" / "cloud-keys.env"
_RELOAD_URL = "http://localhost:8000/v1/cloud/reload"


def _read_keys() -> dict:
    """Parse cloud-keys.env into a dict."""
    result = {}
    if not _KEYS_FILE.exists():
        return result
    for line in _KEYS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def _write_keys(keys: dict) -> None:
    """Write a dict back to cloud-keys.env preserving comments."""
    _KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing_lines = []
    if _KEYS_FILE.exists():
        existing_lines = _KEYS_FILE.read_text(encoding="utf-8").splitlines()

    # Update existing lines in-place
    updated_keys = set()
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        k, _, _ = stripped.partition("=")
        k = k.strip()
        if k in keys:
            new_lines.append(f"{k}={keys[k]}")
            updated_keys.add(k)
        else:
            new_lines.append(line)

    # Append any new keys that weren't already in the file
    for k, v in keys.items():
        if k not in updated_keys:
            new_lines.append(f"{k}={v}")

    content = "\n".join(new_lines)
    if content and not content.endswith("\n"):
        content += "\n"

    _KEYS_FILE.write_text(content, encoding="utf-8")
    try:
        os.chmod(_KEYS_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except OSError:
        pass


def _reload_server() -> bool:
    """Tell the running Jarvis server to reload cloud keys. Returns True on success."""
    try:
        resp = httpx.post(_RELOAD_URL, timeout=5.0)
        return resp.status_code < 300
    except Exception:
        return False


def _log_to_obsidian(env_var: str) -> None:
    """Append an audit entry (key name only) to the credentials log in Obsidian."""
    try:
        from datetime import datetime, timezone
        vault = Path.home() / "second-brain"
        log_dir = vault / "Income" / "Setup"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "credentials-log.md"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"- {ts} — `{env_var}` saved to cloud-keys.env\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# credential_save
# ---------------------------------------------------------------------------


@ToolRegistry.register("credential_save")
class CredentialSaveTool(BaseTool):
    """Save an API key to cloud-keys.env and reload the live server."""

    tool_id = "credential_save"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="credential_save",
            description=(
                "Save an API key or credential to ~/.openjarvis/cloud-keys.env. "
                "Automatically reloads the running Jarvis server so the key is active "
                "immediately without a restart. Logs the key NAME (not value) to Obsidian."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "env_var": {
                        "type": "string",
                        "description": "Environment variable name (e.g. 'BEEHIIV_API_KEY').",
                    },
                    "value": {
                        "type": "string",
                        "description": "The credential value to store.",
                    },
                },
                "required": ["env_var", "value"],
            },
            category="system",
        )

    def execute(self, *, env_var: str, value: str, **_: Any) -> ToolResult:
        if not re.match(r"^[A-Z][A-Z0-9_]{1,63}$", env_var):
            return ToolResult(
                tool_name="credential_save",
                content=f"Invalid env_var name '{env_var}'. Use UPPER_SNAKE_CASE.",
                success=False,
            )
        if not value.strip():
            return ToolResult(
                tool_name="credential_save",
                content="Value cannot be empty.",
                success=False,
            )
        try:
            keys = _read_keys()
            keys[env_var] = value.strip()
            _write_keys(keys)

            # Also set in current process environment for immediate use
            os.environ[env_var] = value.strip()

            reloaded = _reload_server()
            _log_to_obsidian(env_var)

            reload_note = "Server reloaded — key is active now." if reloaded else \
                          "Note: server reload failed (may not be running) — restart with: jarvis serve"

            return ToolResult(
                tool_name="credential_save",
                content=(
                    f"✅ {env_var} saved to ~/.openjarvis/cloud-keys.env\n"
                    f"{reload_note}"
                ),
                success=True,
                metadata={"env_var": env_var, "server_reloaded": reloaded},
            )
        except Exception as exc:
            return ToolResult(
                tool_name="credential_save",
                content=f"Failed to save credential: {exc}",
                success=False,
            )


# ---------------------------------------------------------------------------
# credential_get
# ---------------------------------------------------------------------------


@ToolRegistry.register("credential_get")
class CredentialGetTool(BaseTool):
    """Read a credential value from cloud-keys.env."""

    tool_id = "credential_get"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="credential_get",
            description=(
                "Read the current value of a named credential from "
                "~/.openjarvis/cloud-keys.env. Use to verify that a key was saved "
                "correctly after credential_save or platform_signup."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "env_var": {
                        "type": "string",
                        "description": "Environment variable name to read (e.g. 'BEEHIIV_API_KEY').",
                    },
                },
                "required": ["env_var"],
            },
            category="system",
        )

    def execute(self, *, env_var: str, **_: Any) -> ToolResult:
        # Check live environment first (may have been set in-process)
        live_val = os.environ.get(env_var, "")
        if live_val:
            masked = live_val[:6] + "..." + live_val[-4:] if len(live_val) > 10 else "***"
            return ToolResult(
                tool_name="credential_get",
                content=f"✅ {env_var} is set (value: {masked})",
                success=True,
                metadata={"env_var": env_var, "is_set": True, "masked_value": masked},
            )

        keys = _read_keys()
        if env_var in keys:
            v = keys[env_var]
            masked = v[:6] + "..." + v[-4:] if len(v) > 10 else "***"
            # Set in process env for this session
            os.environ[env_var] = v
            return ToolResult(
                tool_name="credential_get",
                content=f"✅ {env_var} is set in cloud-keys.env (value: {masked})",
                success=True,
                metadata={"env_var": env_var, "is_set": True, "masked_value": masked},
            )

        return ToolResult(
            tool_name="credential_get",
            content=(
                f"❌ {env_var} is NOT set.\n"
                f"Run platform_signup or credential_save to configure it."
            ),
            success=True,
            metadata={"env_var": env_var, "is_set": False},
        )
