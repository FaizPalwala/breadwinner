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

```bash
git clone https://github.com/FaizPalwala/bread-winner.git
cd bread-winner

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Launch the Studio

Just run:

```bash
breadwinner
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
│ • Action Verbs:  [██████████░░]  │ Acme Corp — Senior SRE              │
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
- Uses your local Chrome, Brave, Edge, or Chromium browser in headless mode—**zero C-library dependencies** (no WeasyPrint or Cairo compilation headaches).
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

# Flag a job
breadwinner flag monzo-applied-ai high_priority

# Export / Import tracker CSV
breadwinner sync --export-csv ./job_tracker.csv
breadwinner sync --import-csv ./targets.csv
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
