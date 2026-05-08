#Requires -Version 5.1
<#
.SYNOPSIS
    One-shot setup for OpenJarvis Personal Second Brain on Windows.

.DESCRIPTION
    Creates the Obsidian vault folder structure, writes the OpenJarvis config,
    seeds the MEMORY.md file, checks/pulls Ollama models, and indexes the vault.

.PARAMETER VaultPath
    Path for the new Obsidian vault. Defaults to "$HOME\second-brain".

.EXAMPLE
    .\setup_second_brain.ps1
    .\setup_second_brain.ps1 -VaultPath "D:\MyVault"
#>

param(
    [string]$VaultPath = (Join-Path $HOME "second-brain")
)

$ErrorActionPreference = "Stop"
$ConfigDir = Join-Path $HOME ".openjarvis"
$RepoRoot  = Split-Path -Parent $PSScriptRoot
$ConfigTemplate = Join-Path $RepoRoot "configs\personal\second_brain.toml"

# ── Helpers ──────────────────────────────────────────────────────────────────
function Write-Info    { param($msg) Write-Host "[info]  $msg" -ForegroundColor Cyan    }
function Write-Ok      { param($msg) Write-Host "[ok]    $msg" -ForegroundColor Green   }
function Write-Warn    { param($msg) Write-Host "[warn]  $msg" -ForegroundColor Yellow  }
function Write-Section { param($msg) Write-Host "`n$msg" -ForegroundColor Cyan          }

function Test-Command {
    param([string]$Name)
    $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  OpenJarvis Personal Second Brain — Setup     " -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── Prerequisites check ───────────────────────────────────────────────────────
Write-Section "Checking prerequisites..."

$missing = @()
if (-not (Test-Command "python"))   { $missing += "Python 3.10+  →  https://www.python.org/downloads/" }
if (-not (Test-Command "uv"))       { $missing += "uv            →  https://astral.sh/uv  (run: winget install astral-sh.uv)" }
if (-not (Test-Command "git"))      { $missing += "git           →  https://git-scm.com/download/win" }
if (-not (Test-Command "ollama"))   { $missing += "Ollama        →  https://ollama.com/download/windows" }

if ($missing.Count -gt 0) {
    Write-Warn "The following tools are required but not found in PATH:"
    $missing | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
    Write-Host ""
    $continue = Read-Host "Continue anyway? Some steps will be skipped. (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") { exit 1 }
} else {
    Write-Ok "All prerequisites found."
}

# ── 1. Vault folder structure ──────────────────────────────────────────────────
Write-Section "1. Creating vault at $VaultPath ..."

$folders = @(
    "Jarvis\Memories",
    "Jarvis\Journal",
    "Jarvis\Tasks",
    "Areas",
    "Projects",
    "Resources",
    "Archive",
    "Content\Newsletter",
    "Content\Blog",
    "Content\Twitter",
    "Content\YouTube",
    "Income\Revenue",
    "Income\Ideas",
    "Income\Analytics"
)
foreach ($f in $folders) {
    $dir = Join-Path $VaultPath $f
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
}
Write-Ok "Vault folders created."

# ── 2. Vault README ────────────────────────────────────────────────────────────
$readmePath = Join-Path $VaultPath "README.md"
if (-not (Test-Path $readmePath)) {
    @"
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
- Use frontmatter tags to organise: ``tags: [health, goal]``
- Ask Jarvis: *"What do you know about X?"* to search this vault.
- Ask Jarvis: *"Remember that..."* to create a new memory note.
"@ | Set-Content -Encoding UTF8 -Path $readmePath
    Write-Ok "Created vault README."
}

# ── 3. OpenJarvis config ───────────────────────────────────────────────────────
Write-Section "2. Writing OpenJarvis config..."

if (-not (Test-Path $ConfigDir)) {
    New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
}

$configDest = Join-Path $ConfigDir "config.toml"
if (Test-Path $configDest) {
    Write-Warn "Config already exists at $configDest — skipping. Edit manually if needed."
} elseif (-not (Test-Path $ConfigTemplate)) {
    Write-Warn "Config template not found at $ConfigTemplate — skipping."
} else {
    # Substitute placeholder vault path and convert forward slashes for Windows
    $vaultEscaped = $VaultPath -replace '\\', '/'
    (Get-Content $ConfigTemplate -Raw) -replace '~/second-brain', $vaultEscaped |
        Set-Content -Encoding UTF8 -Path $configDest
    Write-Ok "Config written to $configDest"
}

# ── 4. Initial MEMORY.md ───────────────────────────────────────────────────────
$memoryPath = Join-Path $ConfigDir "MEMORY.md"
if (-not (Test-Path $memoryPath)) {
    @"
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
"@ | Set-Content -Encoding UTF8 -Path $memoryPath
    Write-Ok "Created $memoryPath"
}

# ── 5. Ollama models ───────────────────────────────────────────────────────────
Write-Section "3. Checking Ollama models..."

if (Test-Command "ollama") {
    $pulledModels = ollama list 2>$null | Select-String -Pattern '\S+' | ForEach-Object { $_.Matches[0].Value }

    foreach ($model in @("deepseek-v4-pro:cloud", "qwen2.5:7b")) {
        if ($pulledModels -contains $model) {
            Write-Ok "Model already available: $model"
        } else {
            Write-Info "Pulling $model (this may take a while)..."
            try {
                ollama pull $model
                Write-Ok "Pulled $model"
            } catch {
                Write-Warn "Could not pull $model — pull manually with: ollama pull $model"
            }
        }
    }
} else {
    Write-Warn "Ollama not found. After installing, run:"
    Write-Warn "  ollama pull deepseek-v4-pro:cloud"
    Write-Warn "  ollama pull qwen2.5:7b"
}

# ── 6. Index vault ─────────────────────────────────────────────────────────────
Write-Section "4. Indexing vault into memory backend..."

if (Test-Command "jarvis") {
    try {
        jarvis memory index $VaultPath
        Write-Ok "Vault indexed."
    } catch {
        Write-Warn "Vault indexing failed: $_"
        Write-Warn "Run manually after setup: jarvis memory index `"$VaultPath`""
    }
} else {
    Write-Warn "'jarvis' CLI not found. After installing OpenJarvis, run:"
    Write-Warn "  jarvis memory index `"$VaultPath`""
}

# ── Done ───────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Setup complete!                              " -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Vault:   " -NoNewline; Write-Host $VaultPath   -ForegroundColor Cyan
Write-Host "  Config:  " -NoNewline; Write-Host $configDest  -ForegroundColor Cyan
Write-Host "  Memory:  " -NoNewline; Write-Host $memoryPath  -ForegroundColor Cyan
Write-Host ""
Write-Host "  Start chatting:  " -NoNewline; Write-Host "jarvis chat" -ForegroundColor Cyan
Write-Host "  Search memory:   " -NoNewline; Write-Host "jarvis memory search `"your query`"" -ForegroundColor Cyan
Write-Host "  Re-index vault:  " -NoNewline; Write-Host "jarvis memory index `"$VaultPath`"" -ForegroundColor Cyan
Write-Host ""
