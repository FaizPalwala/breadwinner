# 🥖 Breadwinner
> **The Local-First, 8-Bit Career Engineering Studio & Anti-Hallucination Tailoring Engine.**  
> *Zero fabricated metrics. Zero keyword-stuffing slop. 100% private and offline on your machine.*

---

## What is Breadwinner?

Job hunting is broken by clinical automated slop and hallucination factories that invent experience you don't have. **Breadwinner** flips the script:

1. **Anti-Hallucination Invariant**: Every bullet point must trace back to verified facts in your local **Career Pantry**. We never invent skills, metrics, or company scale.
2. **Strict Metric Preservation**: If you scaled a service to `10M events` or reduced latency by `45%`, those numbers are sacred (Google XYZ formula).
3. **100% Local-First & Private (BYOK)**: Your resume, notes, and API keys stay on your hard drive. Run completely offline with local models (LM Studio, Ollama) or connect your own API key (Gemini, DeepSeek, Groq, OpenAI).
4. **Desktop-in-the-Terminal (8-Bit Bakery)**: An interactive retro terminal app with animated sprites, tactile hotkeys, and a zero-config setup wizard designed for non-technical and power users alike.

---

## Quick Start (30 Seconds)

### 1. Installation

<!-- tabs:start -->
#### **macOS / Linux**
```bash
git clone https://github.com/FaizPalwala/bread-winner.git
cd bread-winner

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
breadwinner
```

#### **Windows (PowerShell)**
```powershell
git clone https://github.com/FaizPalwala/bread-winner.git
cd bread-winner

# Option A: 1-Click Bootstrap
powershell -ExecutionPolicy Bypass -File install.ps1

# Option B: Manual Setup
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
.\breadwinner.bat
```
<!-- tabs:end -->

### 2. Launch the Studio

Just run:

```bash
# macOS / Linux
breadwinner

# Windows
.\breadwinner.bat
```

If it's your first time, the **Bakery Welcome Screen** will greet you:
- **Click "Load Demo Loaf 🥖"** to test drive the studio immediately with a pre-loaded engineering profile (zero configuration needed).
- Or **drag and drop** your existing `.pdf`, `.docx`, `.json`, or portfolio URL into the dough bin.

---

## Core Features & Workflow

### 1. The 8-Bit Bakery Studio (`breadwinner`)
```
┌────────────────────────────────────────────────────────────────────────┐
│ 🥖 BREADWINNER [Breadbox] [Studio] [Models] [Pantry]                   │
│ [✓ PANTRY] ──▶ [✓ KNEAD] ──▶  ▶ 🥖 PROOF ◀  ──▶ [♨️ OVEN] ──▶ [🍞 LOAF] │
├────────────────────────────────────────────────────────────────────────┤
│ ( 🍞 )  (♨️ OVEN)  🥖 THE OVEN: TAILOR STUDIO                          │
│ Crumb   Dome Hearth  Proofing verified bullets without keyword slop    │
├──────────────────────────────────┬─────────────────────────────────────┤
│ BULLET LABORATORY & ATS AUDIT    │ LIVE JAKE'S RESUME ATS PREVIEW      │
│ - Architected pipeline...        │ # Alex Baker                        │
│                                  │ Staff SRE • alex@breadwinner.dev    │
│ LIVE AUDIT GAUGES                │                                     │
│ • Google XYZ:    [████████░░░░]  │ Experience                          │
│ • Action Verbs:  [██████████░░]  │ Acme Corp - Senior SRE              │
│ • Fact Ground:   [████████████]  │ • Scaled cluster to 500 nodes...    │
│ • Bake Health:   [██████████░░]  │                                     │
├──────────────────────────────────┴─────────────────────────────────────┤
│ [q: Quit] [1-4: Tabs] [b: Bake PDF] [v: View PDF] [e: Fine-Tune] ...   │
└────────────────────────────────────────────────────────────────────────┘
```
- **Global Bakery Stepper**: Live tracking across the 5 pipeline stages (`Pantry` ➔ `Knead` ➔ `Proof` ➔ `Oven` ➔ `Golden Loaf`).
- **Animated Hearth & Crumb**: Non-blocking 8-bit sprites react as your resume proofs and bakes.
- **The Breadbox**: A complete job tracking dashboard with SQLite storage and bi-directional CSV sync.

### 2. Dual-Pane Bullet Laboratory (`e` Hotkey)
- **Split-View Editor**: Edit tailored experience bullets on the left while watching a real-time Markdown preview of your resume compile on the right.
- **4-Bar Google XYZ Telemetry Suite**:
  - `Google XYZ Compliance`: Quantified outcome density (`\b\d+%\b`, `p99 latency`, `\$10M`).
  - `Action Verb Velocity`: Density of high-impact leadership verbs (`Architected`, `Spearheaded`, `Engineered`).
  - `Pantry Fact Grounding`: Cross-references every bullet against your canonical pantry facts to ensure zero hallucinated skills.
  - `Bake Health Index`: Composite readiness score showing whether your draft is ready for the oven.
- **1-Click "Format All with XYZ"**: Detects unquantified bullets and automatically appends structured metric placeholders.

### 3. Native Headless Chromium PDF Baking (`b` Hotkey)
- Generates pixel-perfect, single-column A4 resumes (`resume.pdf`) conforming to the strict `r/EngineeringResumes` (Jake's Resume) gold standard.
- Uses your local Chrome, Brave, Edge, or Chromium browser in headless mode: **zero C-library dependencies** (no WeasyPrint or Cairo compilation headaches).
- Press `b` to bake; press `v` to view in your system PDF reader.

### 4. Career Curator (Anti-Context Bloat)
- Deep career profiles often exceed 1-page resume limits. Breadwinner's curator scores keywords, metric density, and recency to select the top-K relevant roles and projects for each target job.
- Guarantees your resume stays strictly within standard length limits without leaving out your biggest accomplishments.

### 5. Canonical Career Pantry (`pantry/`)
- Keeps your career history safe in local structured files:
  - `profile.json`: Verified work history, technologies, metrics, and education (JSON Resume standard).
  - `context.md`: Personal career directives, target salary, visa constraints, and qualitative goals.
  - `.history/`: Automated timestamped snapshots with 1-click rollback (`breadwinner pantry history`).
- Run **Baker's Interview** (`breadwinner pantry interview` or `m` in TUI) to discover and refine your narrative directives.

---

## Keyboard Hotkeys (Studio)

| Key | Action |
| :---: | :--- |
| `1` | Open **Breadbox** (Application Pipeline Tracker) |
| `2` | Open **The Oven** (Tailor Studio) |
| `3` | Open **Model Switcher** (Inspect active LLM & latency) |
| `4` | Open **Portfolio Pantry** (View verified profile facts) |
| `b` | **Bake ATS PDF** (`resume.pdf`) |
| `v` | **View PDF** in your default system reader |
| `e` | Open **Dual-Pane Bullet Laboratory** |
| `s` | Update application status (`applied`, `interviewing`, `offer`, `rejected`) |
| `y` | Sync pantry against upstream portfolio website |
| `i` | Import/Ingest from URL, file, or pasted bio |
| `m` | Run Baker's Interview |
| `h` | View snapshot history and rollback |
| `f` | Set priority flag (`high_priority`, `followup_needed`) |
| `o` | Open application folder in Finder / file manager |
| `r` | Refresh table and pantry data |
| `q` | Quit |

---

## CLI Usage (Power Users)

If you prefer scripting or using the terminal directly without the visual interface:

### Tailor an Application
```bash
# Interactive mode (prompts for strategy questions or persona)
breadwinner apply https://boards.greenhouse.io/monzo/jobs/123456

# Force target strategy discovery loop
breadwinner apply https://boards.greenhouse.io/monzo/jobs/123456 --strategy

# Fast path with preset persona
breadwinner apply https://boards.greenhouse.io/monzo/jobs/123456 --persona tech_ai --no-strategy
```

### Bake Resumes to PDF
```bash
# Bake current or selected job to resume.pdf
breadwinner bake

# Bake without opening PDF viewer
breadwinner bake --no-open
```

### Pantry Management
```bash
# View current pantry facts
breadwinner pantry show

# Ingest from file, URL, or resume
breadwinner pantry ingest ./my_resume.docx
breadwinner pantry ingest https://myportfolio.com

# Sync from linked portfolio
breadwinner pantry sync

# View history and rollback
breadwinner pantry history
breadwinner pantry revert <snapshot_id>
```

### Application Tracking
```bash
# View active jobs
breadwinner jobs

# Update status and notes
breadwinner status monzo-applied-ai interviewing -n "Round 1 scheduled"

# Flag a job with priority or custom labels
breadwinner flag monzo-applied-ai high_priority
```

### CLI Power Tools

Breadwinner includes a full suite of headless power tools for automation, inspection, and maintenance:

#### 1. Storage & Environment Map (`breadwinner where`)
Inspect your active paths, pantry directory, database location, applications folder, and LLM provider configuration:
```bash
breadwinner where
```

#### 2. Factory Reset & State Cleanup (`breadwinner reset`)
Selectively purge or reset local state while preserving your configured API keys:
```bash
# Reset specific components
breadwinner reset --pantry         # Clear profile.json, context.md, and snapshots
breadwinner reset --applications   # Delete all generated application folders
breadwinner reset --db             # Purge tracking SQLite database and CSV
breadwinner reset --personas       # Delete custom synthesized personas

# Complete fresh reset (preserves API keys in .env)
breadwinner reset --all

# Purge credentials too
breadwinner reset --all --keys
```

#### 3. Career Pantry Management (`breadwinner pantry`)
Manage your canonical verified facts, portfolio sync, and rollback snapshots:
```bash
# Inspect current derived facts and verified roles
breadwinner pantry show
# (or inspect job postings directly)
breadwinner job inspect https://boards.greenhouse.io/company/jobs/123

# Ingest from file (.docx, .pdf), portfolio URL, or pasted bio
breadwinner pantry ingest ./resume.pdf

# Interactive Baker's Interview to synthesize personal career directives
breadwinner pantry interview

# Bi-directional sync against live portfolio website or repo
breadwinner pantry sync

# View historical snapshot ledger
breadwinner pantry history

# Revert to a previous snapshot
breadwinner pantry revert <snapshot_id>
```

#### 4. Model Switching & Discovery (`breadwinner models` & `switch`)
Inspect available local and cloud LLM providers and switch active engines on the fly:
```bash
# Discover detected local models (Ollama, LM Studio) and cloud endpoints
breadwinner models

# Switch active provider and model
breadwinner switch lmstudio qwen2.5-coder-14b
breadwinner switch ollama llama3.2:latest
breadwinner switch gemini gemini-2.5-flash
breadwinner switch groq llama-3.3-70b-versatile
```

#### 5. Automated Job Link Health Check (`breadwinner check-links`)
Audit your tracked jobs to detect closed or expired postings across ATS portals:
```bash
breadwinner check-links
```

#### 6. Bidirectional SQLite <-> CSV Sync (`breadwinner sync`)
Export your SQLite application pipeline to a portable CSV, or import external sheets:
```bash
# Export tracker database to CSV
breadwinner sync --export-csv ./job_tracker.csv

# Import external jobs CSV into SQLite
breadwinner sync --import-csv ./targets.csv
```

#### 7. Recruiter Follow-ups & Priority Flags (`breadwinner followups` & `flag`)
Surface applications needing a follow-up and tag jobs with custom priority flags:
```bash
# Find applications submitted >= 7 days ago with no recruiter response
breadwinner followups --days 7

# Tag a target application with custom flags
breadwinner flag deliveroo-mle high_priority
breadwinner flag gitlab-backend referral

# Clear a flag
breadwinner flag deliveroo-mle
```

---

## AI Providers (BYOK or 100% Free Offline)

Configure your preferred engine in `.env`:

| Provider | Setting in `.env` | Cost | Privacy / Network |
| :--- | :--- | :--- | :--- |
| **LM Studio** | `BREADWINNER_LLM_PROVIDER=lmstudio` | **Free** | **100% Offline (Local hardware)** |
| **Ollama** | `BREADWINNER_LLM_PROVIDER=ollama` | **Free** | **100% Offline (Local hardware)** |
| **Google Gemini** | `BREADWINNER_LLM_PROVIDER=gemini`<br>`GEMINI_API_KEY=...` | Free tier available | Cloud API (BYOK) |
| **Groq Cloud** | `BREADWINNER_LLM_PROVIDER=groq`<br>`GROQ_API_KEY=...` | Free tier available | Cloud API (BYOK) |
| **DeepSeek** | `BREADWINNER_LLM_PROVIDER=deepseek`<br>`DEEPSEEK_API_KEY=...` | Low cost | Cloud API (BYOK) |
| **OpenAI** | `BREADWINNER_LLM_PROVIDER=openai`<br>`OPENAI_API_KEY=...` | Standard pricing | Cloud API (BYOK) |

---

## Security & Privacy Guarantee

- **Zero Telemetry**: Breadwinner sends zero usage data, analytics, or error logs to external servers.
- **Local Storage**: All resumes, pantry files, application notes, and database records remain strictly on your machine.
- **Git Isolation**: `.env`, `pantry/`, `applications/`, and `tracker.db` are permanently excluded by `.gitignore`.

---

## Testing

Run the full automated test suite:

```bash
pytest tests/ -v
```

All 64 tests pass with zero network dependencies.

---

## License

MIT License. Copyright (c) 2026 Faiz Palwala.
