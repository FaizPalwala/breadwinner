# 🥖 BREADWINNER BETA TESTING GUIDE (v1.0-beta)

> **Welcome to the Breadwinner closed beta!**  
> Breadwinner is an anti-hallucination, local-first career engineering studio and application tailoring engine.  
> It compiles ATS-optimized resumes and application packages directly on your machine while strictly preserving your factual metrics (Google XYZ formula).

---

## 🚀 3-Minute Quickstart

### 1. Clone & Setup Environment
```bash
git clone -b release/beta-v1 https://github.com/FaizPalwala/ingestion-engine.git breadwinner
cd breadwinner

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure Your AI Provider
Copy the example environment configuration:
```bash
cp .env.example .env
```
Open `.env` in your editor and add your preferred API key (Gemini, OpenAI, DeepSeek, or Groq):
```ini
# Recommended default (fast & low latency):
BREADWINNER_LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here

# Or use OpenAI:
# BREADWINNER_LLM_PROVIDER=openai
# OPENAI_API_KEY=your_openai_api_key_here
```
*(You can also configure API keys dynamically inside the TUI studio by pressing `m` for the Model Switcher).*

---

## 📦 How to Ingest Career Data

Breadwinner builds your canonical **Career Pantry** from verified documents. You can initialize it in one of two ways:

1. **Drop your existing resume directly into pantry:**
   ```bash
   cp /path/to/my_resume.pdf pantry/resume.pdf
   ```
2. **Or run the universal ingest command:**
   ```bash
   breadwinner ingest --resume /path/to/my_resume.pdf
   ```
*(Supports `.pdf`, `.docx`, `.md`, `.json`, and live developer portfolio URLs).*

To inspect your extracted experience, metrics, and skill categories:
```bash
breadwinner pantry show
```

---

## ♨️ How to Tailor Applications

### Option A: The Interactive TUI Studio (Recommended)
Launch the 8-bit retro terminal workspace:
```bash
breadwinner
# or
breadwinner ui
```
- **Breadbox (`1`)**: Review your pipeline tracker and application status table. Select any row and press `e` to jump directly into the Studio Lab with live XYZ metric gauges.
- **Studio (`2`)**: Paste any target job link, choose your resume template (Jake's Resume / HTML / Markdown), and run the tailoring engine.
- **Pantry (`3`)**: Full local IDE for editing `profile.yaml`, `context.md`, and project dossiers.
- **Hotkeys**:
  - `e`: Open tailored application in Studio Bullet Lab
  - `b`: Bake ATS-optimized print-ready PDF via headless Chromium
  - `v`: View baked PDF in default system viewer
  - `s`: Cycle job status (`target` → `tailored` → `applied` → `interviewing` → `offer`)
  - `o`: Reveal application folder in Finder / file explorer
  - `m`: Model quick switcher
  - `q`: Quit

### Option B: Headless CLI Tailoring
If you prefer running from the command line without opening the TUI:
```bash
breadwinner tailor "https://jobs.lever.co/palantir/10dfc8bc-99ad-4ca2-ab76-853cb90a92c2"
```

---

## 🌐 Supported Job Boards

- **Native Direct Scraping**:
  - **Greenhouse**: `job-boards.greenhouse.io/...` or `boards.greenhouse.io/...`
  - **Ashby**: `jobs.ashbyhq.com/...`
  - **Lever**: `jobs.lever.co/...`
  - **Workable**: `apply.workable.com/...`
- **Protected / Anti-Bot Portals (LinkedIn, Workday, Indeed, SmartRecruiters)**:
  - If a job portal restricts scraping (HTTP 999/403/client-side SPA), Breadwinner will catch it gracefully and prompt you in the terminal to paste the raw job description text.
  - Simply paste the text and press **Enter** on an empty line (or Ctrl+D) to proceed.

---

## 🎯 The "Break-It" Focus for Beta Testers

We specifically want your feedback on the following three areas:

1. **Ingestion Fidelity & Mapping:**
   - Did it extract your specific resume format into `pantry/profile.json` accurately?
   - Did it preserve your job dates, company names, and project details without collapsing bullets into an unstructured block?
2. **Portal Variety & Edge Cases:**
   - Try pasting job links from companies you actually care about.
   - Did the parser strip boilerplates cleanly and extract technical requirements?
3. **Bullet Tone & Anti-Hallucination Audit:**
   - Review your generated bullets in `resume.md` / `resume.html`.
   - Do the bullets sound like authentic software engineering?
   - **Crucial check:** Did the engine invent any metrics, scale numbers, or tools that were not present in your career pantry?

---

## 🐛 How to Report Issues & Feedback

- File an issue on GitHub with the label `beta-feedback`:  
  👉 [https://github.com/FaizPalwala/ingestion-engine/issues](https://github.com/FaizPalwala/ingestion-engine/issues)
- Or contact Faiz directly with your feedback notes, screenshot, or sample job URL.
