# Breadwinner

Breadwinner is a CLI tool and terminal UI for ingesting job descriptions, matching them against a verified portfolio source of truth, and generating ATS-aligned resumes, cover letters, and portal application responses. It operates with free-tier cloud APIs (Google Gemini, Groq) or local LLMs via LM Studio and Ollama.

---

## Key Features

1. **Portfolio as Single Source of Truth**: Parses achievements, project case studies, and work history directly from an Astro/Keystatic portfolio, JSON Resume, or Markdown directory. Eliminates hallucinated experience by grounding generation strictly in verified facts and quantified metrics.
2. **Standard Resume Templates**: Includes single-column, ATS-parsable templates based on the `r/EngineeringResumes` standard (Jake's Resume), with strict XYZ metric structure (`Accomplished [X] as measured by [Y], by doing [Z]`).
3. **Free & Local LLM Support**: Works out of the box with LM Studio on Apple Silicon/PC (`http://localhost:1234/v1`), Google Gemini free/student tier, Groq, and Ollama.
4. **Narrative Personas**: Switch between technical roles (`tech_ai`), administrative/operations roles (`bridging_admin`), and service roles (`hospitality`).
5. **Interactive Terminal UI**: Full keyboard-navigable terminal interface (`breadwinner ui`) built with Textual for managing your application pipeline, tailoring new jobs, and switching models.
6. **Dual-Sync Application Tracker**: Stores job records in an SQLite database (`tracker.db`) with automatic bidirectional sync to CSV (`job_tracker.csv`).

---

## Architecture

```
                     ┌─────────────────────────────────────────────────────────┐
                     │   Profile Source Adapters                               │
                     │   ├── Astro/Keystatic (pages/about.astro, content/)     │
                     │   ├── JSON Resume (schema resume.json)                  │
                     │   └── Markdown Directory (experience.md, projects/)     │
                     └────────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
┌─────────────────────────┐        ┌─────────────────────────────┐
│  Job Ingestion          │        │ Profile Extraction          │
│  - URL Scraper          │        │ - Facts & Metrics           │
│  - Text/File Parser     │        │ - XYZ Formula Preservation  │
└───────────┬─────────────┘        └──────────────┬──────────────┘
            │                                     │
            └──────────────────┬──────────────────┘
                               │
                               ▼
            ┌───────────────────────────────────────┐
            │   Match & Keyword Gap Analyzer        │
            │   - Keyword overlap & gaps            │
            │   - Match score                       │
            └──────────────────┬────────────────────┘
                               │
                               ▼
            ┌───────────────────────────────────────┐
            │   Persona Controller                  │
            │   - tech_ai (scale & metrics)         │
            │   - bridging_admin (de-tuned)         │
            │   - hospitality (service)             │
            └──────────────────┬────────────────────┘
                               │
                               ▼
            ┌───────────────────────────────────────┐
            │   LLM Provider Layer                  │
            │   - LM Studio (local localhost:1234)  │
            │   - Google Gemini (free/student tier) │
            │   - Groq Cloud / Ollama               │
            └──────────────────┬────────────────────┘
                               │
                               ▼
            ┌───────────────────────────────────────┐
            │   Template Rendering (Jinja2)         │
            │   - jakes (single-column HTML/CSS)    │
            │   - modern (clean sans-serif)         │
            │   - ats (plain Markdown)              │
            │   - JSON Resume schema export         │
            └──────────────────┬────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│ Tailored CV   │      │ Cover Letter  │      │ Portal Q&A    │
│ (MD, HTML,    │      │ (3 paragraphs,│      │ (Greenhouse,  │
│  JSON Resume) │      │  proof points)│      │  Lever Q&A)   │
└───────┬───────┘      └───────┬───────┘      └───────┬───────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
                               ▼
            ┌───────────────────────────────────────┐
            │   Dual-Sync Application Tracker       │
            │   - SQLite (tracker.db)               │
            │   - CSV (job_tracker.csv)             │
            │   - Link health checks & follow-ups   │
            └───────────────────────────────────────┘
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


### Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your preferred LLM provider:
- **Local LM Studio**: Run LM Studio local server on port 1234. Set `BREADWINNER_LLM_PROVIDER=lmstudio`.
- **Google Gemini**: Set `BREADWINNER_LLM_PROVIDER=gemini` and add `GEMINI_API_KEY=...`.
- **Portfolio Path**: Set `PORTFOLIO_PATH=/path/to/portfolio`.

---

## Terminal UI (`breadwinner ui`)

Launch the interactive interface:

```bash
breadwinner ui
```

Or open directly with a target job URL preloaded:

```bash
breadwinner ui --url https://boards.greenhouse.io/monzo/jobs/123456
```

### Keyboard Navigation:
- `1`: Pipeline Tracker
- `2`: Tailor Studio
- `3`: Model Switcher
- `4`: Portfolio Profile
- `s`: Update job status modal (`applied`, `interviewing`, `offer`, `rejected`)
- `f`: Set/clear job flag (`high_priority`, `followup_needed`)
- `o`: Open application folder in file manager
- `r`: Refresh data
- `q`: Quit

---

## CLI Usage

### 1. Ingest and Tailor an Application

From a URL:
```bash
breadwinner apply https://boards.greenhouse.io/monzo/jobs/123456 --persona tech_ai
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
- `resume.html`: Printable single-column layout (1-page A4 print budget).
- `resume.md`: Clean Markdown.
- `resume.json`: Standard JSON Resume schema.
- `cover_letter.md`: 3-paragraph targeted cover letter.
- `portal_answers.md`: Ready-to-copy responses for portal screening fields.

### 2. Provider and Model Discovery

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

### 3. Application Pipeline Tracking

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

### 4. Personas & Custom Overrides

List available narrative personas:
```bash
breadwinner personas
```

- `tech_ai`: Technical roles. Preserves systems metrics, backend architecture, and ML research background.
- `bridging_admin`: De-tunes technical jargon. Emphasizes operational organization, punctuality, and immediate availability.
- `hospitality`: Focuses on food hygiene, communication, and composure in fast-paced environments.

#### Custom Private Personas:
To customize directives with your private metrics without committing them to git, create a `user_personas/` folder (gitignored):
```bash
mkdir -p user_personas
cp src/breadwinner/personas/tech_ai.yaml user_personas/tech_ai.yaml
```
`breadwinner` automatically loads `user_personas/<slug>.yaml` with priority over built-in templates.


---

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Tests cover portfolio adapters, HTML scraping, persona validation, template rendering, SQLite/CSV synchronization, provider discovery, and headless UI widget mounting.

---

## Security

- All API keys and environment variables are read from `.env`, which is ignored by git.
- Supports fully local execution with LM Studio or Ollama with zero external network traffic.
- Generated applications and candidate profiles remain in local storage.

---

## License

MIT License.
