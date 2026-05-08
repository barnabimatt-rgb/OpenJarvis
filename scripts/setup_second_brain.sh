#!/usr/bin/env bash
# setup_second_brain.sh — One-shot setup for OpenJarvis Personal Second Brain
#
# Usage:
#   bash scripts/setup_second_brain.sh [VAULT_PATH]
#
# VAULT_PATH defaults to ~/second-brain.
# Safe to run multiple times — existing files are never overwritten.

set -euo pipefail

VAULT="${1:-$HOME/second-brain}"
CONFIG_DIR="$HOME/.openjarvis"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_TEMPLATE="$REPO_ROOT/configs/personal/second_brain.toml"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[info]${NC}  $*"; }
success() { echo -e "${GREEN}[ok]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC}  $*"; }

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  OpenJarvis Personal Second Brain — Setup     ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo ""

# ── 1. Create Obsidian vault folder structure ─────────────────────────────────
info "Creating vault at $VAULT ..."
mkdir -p "$VAULT"/{Jarvis/{Memories,Journal,Tasks},Areas,Projects,Resources,Archive}
success "Vault folders created."

# ── 2. Vault README ───────────────────────────────────────────────────────────
if [ ! -f "$VAULT/README.md" ]; then
    cat > "$VAULT/README.md" <<'EOF'
# Second Brain

Managed by OpenJarvis. Open this vault in Obsidian for a human-readable view.

## Folder Structure

| Folder | Purpose |
|--------|---------|
| **Jarvis/Memories/** | Facts, preferences, and notes saved automatically by the AI |
| **Jarvis/Journal/**  | Daily journal entries (agent or user-created) |
| **Jarvis/Tasks/**    | Tasks and reminders tracked by the AI |
| **Areas/**           | Ongoing life areas: health, finance, relationships, work, etc. |
| **Projects/**        | Active projects with goals and next actions |
| **Resources/**       | Reference notes, articles, research, and saved links |
| **Archive/**         | Completed or inactive notes |

## Tips

- Edit any note freely — Jarvis will re-index changes next startup.
- Use frontmatter tags to organise: `tags: [health, goal]`
- Ask Jarvis: *"What do you know about X?"* to search this vault.
- Ask Jarvis: *"Remember that..."* to create a new memory note.
EOF
    success "Created vault README."
fi

# ── 3. OpenJarvis config ──────────────────────────────────────────────────────
mkdir -p "$CONFIG_DIR"
if [ ! -f "$CONFIG_DIR/config.toml" ]; then
    # Substitute placeholder vault path with the actual path
    sed "s|~/second-brain|$VAULT|g" "$CONFIG_TEMPLATE" > "$CONFIG_DIR/config.toml"
    success "Config written to $CONFIG_DIR/config.toml"
else
    warn "Config already exists at $CONFIG_DIR/config.toml — skipping. Edit manually if needed."
fi

# ── 4. Initial MEMORY.md ──────────────────────────────────────────────────────
if [ ! -f "$CONFIG_DIR/MEMORY.md" ]; then
    cat > "$CONFIG_DIR/MEMORY.md" <<'EOF'
# Agent Memory

OpenJarvis reads and updates this file across every session.
You can edit it manually; the agent will also add entries here automatically.

---

## About Me

<!-- The agent will populate this section as you share information about yourself. -->

## Preferences

<!-- Communication style, topics of interest, tools you use, etc. -->

## Goals

<!-- Short-term and long-term goals you've shared with the agent. -->

## Important People

<!-- Family, friends, colleagues — names, relationships, key details. -->

## Reminders & Follow-ups

<!-- Ongoing commitments or things to keep an eye on. -->
EOF
    success "Created $CONFIG_DIR/MEMORY.md"
fi

# ── 5. Check Ollama models ────────────────────────────────────────────────────
echo ""
info "Checking Ollama models ..."
if command -v ollama &>/dev/null; then
    PULLED=$(ollama list 2>/dev/null | awk '{print $1}')
    for MODEL in "deepseek-v4-pro:cloud" "qwen2.5:7b"; do
        if echo "$PULLED" | grep -qF "$MODEL"; then
            success "Model already available: $MODEL"
        else
            warn "Model not found: $MODEL — pulling now (this may take a while)..."
            ollama pull "$MODEL" && success "Pulled $MODEL" || warn "Could not pull $MODEL — pull manually with: ollama pull $MODEL"
        fi
    done
else
    warn "Ollama not found in PATH. Install from https://ollama.com then run:"
    warn "  ollama pull deepseek-v4-pro:cloud && ollama pull qwen2.5:7b"
fi

# ── 6. Index vault into memory ────────────────────────────────────────────────
echo ""
info "Indexing vault into memory backend ..."
if command -v jarvis &>/dev/null; then
    jarvis memory index "$VAULT" && success "Vault indexed."
else
    warn "'jarvis' CLI not found. After installing OpenJarvis run:"
    warn "  jarvis memory index $VAULT"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup complete!                              ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "  Vault:   ${CYAN}$VAULT${NC}"
echo -e "  Config:  ${CYAN}$CONFIG_DIR/config.toml${NC}"
echo -e "  Memory:  ${CYAN}$CONFIG_DIR/MEMORY.md${NC}"
echo ""
echo -e "  Start chatting:  ${CYAN}jarvis chat${NC}"
echo -e "  Search memory:   ${CYAN}jarvis memory search \"your query\"${NC}"
echo -e "  Re-index vault:  ${CYAN}jarvis memory index $VAULT${NC}"
echo ""
