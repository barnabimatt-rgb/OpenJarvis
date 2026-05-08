# OpenJarvis — Complete Guide
### Personal Second Brain + Passive Income Engine

---

## Table of Contents

1. [What Is OpenJarvis](#1-what-is-openjarvis)
2. [Prerequisites](#2-prerequisites)
3. [Installation — macOS / Linux](#3-installation--macos--linux)
4. [Installation — Windows](#4-installation--windows)
5. [Desktop App (Optional)](#5-desktop-app-optional)
6. [Understanding the Configs](#6-understanding-the-configs)
7. [Set Up Your Second Brain (Obsidian Vault)](#7-set-up-your-second-brain-obsidian-vault)
8. [Platform Onboarding — Create All Your Accounts](#8-platform-onboarding--create-all-your-accounts)
9. [Add API Keys](#9-add-api-keys)
10. [Start the Passive Income Engine](#10-start-the-passive-income-engine)
11. [What Happens Every Morning at 7 AM](#11-what-happens-every-morning-at-7-am)
12. [Income Streams Explained](#12-income-streams-explained)
13. [All Tools Reference](#13-all-tools-reference)
14. [All Connectors Reference](#14-all-connectors-reference)
15. [Revenue Tracking](#15-revenue-tracking)
16. [Publishing Workflow](#16-publishing-workflow)
17. [Troubleshooting](#17-troubleshooting)
18. [Quick Reference Card](#18-quick-reference-card)

---

## 1. What Is OpenJarvis

OpenJarvis is a local-first AI agent framework that runs entirely on your machine. It combines:

- **A persistent personal second brain** — remembers everything you tell it, stores notes to an Obsidian vault, searches memory semantically
- **A passive income engine** — autonomously discovers trending niches, drafts content for 12+ platforms daily, tracks revenue across all your income streams
- **A browser automation layer** — can create accounts on platforms, extract API keys, and fill forms on your behalf
- **A scheduled operative agent** — runs at 7 AM every day without you having to do anything

Everything runs locally. Your data never leaves your machine unless you explicitly tell the agent to publish something. Every piece of content is saved as a draft in Obsidian for your review before it goes anywhere public.

### How It Makes Money

The agent doesn't make money by itself — it builds the infrastructure that earns passively:

| Stream | How | Timeline |
|---|---|---|
| Newsletter (Beehiiv) | Sponsorships + paid subscriber tier | Month 3–6 |
| Blog (Ghost) | SEO organic traffic → affiliate links | Month 2–4 |
| Twitter/X threads | Audience growth → funnel to products | Month 1+ |
| Affiliate commissions | Blog posts recommending tools with tracked links | Month 2+ |
| Digital products (Gumroad / Lemon Squeezy) | Ebooks, templates, mini-courses | Month 4–6 |
| Email list (ConvertKit) | Nurture sequences → product sales | Month 3+ |
| Dev.to / Medium | Cross-posting blog for additional reach | Month 1+ |
| Patreon | Monthly supporters for exclusive content | Month 6+ |

---

## 2. Prerequisites

Install these before anything else.

### Required (all platforms)

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.10+ | python.org |
| Git | any | git-scm.com |
| Ollama | latest | ollama.com |
| uv (Python package manager) | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 18+ | nodejs.org |

### For browser automation (account creation)

```bash
# After installing OpenJarvis:
uv sync --extra browser
playwright install chromium
```

### For the Desktop App (optional)

| Tool | Minimum version | Install |
|---|---|---|
| Rust | latest stable | rustup.rs |
| Tauri CLI | 2.x | `cargo install tauri-cli` |

---

## 3. Installation — macOS / Linux

```bash
# 1. Clone the repo
git clone https://github.com/open-jarvis/OpenJarvis.git
cd OpenJarvis

# 2. One-command quickstart (installs deps, pulls a starter model, opens the UI)
./scripts/quickstart.sh
```

The quickstart script does the following automatically:
- Checks Python 3.10+, Node.js 18+, uv, Ollama
- Installs Ollama if missing (macOS via Homebrew, Linux via install script)
- Starts the Ollama daemon if not running
- Pulls `qwen3:0.6b` as a starter model
- Runs `uv sync --extra server` to install all Python dependencies
- Builds the Rust extension (`maturin develop`)
- Installs frontend Node dependencies
- Starts the backend API on port 8000 and frontend on port 5173
- Opens your browser to the chat UI

**To stop:** press `Ctrl+C`

### Manual install (if quickstart fails)

```bash
# Install Python deps
uv sync --extra server

# Build Rust extension
uv run maturin develop -m rust/crates/openjarvis-python/Cargo.toml

# Pull the AI models (these are the recommended ones)
ollama pull deepseek-v4-pro:cloud   # primary — best reasoning
ollama pull qwen2.5:7b              # fallback — works fully offline

# Start the backend
uv run jarvis serve --port 8000

# In another terminal, start the frontend
cd frontend && npm install && npm run dev
```

---

## 4. Installation — Windows

### Step 1: Install prerequisites

Open PowerShell as Administrator and run:

```powershell
# Install winget packages
winget install Python.Python.3.11
winget install Git.Git
winget install OpenJS.NodeJS
winget install astral-sh.uv

# Install Ollama — download the Windows installer from:
# https://ollama.com/download/windows
# Then run the .exe
```

### Step 2: Clone and install

```powershell
git clone https://github.com/open-jarvis/OpenJarvis.git
cd OpenJarvis

# Install Python deps
uv sync --extra server

# Build Rust extension
uv run maturin develop -m rust/crates/openjarvis-python/Cargo.toml
```

### Step 3: Set up the second brain

```powershell
# Run the Windows setup script
.\scripts\setup_second_brain.ps1

# Or with a custom vault path:
.\scripts\setup_second_brain.ps1 -VaultPath "D:\MyVault"
```

### Step 4: Start

```powershell
# Terminal 1 — backend
uv run jarvis serve --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 5. Desktop App (Optional)

The Tauri desktop app gives you a native window on Mac and Windows with a system tray icon, always-on-top overlay (macOS), and reads your `config.toml` to automatically use the right model and agent.

### Build from source

```bash
# macOS / Linux
cd frontend
npm install
npm run tauri build

# Windows (PowerShell)
cd frontend
npm install
npm run tauri build
```

The built app will be in `frontend/src-tauri/target/release/bundle/`.

### How the desktop app reads your config

The app reads `~/.openjarvis/config.toml` at startup. If you set:

```toml
[intelligence]
default_model = "deepseek-v4-pro:cloud"

[agent]
default_agent = "operative"
```

...the app will use those values instead of its built-in defaults. Cloud models (anything ending in `:cloud`) skip the local Ollama pull step.

---

## 6. Understanding the Configs

All config files live in `configs/personal/`. Copy the one you want to `~/.openjarvis/config.toml`.

| Config file | Purpose |
|---|---|
| `second_brain.toml` | Personal assistant — persistent memory, Obsidian vault, daily conversations |
| `passive_income.toml` | **Full passive income engine** — runs at 7 AM, generates content, tracks revenue |
| `affiliate_marketing.toml` | Affiliate-focused variant — runs at 6 AM, specialized for affiliate content |
| `platform_setup.toml` | One-time onboarding — creates accounts on all platforms |

### Config structure

Every config has five pillars:

```toml
[intelligence]       # Which AI model to use
[agent]              # What the agent does (its "job description")
[agent.schedule]     # When to run automatically
[tools.storage]      # Memory backend (Obsidian + SQLite)
[connectors.*]       # Platform connections
```

---

## 7. Set Up Your Second Brain (Obsidian Vault)

The second brain is an Obsidian vault that the agent reads from and writes to. Run this once:

```bash
# macOS / Linux
bash scripts/setup_second_brain.sh ~/second-brain

# Windows
.\scripts\setup_second_brain.ps1

# Custom path
bash scripts/setup_second_brain.sh /path/to/your/vault
```

This creates:

```
~/second-brain/
├── Jarvis/
│   ├── Memories/      ← Agent-created memory notes
│   ├── Journal/       ← Daily journal entries
│   └── Tasks/         ← Task tracking
├── Content/
│   ├── Newsletter/    ← Daily newsletter drafts (review before sending)
│   ├── Blog/
│   │   └── affiliate/ ← Affiliate-focused blog drafts
│   ├── Twitter/       ← Thread drafts
│   └── YouTube/       ← Video scripts
├── Income/
│   ├── Revenue/       ← Daily revenue snapshots
│   ├── Ideas/         ← Product and niche ideas
│   ├── Analytics/     ← Performance tracking
│   └── Setup/         ← Onboarding logs + credentials audit log
├── Areas/             ← Life areas (health, finance, work, etc.)
├── Projects/          ← Active projects
├── Resources/         ← Reference notes
└── Archive/           ← Completed notes
```

**Open the vault in Obsidian:** File → Open Vault → select `~/second-brain`

The agent will write new notes here automatically. You can edit any note — the agent re-indexes changes on next startup.

---

## 8. Platform Onboarding — Create All Your Accounts

Before the passive income engine can publish anything, it needs API keys for each platform. The `platform_setup` agent automates this.

### Step 1: Install browser automation

```bash
uv sync --extra browser
playwright install chromium
```

### Step 2: Run the onboarding agent

```bash
jarvis serve --config configs/personal/platform_setup.toml
```

Open `http://localhost:5173` and start chatting. Say:

> "Set up all my platforms"

or to do them one at a time:

> "Set up Dev.to"

### What happens for each platform

1. The agent checks if the API key is already saved — skips if so
2. Asks you for your email and password to use
3. Opens a **visible Chrome window** so you can watch and intervene
4. Fills the signup form
5. Detects any CAPTCHA — either auto-solves (if you have a 2Captcha key) or pauses for you to solve manually
6. Watches your Gmail for the verification email and extracts the code automatically
7. Navigates to the API settings page and copies the key
8. Saves the key to `~/.openjarvis/cloud-keys.env`
9. Reloads the server live — no restart needed
10. Logs the platform name to `~/second-brain/Income/Setup/onboarding-status.md`

### Platform order (easiest → hardest)

| # | Platform | What you'll need |
|---|---|---|
| 1 | Dev.to | Email + password |
| 2 | ConvertKit | Email + password |
| 3 | Beehiiv | Email + password |
| 4 | Gumroad | Email + password |
| 5 | Lemon Squeezy | Email + password |
| 6 | Patreon | Email + password (has CAPTCHA) |
| 7 | Medium | Email only (magic link login) |
| 8 | Reddit | Email + password + username (has CAPTCHA) |
| 9 | Twitter/X | Email + password (has CAPTCHA; developer approval required after) |
| 10 | LinkedIn | Email + password (has CAPTCHA; OAuth required for API) |
| 11 | Ghost | Email + password (self-hosted or Ghost Pro) |
| 12 | Stripe | Email + password (get a restricted read-only key) |

### Platforms that need extra manual steps

**Twitter/X:** After basic account creation, you need to apply for a developer account at `developer.twitter.com`. Free tier allows 1,500 tweets/month. Approval usually takes 1–2 days.

**LinkedIn:** Requires creating an app at `linkedin.com/developers` and completing an OAuth 2.0 flow to get an access token.

**Stripe:** Use a **restricted key** (read-only access to charges and subscriptions) — never use your live secret key. Create one at `dashboard.stripe.com → Developers → Restricted keys`.

**Ghost:** If self-hosted, the Admin API key is under `Ghost Admin → Settings → Integrations → Add Custom Integration`.

**CAPTCHA solving (optional):** Sign up at [2captcha.com](https://2captcha.com) — top up $5 and add `TWOCAPTCHA_API_KEY=your_key` to `cloud-keys.env`. Without this, the agent will pause and ask you to solve CAPTCHAs manually in the browser window.

---

## 9. Add API Keys

All keys live in one file: `~/.openjarvis/cloud-keys.env`

Create or edit it:

```bash
nano ~/.openjarvis/cloud-keys.env
```

Full list of supported keys:

```bash
# ── AI Models ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...       # For Claude models
OPENAI_API_KEY=sk-...              # For GPT models
OPENROUTER_API_KEY=...             # For OpenRouter

# ── Publishing ─────────────────────────────────────────────────────
BEEHIIV_API_KEY=...
BEEHIIV_PUBLICATION_ID=pub_...     # Settings → Publication → ID
GHOST_ADMIN_URL=https://yourblog.ghost.io
GHOST_ADMIN_API_KEY=id:secret
MEDIUM_INTEGRATION_TOKEN=...
DEVTO_API_KEY=...
CONVERTKIT_API_KEY=...

# ── Social ─────────────────────────────────────────────────────────
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
LINKEDIN_ACCESS_TOKEN=...
LINKEDIN_PERSON_URN=urn:li:person:XXXXXX
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USERNAME=...
REDDIT_PASSWORD=...

# ── Video ──────────────────────────────────────────────────────────
YOUTUBE_API_KEY=...

# ── Revenue ────────────────────────────────────────────────────────
STRIPE_SECRET_KEY=rk_live_...      # RESTRICTED read-only key only
GUMROAD_ACCESS_TOKEN=...
LEMON_SQUEEZY_API_KEY=...
PATREON_ACCESS_TOKEN=...           # OAuth creator token

# ── CAPTCHA (optional) ────────────────────────────────────────────
TWOCAPTCHA_API_KEY=...             # 2captcha.com — ~$3/1000 solves

# ── Link shortening (optional) ────────────────────────────────────
BITLY_ACCESS_TOKEN=...

# ── Revenue alerts (optional) ─────────────────────────────────────
REVENUE_DAILY_TARGET=50.00         # Alert when daily revenue hits this
REVENUE_DROP_THRESHOLD_PCT=30      # Alert on % revenue drop vs yesterday
```

**File permissions:** The file should be readable only by you:

```bash
chmod 600 ~/.openjarvis/cloud-keys.env
```

**After adding a key:** If the server is already running, the agent will reload keys automatically on next tool use. Or force a reload:

```bash
curl -X POST http://localhost:8000/v1/cloud/reload
```

---

## 10. Start the Passive Income Engine

### Copy the config

```bash
cp configs/personal/passive_income.toml ~/.openjarvis/config.toml
```

Edit the vault path if yours is different from `~/second-brain`:

```bash
nano ~/.openjarvis/config.toml
# Change: vault_path = "~/second-brain"
# To: vault_path = "/your/actual/vault/path"
# (appears in two places)
```

### Start the server

```bash
jarvis serve
```

Or with the config explicitly:

```bash
jarvis serve --config ~/.openjarvis/config.toml
```

The operative agent will now run automatically at **7:00 AM local time every day**.

### Test it immediately

Don't want to wait for 7 AM? Trigger the routine manually:

```bash
# In the chat UI or via CLI:
jarvis chat
```

Then say:

> "Run the morning routine now"

or:

> "Discover today's best niche and draft a newsletter"

### Run as a background service

**macOS (launchd):**

```bash
# Create a launch agent
cat > ~/Library/LaunchAgents/com.openjarvis.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openjarvis</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/uv</string>
        <string>run</string>
        <string>jarvis</string>
        <string>serve</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/OpenJarvis</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.openjarvis.plist
```

**Linux (systemd):**

```bash
cat > ~/.config/systemd/user/openjarvis.service << 'EOF'
[Unit]
Description=OpenJarvis Passive Income Engine

[Service]
WorkingDirectory=/path/to/OpenJarvis
ExecStart=/home/youruser/.local/bin/uv run jarvis serve
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user enable openjarvis
systemctl --user start openjarvis
```

**Windows (Task Scheduler):**

```powershell
$action = New-ScheduledTaskAction -Execute "uv" -Argument "run jarvis serve" -WorkingDirectory "C:\path\to\OpenJarvis"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "OpenJarvis" -Action $action -Trigger $trigger -RunLevel Highest
```

---

## 11. What Happens Every Morning at 7 AM

The operative agent wakes up and executes this routine automatically:

### Step 1 — Revenue Check (2 min)
Pulls data from Stripe, Gumroad, and Lemon Squeezy. Logs a snapshot to `~/second-brain/Income/Revenue/YYYY-MM-DD.md`. Flags unusual spikes or drops with a warning.

### Step 2 — Niche Discovery (3 min)
Runs `niche_discovery` which scans:
- **Google Trends** daily trending RSS feed
- **HackerNews** top 15 stories
- **Reddit** trending subreddits
- **Product Hunt** new launches

Scores each topic on **growth velocity (40%) + low competition (30%) + monetization potential (30%)**. Picks the highest-scoring niche not used in the last 14 days. Stores the choice in memory.

### Step 3 — Research (5 min)
Uses `web_search` to gather 8–12 facts on the chosen niche:
- One surprising statistic
- One common misconception to debunk
- Two monetization angles (tools, courses, affiliates)
- Three content hooks (questions people are asking)

### Step 4 — Content Generation (15 min)
Drafts and saves all content to Obsidian. **Nothing is published yet.**

**4a. Newsletter draft** → `~/second-brain/Content/Newsletter/YYYY-MM-DD-<slug>.md`
- Compelling subject line + preview text
- "The Opportunity" section (80 words)
- "What Nobody Is Saying" — contrarian insight (100 words)
- "How To Profit" — two monetization paths (120 words)
- Single CTA

**4b. Blog post draft** → `~/second-brain/Content/Blog/YYYY-MM-DD-<slug>.md`
- SEO-optimised title (50–60 chars)
- Meta description (150 chars)
- Five H2 sections with affiliate-friendly tool recommendations
- Conclusion + newsletter CTA

**4c. Three Twitter thread drafts** → `~/second-brain/Content/Twitter/YYYY-MM-DD-thread-N.md`
- Each thread is 10 tweets
- Three different content angles
- Hook tweet + body + monetization recommendation + CTA

### Step 5 — Summary
The agent outputs a 5-bullet summary to the chat:
```
• Niche: <topic> (score: X/100)
• Newsletter: ~/second-brain/Content/Newsletter/<file>
• Blog post: ~/second-brain/Content/Blog/<file>
• Twitter threads: 3 drafts in Content/Twitter/
• Revenue: MRR $X · Today $X
```

---

## 12. Income Streams Explained

### Newsletter (Beehiiv)

Beehiiv is the recommended newsletter platform because it has a generous free tier (up to 2,500 subscribers) and built-in monetization via its ad network (Boosts).

**How you earn:**
- Beehiiv Boosts: get paid $1–$3 per new subscriber you send to other newsletters (the platform handles it automatically)
- Paid subscriptions: once you have a following, charge $5–$10/month for a premium tier
- Sponsorships: brands pay $100–$1,000+ per placement once you reach 1,000+ subscribers

**The agent's role:** Drafts one newsletter issue per day. You review it in Obsidian, make any edits, then tell the agent:

> "Publish today's newsletter draft to Beehiiv"

### Blog — Ghost

Ghost is a clean, fast blogging platform. Self-hosting on a $4/month VPS (DigitalOcean, Vultr) keeps costs near zero.

**How you earn:**
- Affiliate links: every blog post recommends 2–4 tools with your affiliate links
- SEO organic traffic: takes 3–6 months to build but compounds forever
- Ghost paid memberships: charge for premium content once audience grows

**The agent's role:** Drafts one SEO blog post per day. You review and publish when ready.

### Twitter / X

Twitter's free developer tier allows 1,500 tweets per month — enough for 5 threads per day.

**How you earn:**
- Build audience → drive traffic to newsletter, blog, products
- Twitter itself pays for ads on reply threads once you reach 500+ followers and 5M impressions/month

**The agent's role:** Drafts 3 thread outlines daily. You pick the best one and tell the agent:

> "Post thread 2 from today's drafts"

### Affiliate Marketing

Every blog post, newsletter, and thread naturally recommends tools. Those recommendations use your tracked UTM links.

**Best affiliate programs to join first** (already in the `affiliate_finder` tool database):
- ConvertKit: 30% recurring
- Beehiiv: 50% for 12 months
- Webflow: up to 50% recurring
- HubSpot: 30% recurring
- NordVPN: 40% + 30% recurring
- Jasper AI: 30% recurring
- Kajabi: 30% recurring

**The agent's role:** Runs `affiliate_finder(niche=<today_niche>)` and weaves the top programs naturally into blog posts and newsletters.

### Digital Products (Gumroad / Lemon Squeezy)

Once you've established a niche and audience (typically month 4–6), package your knowledge:
- A $19 ebook (50 pages)
- A $49 template pack
- A $99 mini-course
- A $29/month SaaS tool (built on OpenJarvis itself)

**Lemon Squeezy vs Gumroad:**
- Lemon Squeezy: better for subscriptions and SaaS, handles VAT automatically
- Gumroad: simpler setup, better for one-time digital downloads

### Patreon

Once you have regular readers, some will pay $3–$15/month for:
- Early access to posts
- Behind-the-scenes updates
- Monthly Q&A

The agent tracks patron count and monthly pledge total daily.

---

## 13. All Tools Reference

These are the tools the agent can call. You can also call any of them directly in chat.

### Research Tools

| Tool | What it does |
|---|---|
| `web_search` | Searches the web via Tavily (paid) or DuckDuckGo (free fallback) |
| `niche_discovery` | Scans Google Trends, HackerNews, Reddit, Product Hunt — returns ranked niches with scores |
| `affiliate_finder` | Finds relevant affiliate programs for a niche from 35+ curated programs + web discovery |
| `seo_keywords` | Google Autocomplete + DuckDuckGo competition scoring — classifies keywords by difficulty and intent |

### Content Tools

| Tool | What it does |
|---|---|
| `content_repurpose` | Transforms one piece of content into 8 platform formats (newsletter, blog, Twitter, LinkedIn, YouTube, Reddit, Dev.to, short-form hook) |
| `file_write` | Saves content to Obsidian vault or any file path |
| `file_read` | Reads any file |
| `image_generate` | Generates images for blog posts / social media |
| `text_to_speech` | Converts text to audio for the morning digest |

### Publishing Tools

| Tool | What it does |
|---|---|
| `beehiiv_create_draft` | Creates a Beehiiv newsletter draft |
| `beehiiv_send` | Sends a Beehiiv newsletter to subscribers |
| `beehiiv_stats` | Gets open rate, click rate, subscriber count |
| `ghost_create_draft` | Creates a Ghost blog post draft |
| `ghost_publish` | Publishes a Ghost post publicly |
| `ghost_list_posts` | Lists your Ghost posts |
| `devto_create_draft` | Creates a Dev.to article draft |
| `devto_publish` | Publishes to Dev.to |
| `devto_article_stats` | Gets views, reactions, comments per article |
| `medium_create_draft` | Creates a Medium story draft |
| `medium_publish` | Publishes to Medium |
| `twitter_post_tweet` | Posts a single tweet |
| `twitter_post_thread` | Posts a reply-chained thread of up to 25 tweets |
| `twitter_get_metrics` | Gets impressions, likes, retweets for a tweet |
| `linkedin_post` | Posts a LinkedIn text update |
| `linkedin_share_article` | Shares a link post on LinkedIn |
| `reddit_post_link` | Submits a link post to a subreddit |
| `reddit_post_text` | Submits a self-text post to a subreddit |
| `reddit_subreddit_info` | Gets subscriber count and description for a subreddit |
| `convertkit_create_broadcast` | Creates a ConvertKit broadcast draft |
| `post_schedule` | Queues a post for the platform's peak engagement time |
| `post_queue_list` | Lists all scheduled posts |

### Analytics Tools

| Tool | What it does |
|---|---|
| `analytics_summary` | Pulls stats from all 10 platforms concurrently — one unified dashboard |
| `youtube_channel_stats` | Subscribers, views, video count |
| `youtube_generate_metadata` | Generates SEO-optimised title, description, tags for a video |
| `youtube_recent_videos` | Lists recent video performance |
| `patreon_summary` | Patron count, monthly pledge total |
| `convertkit_subscriber_stats` | Total subscribers, recent broadcast count |
| `gumroad_sales_summary` | Today's sales, this month, all time |
| `lemon_squeezy_revenue` | MRR, active subscriptions, today's revenue |
| `stripe_revenue_summary` | MRR, today's revenue, new customers |
| `utm_link` | Generates UTM-tracked affiliate links; stores for attribution |
| `revenue_alert_check` | Checks thresholds and sends Telegram alerts on milestones |

### Memory Tools

| Tool | What it does |
|---|---|
| `memory_manage` | Store, retrieve, and search personal memories |
| `memory_store` | Save a specific fact to memory |
| `memory_search` | Semantic search across all memories |
| `obsidian_search_notes` | Full-text search across your Obsidian vault |

### Browser / Setup Tools

| Tool | What it does |
|---|---|
| `browser_navigate` | Navigate to a URL (add `headed=true` for visible window) |
| `browser_click` | Click an element (CSS selector or text) |
| `browser_type` | Type text into a form field |
| `browser_screenshot` | Take a screenshot of the current page |
| `browser_extract` | Extract text, links, or tables from a page |
| `platform_signup` | Automates account creation for 12 platforms |
| `captcha_solve` | Solves reCAPTCHA/hCaptcha via 2Captcha API |
| `email_verify_code` | Polls Gmail for platform verification emails |
| `credential_save` | Saves an API key to cloud-keys.env + reloads server live |
| `credential_get` | Reads a credential value from cloud-keys.env |

---

## 14. All Connectors Reference

Connectors are data sources that sync to memory and expose tools to the agent.

| Connector | What it connects | Auth needed |
|---|---|---|
| `beehiiv` | Newsletter: posts, subscribers, stats | `BEEHIIV_API_KEY` + `BEEHIIV_PUBLICATION_ID` |
| `ghost` | Blog: posts, pages | `GHOST_ADMIN_URL` + `GHOST_ADMIN_API_KEY` |
| `twitter` | Tweets, thread posting, metrics | 4 Twitter OAuth keys |
| `linkedin` | Posts, article shares | `LINKEDIN_ACCESS_TOKEN` + `LINKEDIN_PERSON_URN` |
| `reddit_publisher` | Subreddit posts | `REDDIT_CLIENT_ID/SECRET/USERNAME/PASSWORD` |
| `devto` | Articles, stats | `DEVTO_API_KEY` |
| `medium` | Stories | `MEDIUM_INTEGRATION_TOKEN` |
| `convertkit` | Subscribers, broadcasts, tags | `CONVERTKIT_API_KEY` |
| `youtube` | Channel stats, video metadata | `YOUTUBE_API_KEY` |
| `stripe` | MRR, customers, revenue | `STRIPE_SECRET_KEY` (restricted, read-only) |
| `gumroad` | Sales, products, revenue | `GUMROAD_ACCESS_TOKEN` |
| `lemon_squeezy` | Subscriptions, orders, MRR | `LEMON_SQUEEZY_API_KEY` |
| `patreon` | Patrons, pledge sum | `PATREON_ACCESS_TOKEN` |
| `obsidian` | Read/write Obsidian vault notes | vault path in config |
| `gmail` | Email reading (used for verification) | Gmail OAuth credentials |
| `gcalendar` | Calendar events | Google OAuth |
| `gdrive` | Google Drive files | Google OAuth |
| `notion` | Notion pages | `NOTION_API_KEY` |
| `slack` | Slack messages | Slack OAuth |
| `hackernews` | HN top stories | none (public API) |
| `news_rss` | RSS feed reading | none |
| `weather` | Weather data | none |

---

## 15. Revenue Tracking

### Daily revenue snapshot

Every morning the agent saves a file to `~/second-brain/Income/Revenue/YYYY-MM-DD.md`:

```markdown
# Revenue — 2025-05-08

- Stripe MRR: $0.00
- Stripe today: $0.00
- Stripe new customers (7d): 0
- Gumroad today: $0.00
- Gumroad this month: $0.00
- Lemon Squeezy MRR: $0.00
- Lemon Squeezy active subscriptions: 0
- Patreon patrons: 0
- Patreon monthly: $0.00
```

### Revenue alerts

Automatic Telegram notifications fire when:
- **First sale ever** — any platform, any amount
- **Daily target hit** — when today's total crosses `REVENUE_DAILY_TARGET` (default $50)
- **MRR milestone** — at $10, $50, $100, $250, $500, $1k, $2.5k, $5k, $10k
- **Revenue drop** — if today is 30%+ below yesterday

To configure alerts, add to `cloud-keys.env`:
```bash
REVENUE_DAILY_TARGET=100.00
REVENUE_DROP_THRESHOLD_PCT=25
```

For Telegram alerts, you need the Telegram connector configured (ask the agent to set it up via `jarvis chat`).

### Pull a dashboard anytime

In chat:
> "Show me my analytics dashboard"

The agent calls `analytics_summary` and returns something like:

```
## Analytics Dashboard — 2025-05-08 07:14 UTC

### Revenue
| Platform    | Metric 1              | Metric 2              | Metric 3           |
|-------------|----------------------|----------------------|--------------------|
| Stripe      | MRR: $127.00         | Today: $12.00        | New customers: 3   |
| Gumroad     | All time: $843.00    | This month: $127.00  | Today: $12.00      |

### Audience
| Platform    | Metric 1              | Metric 2              | Metric 3           |
|-------------|----------------------|----------------------|--------------------|
| Beehiiv     | Subscribers: 1,247   | —                    | —                  |
| ConvertKit  | Subscribers: 893     | Broadcasts: 12       | —                  |
| YouTube     | Subscribers: 234     | Views: 18,402        | Videos: 47         |
```

---

## 16. Publishing Workflow

### The golden rule: draft → review → publish

The agent **never publishes automatically.** Everything goes to Obsidian first. This keeps you in control and within all platform terms of service.

### Typical daily workflow

```
7:00 AM  Agent runs automatically
7:20 AM  You check ~/second-brain/Content/ in Obsidian
7:30 AM  You read today's newsletter draft, make edits
8:00 AM  You tell the agent: "Publish today's newsletter to Beehiiv"
         Agent calls beehiiv_create_draft → you review in Beehiiv → press send
```

### Scheduling posts for later

Instead of publishing immediately, queue a post for the platform's peak time:

> "Schedule today's Twitter thread for the best time"

The agent calls `post_schedule(platform="twitter", tool_name="twitter_post_thread", tool_args={...})` and picks the next optimal slot (e.g. tomorrow 2 PM UTC). The operative agent fires it at that time.

### Cross-posting the same content

> "Take today's blog post and repurpose it for Dev.to, Medium, and LinkedIn"

The agent runs `content_repurpose` with the blog content and returns platform-adapted versions for each. Dev.to gets a technical framing, LinkedIn gets a professional tone, Medium gets a storytelling angle.

### Tracking your affiliate links

Every time you're about to publish something with a link:

> "Generate a tracked link for my Beehiiv signup page for the Twitter thread"

The agent calls `utm_link(url="https://yourpage.beehiiv.com/subscribe", platform="twitter", campaign="ai-automation")` and returns a UTM URL. Use that in your content so you know which posts are driving subscribers.

---

## 17. Troubleshooting

### "Ollama not found" or model pull fails

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Start it if not running
ollama serve

# Pull models manually
ollama pull qwen2.5:7b
```

### Agent doesn't remember previous sessions

Check your config has sessions set to not expire:

```toml
[sessions]
max_age_hours = 87600   # 10 years
```

And that the memory backend is set to `obsidian` or `sqlite` (not `memory` which is in-RAM only).

### Browser tools fail ("playwright not installed")

```bash
uv sync --extra browser
playwright install chromium
```

### `platform_signup` says CAPTCHA detected but I don't have a 2Captcha key

The browser window will stay open. Solve the CAPTCHA manually in the visible Chrome window, then tell the agent:

> "I solved the CAPTCHA, please continue the signup"

### API key saved but connector says "not connected"

Force a reload:
```bash
curl -X POST http://localhost:8000/v1/cloud/reload
```

Or restart the server: `jarvis serve`

### Desktop app ignores my config.toml

The app reads `~/.openjarvis/config.toml` at startup. Make sure:
1. The file exists at exactly that path
2. The `[intelligence]` section has `default_model` set
3. Cloud models end in `:cloud` (e.g. `deepseek-v4-pro:cloud`)

### Revenue alerts not sending to Telegram

1. Confirm the Telegram connector is configured (`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in cloud-keys.env)
2. Send a test: `jarvis chat` → "Send me a test Telegram message"

### The 7 AM job isn't running

Check the agent type is set correctly:
```toml
[agent]
default_agent = "operative"

[agent.schedule]
schedule_type  = "cron"
schedule_value = "0 7 * * *"
```

And that `jarvis serve` is running as a background service (not just the frontend).

---

## 18. Quick Reference Card

### First-time setup (30 minutes)

```bash
git clone https://github.com/open-jarvis/OpenJarvis.git && cd OpenJarvis
./scripts/quickstart.sh                          # installs everything, opens UI

bash scripts/setup_second_brain.sh ~/second-brain  # creates vault + copies config

uv sync --extra browser                          # enable browser automation
playwright install chromium

cp configs/personal/platform_setup.toml ~/.openjarvis/config.toml
jarvis serve                                     # start onboarding agent
# In chat: "Set up all my platforms"
```

### Start the passive income engine (2 minutes)

```bash
cp configs/personal/passive_income.toml ~/.openjarvis/config.toml
jarvis serve
# Runs automatically at 7 AM every day
# Test now: open chat → "Run the morning routine now"
```

### Daily commands (in chat)

```
"Show me my analytics dashboard"
"What's today's revenue?"
"Publish today's newsletter to Beehiiv"
"Schedule today's Twitter thread"
"Generate a tracked link for [url]"
"Find affiliate programs for [niche]"
"Repurpose today's blog post for LinkedIn and Dev.to"
"Check my revenue alerts"
```

### Key file locations

| File | Purpose |
|---|---|
| `~/.openjarvis/config.toml` | Active configuration |
| `~/.openjarvis/cloud-keys.env` | All API keys (never share this file) |
| `~/.openjarvis/memory.db` | SQLite memory database |
| `~/second-brain/Content/` | All draft content waiting for your review |
| `~/second-brain/Income/Revenue/` | Daily revenue snapshots |
| `~/second-brain/Income/Setup/onboarding-status.md` | Platform setup log |

### Income engine config files

| Config | Command |
|---|---|
| Passive income (7 AM daily) | `cp configs/personal/passive_income.toml ~/.openjarvis/config.toml` |
| Affiliate marketing (6 AM daily) | `cp configs/personal/affiliate_marketing.toml ~/.openjarvis/config.toml` |
| Platform onboarding (one-time) | `cp configs/personal/platform_setup.toml ~/.openjarvis/config.toml` |
| Personal second brain only | `cp configs/personal/second_brain.toml ~/.openjarvis/config.toml` |
