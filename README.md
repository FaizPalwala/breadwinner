# Breadwinner

Breadwinner is a local-first, privacy-respecting CLI tool and terminal UI for ingesting job descriptions, matching them against a verified portfolio source of truth, and generating ATS-aligned resumes, cover letters, and portal application responses. It operates with fully local LLMs (LM Studio, Ollama) or hosted AI providers (DeepSeek, Google Gemini, Groq, OpenAI) using Bring-Your-Own-Key (BYOK).

---

## Key Features

1. **Canonical Career Pantry**: Decouples external portfolio websites from your permanent, verified knowledge base stored in `pantry/` (`profile.json` JSON Resume standard + `context.md` qualitative career guardrails). Supports universal ingestion from live portfolios, resumes (`.docx`, `.pdf`, `.json`), or raw text bios.
2. **Interactive Baker's Interview**: Discovers qualitative boundaries, visa statuses, target compensation, and priority narratives through a guided conversation loop, synthesizing them into permanent directives.
3. **Two-Way Upstream Sync & Diff**: Link your Pantry to an upstream website or portfolio, detect remote updates, inspect side-by-side diffs, and merge changes with automated snapshot rollbacks.
4. **Target Strategy Discovery Loop**: Probes role-specific strategic hooks, key superpower proof points, and tactical framing for each target role, injecting high-priority directives directly into the tailoring engine.
5. **Dynamic Persona Synthesis & Management**: Synthesize customized, reusable narrative personas on-the-fly from the strategy loop, or manage custom presets interactively via `breadwinner personas create/view/delete`.
6. **Native Headless ATS PDF Baking**: Zero-dependency PDF export powered by headless Chromium/Chrome/Edge/Brave. Generates print-perfect A4 resumes (`resume.pdf`) conforming to the strict `r/EngineeringResumes` (Jake's Resume) standard.
7. **Local-First & BYOK Architecture**: Run 100% locally with LM Studio or Ollama with zero data leaving your machine, or connect your own API keys for DeepSeek, Google Gemini, Groq, and OpenAI.
8. **Interactive Terminal UI**: Full keyboard-navigable terminal interface (`breadwinner ui`) built with Textual for managing your pipeline, tailoring applications, and managing your career pantry.
9. **Dual-Sync Application Tracker**: Stores job records in an SQLite database (`tracker.db`) with automatic bidirectional sync to CSV (`job_tracker.csv`).

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Career Pantry (pantry/)                           │
│  - profile.json (JSON Resume Standard Facts & Verified Metrics)        │
│  - context.md (Qualitative Directives, Guardrails & Preferences)       │
│  - .history/ (Automated Timestamped Snapshot DAG for Rollbacks)        │
│  - Universal Ingestor (.docx, .pdf, .json, URLs, Raw Bios)             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────┐        ┌─────────────────────────────────────┐
│  Job Ingestion          │        │ Target Strategy Discovery Loop      │
│  - URL Scraper          │───────▶│ - Role-Specific Hook & Alignment    │
│  - Text/File Parser     │        │ - Superpower Proof Point Discovery  │
│  - Portal Type Detect   │        │ - Tactical Framing & Gap Directives │
└───────────┬─────────────┘        └──────────────────┬──────────────────┘
            │                                         │
            └───────────────────┬─────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────┐
            │   Persona Controller & Synthesizer      │
            │   - Built-in (tech_ai, admin, service)  │
            │   - Custom Local (user_personas/*.yaml) │
            │   - Dynamic Persona Synthesis on-the-fly│
            └───────────────────┬─────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────┐
            │   Match & Keyword Gap Analyzer          │
            │   - Semantic & ATS overlap (0-100%)     │
            │   - Strict XYZ Metric Preservation      │
            └───────────────────┬─────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────┐
            │   LLM Provider Layer (Local & BYOK)     │
            │   - LM Studio / Ollama (100% Offline)   │
            │   - Google Gemini / Groq Cloud / DeepSeek│
            └───────────────────┬─────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────┐
            │   Template Rendering & Headless Baking  │
            │   - Jake's Resume (r/EngineeringResumes)│
            │   - Modern Clean HTML / Plain ATS MD    │
            │   - Native Chromium Headless PDF Export │
            └───────────────────┬─────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ resume.pdf    │       │ cover_letter  │       │ portal_answers│
│ (ATS PDF +    │       │ (Targeted 3-  │       │ (Screening    │
│  HTML & JSON) │       │  paragraph)   │       │  Questions)   │
└───────┬───────┘       └───────┬───────┘       └───────┬───────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                                ▼
            ┌─────────────────────────────────────────┐
            │   Dual-Sync Application Tracker         │
            │   - SQLite (tracker.db)                 │
            │   - CSV (job_tracker.csv)               │
            │   - Follow-up & Link Health Reminders   │
            └─────────────────────────────────────────┘
```

---

## Installation

```bash
git clone https://github.com/FaizPalwala/bread-winner.git
cd bread-winner

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```


### Quick Setup (60 Seconds)

If this is your first time using Breadwinner, run the interactive onboarding wizard:

```bash
breadwinner setup
```

The wizard will:
1. Detect or create your candidate portfolio (`./portfolio/resume.json`).
2. Guide you through selecting your preferred AI engine (Gemini, DeepSeek, local LM Studio, Groq, Ollama, or Mock).
3. Test connectivity and write `.env` with secure `0600` permissions.

Alternatively, you can manually copy `.env.example` to `.env`:

```bash
cp .env.example .env
chmod 600 .env  # Restrict permissions to owner only
```

Configure your preferred LLM provider in `.env`:
- **DeepSeek**: Set `BREADWINNER_LLM_PROVIDER=deepseek` and add `DEEPSEEK_API_KEY=...`.
- **Local LM Studio**: Run LM Studio local server on port 1234. Set `BREADWINNER_LLM_PROVIDER=lmstudio`.
- **Google Gemini**: Set `BREADWINNER_LLM_PROVIDER=gemini` and add `GEMINI_API_KEY=...`.
- **Groq Cloud**: Set `BREADWINNER_LLM_PROVIDER=groq` and add `GROQ_API_KEY=...`.
- **Local Ollama**: Start Ollama (`ollama serve`). Set `BREADWINNER_LLM_PROVIDER=ollama`.
- **Portfolio Path**: Set `PORTFOLIO_PATH=/path/to/portfolio`.

#### Zero-Cost Setup Options:
Breadwinner can be run completely free of charge:
- **100% Offline & Free**: Run local models via [LM Studio](https://lmstudio.ai/) or [Ollama](https://ollama.com/) with zero external network calls.
- **Free Developer Tiers**: Utilize free API developer keys from [Google AI Studio](https://aistudio.google.com/) (Gemini 2.5 Flash) or [Groq Cloud](https://console.groq.com/) (Llama 3.3, Qwen 2.5).


---

## Terminal UI (`breadwinner ui`)

Launch the interactive studio:

```bash
breadwinner ui
```

Or open directly with a target job URL preloaded:

```bash
breadwinner ui --url https://boards.greenhouse.io/monzo/jobs/123456
```

### Keyboard Navigation & Hotkeys:
- `1`: Pipeline Tracker (The Breadbox)
- `2`: Tailor Studio (The Oven)
- `3`: Model Switcher
- `4`: Portfolio Pantry (The Pantry)
- `e`: Fine-Tune tailored bullets interactively before baking
- `b`: Bake print-ready ATS PDF (`resume.pdf`)
- `v`: View baked PDF in default system viewer
- `i`: Ingest career background from URL, file, or text
- `m`: Baker's Interview loop (synthesize personal directives)
- `y`: Sync & diff against linked upstream portfolio
- `h`: Snapshot history & rollback modal
- `s`: Update job status modal (`applied`, `interviewing`, `offer`, `rejected`)
- `f`: Set/clear job flag (`high_priority`, `followup_needed`)
- `o`: Open application folder in Finder / file manager
- `r`: Refresh data
- `q`: Quit

---

## CLI Usage

### 1. Ingest and Tailor an Application

From a URL (interactive mode asks whether to run the Target Strategy Loop or pick an existing persona):
```bash
breadwinner apply https://boards.greenhouse.io/monzo/jobs/123456
```

Force role-specific discovery interview loop:
```bash
breadwinner apply https://boards.greenhouse.io/monzo/jobs/123456 --strategy
```

Fast path without prompts:
```bash
breadwinner apply https://boards.greenhouse.io/monzo/jobs/123456 --persona tech_ai --no-strategy
```

From raw text or markdown:
```bash
breadwinner apply ./job_description.txt \
  --company "Monzo" \
  --title "Machine Learning Engineer" \
  --persona tech_ai \
  --template jakes
```

This generates an application package in `applications/<date>_<company>_<role>/`:
- `resume.pdf`: Headless-rendered print ATS PDF ready for direct upload.
- `resume.html`: Printable single-column layout (1-page A4 print budget).
- `resume.md`: Clean ATS Markdown.
- `resume.json`: Standard JSON Resume schema.
- `cover_letter.md`: 3-paragraph targeted cover letter.
- `portal_answers.md`: Ready-to-copy responses for portal screening fields.

### 2. Direct ATS PDF Baking

Bake a print-ready PDF from an application folder, job ID, or the most recent job:

```bash
# Bake the latest tailored application and open it in preview
breadwinner bake

# Bake a specific folder without auto-opening
breadwinner bake ./applications/2026-09-24_Monzo_SeniorAppliedAIEngineer --no-open
```

### 3. Provider and Model Discovery

List online providers and discovered local/cloud models:
```bash
breadwinner models
```

Switch active provider and model:
```bash
breadwinner switch lmstudio qwen/qwen2.5-coder-14b
breadwinner switch gemini gemini-2.5-flash
breadwinner switch groq llama-3.3-70b-versatile
```

### 4. Application Pipeline Tracking

View active applications:
```bash
breadwinner track
breadwinner track --status interviewing
```

Update status or add notes:
```bash
breadwinner status monzo-senior-applied-ai-engineer interviewing --notes "Technical screen on Thursday"
```

Set flags:
```bash
breadwinner flag monzo-senior-applied-ai-engineer high_priority
```

Check link health:
```bash
breadwinner check-links
```

Find applications needing follow-up:
```bash
breadwinner followups --days 7
```

Sync SQLite database with CSV:
```bash
breadwinner sync --import-csv ./targets.csv
breadwinner sync --export-csv ./job_tracker.csv
```

### 5. Personas & Dynamic Strategy Synthesis

List all available built-in and user-custom personas:
```bash
breadwinner personas
breadwinner personas list
```

- `tech_ai`: Technical roles. Preserves systems metrics, backend architecture, and ML research background.
- `bridging_admin`: De-tunes technical jargon. Emphasizes operational organization, punctuality, and immediate availability.
- `hospitality`: Focuses on food hygiene, communication, and composure in fast-paced environments.

#### Manage & Create Custom Personas:
Create a new custom persona interactively:
```bash
breadwinner personas create
```

Inspect persona directives and tone:
```bash
breadwinner personas view fintech_quant
```

Delete a custom persona:
```bash
breadwinner personas delete fintech_quant
```

Custom personas are persisted to `user_personas/<slug>.yaml` (gitignored), ensuring your private metrics and prompt engineering stay local.


### 6. Career Pantry Management & Upstream Sync

Breadwinner maintains a canonical, versioned knowledge base of your verified career in `pantry/`:

```bash
# Inspect current Pantry facts and personal directives
breadwinner pantry show

# Ingest from a live portfolio URL, resume document (.docx, .pdf, .json), or raw bio
breadwinner pantry ingest https://yourname.com
breadwinner pantry ingest ./my_resume.docx

# Run the Baker's Interview to discover qualitative goals and guardrails
breadwinner pantry interview

# Sync and diff against your linked upstream portfolio (auto-detects additions/changes)
breadwinner pantry sync

# View historical snapshot timeline and rollback changes
breadwinner pantry history
breadwinner pantry revert <snapshot_id>
```

---

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Tests cover portfolio adapters, HTML scraping, persona validation, template rendering, SQLite/CSV synchronization, provider discovery, and headless UI widget mounting.

---

## Security & Credential Handling

Breadwinner is designed for complete privacy and local execution:

1. **Zero External Telemetry**: No analytics, usage metrics, or error reports are ever transmitted. The tool communicates only with the LLM endpoint you configure.
2. **Local Credential Storage**:
   - All API keys reside strictly in your local `.env` file or process environment variables.
   - `.env`, `.env.local`, `*.key`, and `*.pem` are excluded in `.gitignore` to eliminate git leakage risks.
   - Recommended POSIX file hardening: `chmod 600 .env` (restricts read/write access to your user account only).
   - Shell environment variable precedence: You can export keys directly in your terminal session (`export DEEPSEEK_API_KEY=...`) without saving them to disk.
3. **Air-Gapped & Offline Execution**:
   - When configured with `lmstudio` or `ollama`, the entire profile ingestion, keyword matching, and tailoring cycle executes 100% offline on your local hardware.
   - No resumes, portfolio data, or job descriptions leave your local machine.
4. **Data Isolation**:
   - Generated application packages (`./applications/`) and SQLite tracking databases (`./tracker.db`, `./job_tracker.csv`) remain strictly on local disk and are ignored by git.


---

## License

MIT License.
