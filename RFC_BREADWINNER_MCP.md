# RFC: Breadwinner Model Context Protocol (MCP) Server & Job Contract Architecture

**Status:** Draft / Review  
**Target Subsystem:** `breadwinner.mcp`, `breadwinner.core.contract`, `breadwinner.db`  
**Author:** Faiz Palwala & Jess (Executive OS)  
**Implementer Persona:** Barley (`ingestion-engine/.agents/BARLEY.md`)

---

## 1. Executive Summary & Root Cause Analysis

### 1.1 The Operational Bottleneck
Breadwinner was architected as a local-first career studio, pairing an interactive Textual Terminal UI (TUI) with a deterministic Python engine. While effective for standalone human operation, integrating Breadwinner into agentic workflows (e.g., Antigravity, Claude Desktop, Cursor) revealed critical operational friction:
1. **Interactive CLI Traps:** Commands like `breadwinner apply` enforce terminal interactive loops (strategy prompts, persona selectors) that hang or fail inside automated agent subshells.
2. **The Missing Persistence Bug:** While the TUI (`retro.py`) saved `job_description.txt` to the application directory, the CLI (`cli.py`) parsed jobs in-memory and **never wrote `job_description.txt` to disk**. This prevented any offline re-auditing or continuous scoring once the process exited.
3. **Rigid Storage Coupling:** The engine historically mandated that all applications live inside `~/.breadwinner/applications/YYYY-MM-DD_Company_Role/`. In real-world agent pairing, applications live directly in project workspaces (`applications/<company>/`), causing brittle file-copying routines and directory desynchronization.
4. **Naive Metric Scoring & Bullet Penalties:** Breadwinner's keyword and bullet evaluation relied on 1-page new-grad heuristics, penalizing experienced engineers who require 20+ comprehensive bullets to evidence distributed scale, cloud infrastructure, and team leadership.

### 1.2 The Solution
We propose four foundational architectural upgrades:
1. **The Persistent Job Contract (`job.json` & `job_description.txt`):** Fixed across CLI, TUI, and MCP. A standardized, persistent JSON contract created upon ingestion that formalizes deliverables, knockout criteria, and technical domain requirements.
2. **Decoupled Application Storage:** Breadwinner's SQLite database (`tracker.db`) stores arbitrary disk paths (`folder_path` and `contract_path`), allowing applications to live anywhere while remaining fully visible in Breadwinner's UI and tracker.
3. **The Breadwinner MCP Server (`breadwinner.mcp`):** A native Model Context Protocol server exposing Breadwinner's core as discrete, typed tools for ingestion, provenance auditing, visual baking, and state management.
4. **Domain Evidence Recall Metric Engine:** Eliminating false negatives by scoring domain coverage and role metric floors rather than raw word counts or arbitrary bullet limits.

---

## 2. Ingestion & The Job Contract (`job.json`)

### 2.1 The Two Ingestion Paths (Symmetric Contract)
Job ingestion must output identical persistent artifacts regardless of whether it was triggered by a human via URL or by an agent from a locked browser modal:

```
[ Public URL (Greenhouse, Ashby, Lever) ] ──► [ Breadwinner Ingestion Engine ] ──┐
                                                                                  ├──► 1. job_description.txt (Raw text)
[ Authenticated Modal (LinkedIn, Workday) ] ──► [ Agent / User DOM Extract ] ────┘    2. job.json (Machine contract)
```

Both paths write directly into the application folder:
- `job_description.txt`: The complete unformatted job text.
- `job.json`: The machine-readable evaluation contract.

### 2.2 Schema Definition (`job_contract.v1.json`)

```json
{
  "$schema": "https://breadwinner.tools/schemas/job_contract.v1.json",
  "metadata": {
    "company": "ASOS.com",
    "role": "Senior AI / LLM Engineer",
    "portal_type": "workday",
    "source_url": "https://asos.wd3.myworkdayjobs.com/...",
    "seniority_level": "senior",
    "page_budget": 2,
    "date_ingested": "2026-10-22T14:00:00Z"
  },
  "deliverables": {
    "resume": {
      "required": true,
      "template": "executive",
      "target_pages": 2
    },
    "cover_letter": {
      "status": "optional",
      "max_words": 180,
      "required_hooks": ["latency_optimization", "multi_agent_systems"]
    },
    "portfolio_dossier": {
      "required": false
    },
    "portal_questions": [
      {
        "id": "q_work_auth",
        "prompt": "Are you legally authorized to work in the UK?",
        "type": "boolean",
        "required": true
      },
      {
        "id": "q_accommodations",
        "prompt": "Do you require any reasonable adjustments during the interview process?",
        "type": "textarea",
        "required": false
      }
    ]
  },
  "evaluation_criteria": {
    "core_domains": [
      "Large Language Models (LLMs)",
      "Multi-Agent Orchestration",
      "Model Context Protocol (MCP)",
      "Python / PyTorch Systems",
      "Cloud Infrastructure (AWS/GCP)",
      "Distributed Microservices & Event Streaming"
    ],
    "essential_keywords": [
      "python", "pytorch", "llm", "rag", "mcp", "kafka", "redis", "fastapi"
    ],
    "preferred_keywords": [
      "apple mlx", "metal", "slurm", "snowflake", "graphql"
    ],
    "knockout_rules": {
      "min_experience_years": 4,
      "immediate_visa_sponsorship_needed": false,
      "degree_level": "msc_or_equivalent"
    }
  }
}
```

---

## 3. Database Schema Evolution (`tracker.db`)

### 3.1 Current Schema (Single Table)
Currently, `~/.breadwinner/tracker.db` consists of:

```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    location TEXT,
    portal_type TEXT,
    status TEXT NOT NULL,
    match_score INTEGER,
    persona TEXT,
    date_added TEXT NOT NULL,
    date_applied TEXT,
    folder_path TEXT,
    notes TEXT,
    flag TEXT
);
```

### 3.2 Schema Improvements & Field Rationale
1. **`match_score` -> `ats_score`:** 
   - Renaming `match_score` to `ats_score` (with backwards-compatible fallback) aligns the database schema with user-facing domain language.
2. **Why We Retain Both `date_added` and `date_applied`:**
   - `date_added`: The timestamp when the role is first targeted or tailored (`status: target | tailored`).
   - `date_applied`: The timestamp when the application is actually submitted (`status: applied`).
   - **Crucial CRM Mechanics:**
     - **Follow-up Reminders (`breadwinner followups`):** Must trigger $N$ days after `date_applied` (submission date), *not* `date_added`. If a job was tailored on Oct 1 and submitted on Oct 20, a 7-day follow-up reminder must fire on Oct 27, not Oct 8.
     - **Funnel Velocity Metrics:** Allows telemetry to measure pipeline conversion velocity (time from discovery to submission).
3. **Explicit Contract Pointer:**
   - Adding `contract_path TEXT` allows Breadwinner's UI and MCP to immediately resolve the contract without guessing subdirectories.

### 3.3 Database Migration Specification (`002_job_contracts_and_provenance.sql`)

```sql
ALTER TABLE jobs ADD COLUMN contract_path TEXT;
ALTER TABLE jobs ADD COLUMN ats_score INTEGER;
ALTER TABLE jobs ADD COLUMN xyz_score INTEGER;
ALTER TABLE jobs ADD COLUMN domain_recall_score INTEGER;
ALTER TABLE jobs ADD COLUMN provenance_status TEXT DEFAULT 'unverified';

-- Migrate existing match_score values into ats_score
UPDATE jobs SET ats_score = match_score WHERE ats_score IS NULL;
```

---

## 4. Re-Auditing & Rescoring Mechanics (No Network Round-Trips)

### 4.1 How Rescoring Actually Operates
When changes are made to a resume (whether in Breadwinner's TUI or via an agent in HTML), **Breadwinner never re-hits the remote job URL**.
1. **The Remote URL is Zero-State:** Job postings expire, get taken down, or require authentication. Hitting the network during re-baking creates flakiness and latency.
2. **Local Grounding:** Because `job_description.txt` and `job.json` are persisted in the application folder, the audit engine runs **100% locally and deterministically**.
3. **Instant Feedback Loop:**
   - User or Agent edits a bullet in `resume.html`.
   - `breadwinner_audit` reads the local `job.json` and candidate pantry.
   - Evaluates changes in < 50ms and returns the updated `ats_score` and `xyz_score`.

---

### 5. The 6-Pillar Metric Engine & Empirical ASOS Benchmark

### 5.1 Why the Legacy Metrics Produced False Negatives
An audit of Breadwinner's legacy scoring code (`density.py`, `curator.py`, `editor.py`) against real application assets revealed critical failure modes:
1. **Hardcoded Entity Blindspots:** `density.py` searched for a static 40-token list, scoring modern tools (`vLLM`, `Apple MLX`, `Metal`, `Triton`, `FastAPI`, `LangGraph`) as zero salience.
2. **Naive Stop-Word Stripping:** `curator.py` matched incidental non-technical words (`across`, `best`, `features`, `following`) as keyword hits.
3. **Regex Prefix Breakdown:** `editor.py` only evaluated the literal first word for action verbs. When bullets used bold topical lead-ins (e.g. `**Enterprise Platform Stabilization:** Directed...`), it evaluated `**Enterprise` as the verb and failed the check.
4. **Incidental Number Confusion:** Legacy regex counted calendar years (`2024`) and version strings (`Python 3.11`) as Google XYZ accomplishment metrics while missing structured domain evidence.

### 5.2 The Empirical ASOS Benchmark (Side-by-Side Validation)
Evaluating our tailored ASOS application (`applications/asos/resume.md`) across both systems demonstrated the dramatic shift in fidelity:

| Evaluation Dimension | Legacy Breadwinner System | Upgraded 6-Pillar Metric Engine | Root Cause / Operational Impact |
| :--- | :--- | :--- | :--- |
| **Overall Health Score** | **40% (Failing)** 🚨 | **89% (High-Tier Senior Pass)** ✅ | Legacy marked a high-density, production-grade senior resume as low-health fluff due to parsing bugs. |
| **Google XYZ Compliance** | **28%** (11/39 bullets) | **82.3%** (14/17 achievement bullets) | Legacy treated technical skill lists and degree lines as bullets; the new engine targets genuine accomplishment blocks. |
| **Action Verb Recognition** | **2%** (1 bullet found) | **94.1%** (16/17 bullets verified) | Legacy choked on bold category prefixes; new engine extracts semantic action verbs after lead-in tags. |
| **ATS / Technical Relevance**| **20.8% Overlap** (61/293 words)| **96% Domain Evidence Recall** (5/5 pillars) | Legacy counted junk words; new engine validates evidence across the 5 core ASOS JD technical domains. |
| **Provenance Verification** | **95% (Blind to institutions)**| **PASS (Binary 4-point gate)** | Legacy ignored school names; new engine runs hard validation on Universities, Employers, and Metrics. |
| **The "Page 1 Rule"** | **Unchecked (0)** | **68% of flagship metrics on Page 1** | Verifies 23M+ scale and core architecture sit in the top 60% of the document to grab skimming recruiters. |
| **Page Budget & Visual Fill** | **Unchecked (0)** | **Exactly 2 pages, ~82% Page 2 fill** | Verifies zero trailing lines, zero 1.1-page spillover, and clean structural margins. |

### 5.3 Specification of the 6 Diagnostic Pillars

```
┌────────────────────────────────────────────────────────────────────────┐
│                   BREADWINNER 6-PILLAR AUDIT ENGINE                     │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Immutable Truth & Provenance Gate   │ Binary (PASS / FAIL)          │
│    • University, Company, Metric Match │ Hard blocker for hallucination │
├────────────────────────────────────────────────────────────────────────┤
│ 2. Exact Title & Recruiter Search      │ 0 – 100 Score (Weight: 15%)   │
│    • Target title in header/summary    │ Workday/Greenhouse Boolean fit │
├────────────────────────────────────────────────────────────────────────┤
│ 3. Domain Evidence Recall              │ 0 – 100 Score (Weight: 35%)   │
│    • Coverage of JD technical pillars  │ Zero penalty for extra bullets │
├────────────────────────────────────────────────────────────────────────┤
│ 4. Google XYZ True-Impact Density      │ 0 – 100 Score (Weight: 30%)   │
│    • Scale, Latency, %, $ metrics only │ Rejects incidental numbers     │
├────────────────────────────────────────────────────────────────────────┤
│ 5. Information Hierarchy (Page 1 Rule) │ 0 – 100 Score (Weight: 20%)   │
│    • >= 65% of impact on Page 1        │ Front-loaded recruiter magnet  │
├────────────────────────────────────────────────────────────────────────┤
│ 6. ATS Structural Parseability         │ PASS / FAIL + Page Fill %     │
│    • Standard headers, date syntax     │ 75–90% Page 2 budget fill      │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Pillar 1: Immutable Truth & Provenance Gate (Binary PASS / FAIL):**
   - Strictly validates all degree-granting institutions against `_system/core_identity.md` (e.g. *University of Leeds*, *Vellore Institute of Technology*). Any foreign institution produces an immediate hard halt.
   - Validates all employers against the canonical pantry (*Deloitte Consulting*, *Gap Inc.*).
   - Validates metrics against the candidate fact ledger (`23M+`, `100+`, `75k`, `40%`, `90%+`).
   - Verifies zero banned buzzwords (`delve`, `spearheaded`, `tapestry`, `testament`).
2. **Pillar 2: Exact Title & Recruiter Search Alignment (0–100):**
   - Matches target job title from `job.json` (`metadata.role`) against the **Header / Title Subline** and **first 3 sentences of the Summary**.
   - Directly satisfies recruiter Boolean search filters on Workday, Greenhouse, and Ashby.
3. **Pillar 3: Domain Evidence Recall (0–100):**
   - Compares resume achievements against `evaluation_criteria.core_domains` in `job.json`.
   - Measures what percentage of target technical pillars have at least one verified evidence bullet. Extra bullets providing depth do not lower this score.
4. **Pillar 4: Google XYZ True-Impact Density (0–100):**
   - Isolates genuine accomplishment bullets from skill lists.
   - Filters out incidental numbers (years, version tags).
   - Validates true impact tokens: percentages (`%`), latency (`ms`), scale (`users`, `records`, `portraits`), throughput (`QPS`), and currency (`£`, `$`). Target: $\ge 75\%$ of bullets satisfy `[Accomplished X] as measured by [Y], by doing [Z]`.
5. **Pillar 5: Information Hierarchy & The "Page 1 Rule" (0–100):**
   - Parses document DOM to verify that at least **65% of high-impact metrics** and the candidate's highest-seniority commercial roles sit on **Page 1**.
6. **Pillar 6: ATS Structural Parseability & Page Budget Fill (Diagnostic):**
   - Validates standard section headings (`PROFESSIONAL SUMMARY`, `TECHNICAL SKILLS`, `WORK EXPERIENCE`, `EDUCATION`, `PROJECTS`).
   - Validates standard date formatting (`Mon YYYY – Mon YYYY`).
   - Measures rendered PDF page budget. If budget is 2 pages, verifies second page fills between **75% and 92%** (eliminating the "1.2-page orphan" trap).

---

## 6. The Three-Tier Pantry Architecture & Deep Dossier

### 6.1 Structure of the Canonical Pantry
The candidate's source of truth is partitioned into three distinct tiers:

```
~/.breadwinner/pantry/
├── 1. profile.yaml (Structured Fact Ledger)
│      └── Experiences, dates, institutions, verified bullets, metrics, awards.
│
├── 2. context.md (Narrative Ledger)
│      └── Operating texture, ADHD anchoring, voice preference, UK visa boundaries.
│
├── 3. dossier/ (Deep Knowledge Repository)
│      ├── architectures/ (e.g. mlx_ternary_kernel.md, graph_context_mcp.md)
│      ├── dissertations/ (e.g. sfhq_synthetic_data_unlearning_hpc.md)
│      └── essays_and_prs/ (e.g. escape_from_abi_hell.md, pytorch_pr_198776.md)
│
└── .history/ (Automated Rollback Snapshots)
       └── YYYYMMDD_HHMMSS_<trigger>_profile.yaml
```

### 6.2 Atomic Mutations & Automated Snapshots
Every programmatic mutation to the pantry via MCP is:
1. **Schema Validated:** Deserialized into Pydantic models before touching disk.
2. **Snapshot Protected:** Triggers `pantry.create_snapshot()` to copy the current state into `.history/` before applying any patch.
3. **Multi-Tier Synchronized:** Updating `profile.yaml` automatically keeps `profile.json` (JSON Resume standard) in parity.

---

## 7. Headless Visual Baking & Page Budget Diagnostics

### 7.1 Headless Chromium Printing
Breadwinner bakes print-ready PDFs by invoking headless Chromium (`chrome --headless=new --print-to-pdf=<pdf> file://<html_path>`).

### 7.2 The Diagnostic Compiler Feedback Loop
Instead of an opaque command, `breadwinner_bake_pdf` acts as an intelligent visual layout compiler:
1. Takes path to `resume.html`.
2. Compiles to PDF via headless Chromium.
3. Reads generated page metadata via `pypdf`.
4. Validates against `job.json` `metadata.page_budget` (e.g. exactly 2 pages).
5. Returns a structured diagnostic receipt:
   - If `pages == 2` with fill ratio $\ge 75\%$: Returns `status: "SUCCESS"`.
   - If `pages > 2`: Returns `status: "OVERFLOW"`, reporting exact overflow page count and layout advice (e.g. `overflow: document spilled onto page 3 by 6 lines; reduce section padding or tighten 1 bullet`).
   - If `pages == 2` with fill ratio $< 70\%$: Returns `status: "UNDERFILL"`, flagging an awkward trailing white space.

---

## 8. Separation of Concerns: Application Dossiers vs. Workspace Files

### 8.1 Ingestion Generates the Bridge
During ingestion, `breadwinner_ingest_job` hydrates:
- `job_description.txt`: Complete unformatted job text.
- `job.json`: Machine-readable evaluation contract.
- `portal_answers.md`: Quick-fill logistics (visa status, right to work, notice period, salary range, matched tech tags, and screening question stubs).

### 8.2 Zero Tool Bloat for Form Edits
Portal answers are **not** part of the resume evaluation metric system. Because applications live directly in the user's workspace (`applications/<company>/`), the agent and user can view and edit `portal_answers.md` directly using standard filesystem tools. No dedicated MCP editing tools are required for portal answers, eliminating unnecessary protocol overhead.

---

## 9. Breadwinner MCP Tool Suite Specification

The MCP server runs over STDIO via FastMCP. It exposes 8 focused, typed tools:

```
┌─────────────────────────────────────────────────────────────────┐
│                     BREADWINNER MCP TOOLS                       │
├─────────────────────────────────────────────────────────────────┤
│ 1. breadwinner_ingest_job                                       │
│    • Ingests URL or raw text -> writes job.json, JD & dossier   │
│                                                                 │
│ 2. breadwinner_audit                                            │
│    • 6-pillar evaluation of resume against job.json             │
│    • Returns provenance gate, domain recall, XYZ density        │
│                                                                 │
│ 3. breadwinner_tailor                                           │
│    • Automated generation of resume.html/md from pantry         │
│                                                                 │
│ 4. breadwinner_bake_pdf                                         │
│    • Headless Chromium PDF render with page budget audit        │
│                                                                 │
│ 5. breadwinner_track_job                                        │
│    • SQLite CRUD on tracker.db with folder_path pointers        │
│                                                                 │
│ 6. breadwinner_profile                                          │
│    • Surgical get/patch operations on canonical profile.yaml    │
│                                                                 │
│ 7. breadwinner_dossier                                          │
│    • List, read, and write deep knowledge docs in pantry/dossier│
│                                                                 │
│ 8. breadwinner_personas                                         │
│    • List, get, and register narrative tailoring personas       │
└─────────────────────────────────────────────────────────────────┘
```

### Tool 1: `breadwinner_ingest_job`
- **Arguments:**
  - `target_folder`: string (absolute path to application directory)
  - `source_type`: `"url"` | `"text"`
  - `payload`: string (URL or raw job text)
  - `company`?: string
  - `title`?: string
  - `portal_type`?: `"workday"` | `"greenhouse"` | `"lever"` | `"ashby"` | `"linkedin"` | `"general"`
- **Actions:** Writes `<target_folder>/job_description.txt`, `<target_folder>/job.json`, and `<target_folder>/portal_answers.md`. Returns the structured `JobContract`.

### Tool 2: `breadwinner_audit`
- **Arguments:**
  - `resume_path`: string (path to `resume.html` or `resume.md`)
  - `contract_path`: string (path to `job.json`)
- **Returns:**
  ```json
  {
    "provenance_gate": {
      "status": "PASS",
      "flagged_entities": [],
      "unverified_metrics": [],
      "banned_words_found": []
    },
    "ats_alignment": {
      "ats_score": 92,
      "exact_title_match": true,
      "domain_recall_score": 96,
      "matched_domains": ["Large Language Models", "Multi-Agent Orchestration", "Python/PyTorch", "Kafka/Microservices", "Inference Optimization"],
      "missing_domains": [],
      "missing_keywords": ["event-driven"]
    },
    "quality_metrics": {
      "total_achievement_bullets": 17,
      "xyz_compliant_bullets": 14,
      "xyz_score": 82.3,
      "page1_impact_ratio": 68.0
    },
    "page_budget": {
      "pages": 2,
      "fill_ratio": 0.82,
      "status": "OPTIMAL"
    },
    "recommendations": [
      "Add 'event-driven' keyword to SDE 1 microservices bullet to satisfy secondary JD keyword filter."
    ]
  }
  ```

### Tool 3: `breadwinner_tailor`
- **Arguments:**
  - `contract_path`: string
  - `target_folder`: string
  - `persona`?: string (`"tech_ai"`, `"oss_systems"`, `"backend_dist"`, `"bridging_ops"`)
  - `template`?: string (`"executive"`, `"jakes"`, `"modern"`)
  - `directives`?: string
- **Actions:** Writes `resume.md`, `resume.html`, and `cover_letter.md` directly into `target_folder`.

### Tool 4: `breadwinner_bake_pdf`
- **Arguments:**
  - `html_path`: string
  - `output_pdf_path`: string
  - `expected_page_count`?: integer (default: 2)
- **Returns:** Page count, byte size, fill ratio, and diagnostic status (`"SUCCESS"`, `"OVERFLOW"`, `"UNDERFILL"`).

### Tool 5: `breadwinner_track_job`
- **Arguments:**
  - `company`: string
  - `title`: string
  - `folder_path`: string
  - `contract_path`: string
  - `status`: `"target"` | `"tailored"` | `"applied"` | `"interviewing"` | `"offer"` | `"rejected"` | `"archived"`
  - `tier`?: `"canary"` | `"core"` | `"apex"`
  - `ats_score`?: integer
  - `xyz_score`?: integer
  - `notes`?: string
- **Actions:** Upserts record in `tracker.db` and syncs `job_tracker.csv`. Automatically manages `date_added` (on creation) and `date_applied` (when status transitions to `applied`).

### Tool 6: `breadwinner_profile`
- **Arguments:**
  - `action`: `"get"` | `"patch"`
  - `section`?: `"all"` | `"basics"` | `"experiences"` | `"projects"` | `"skills"` | `"education"` | `"awards"`
  - `operation`?: `"append"` | `"update_bullet"` | `"replace_entity"` | `"patch_basics"`
  - `payload`?: dict
- **Actions:** Reads or surgically mutates `profile.yaml`. Validates against Pydantic schema and automatically snapshots previous state to `~/.breadwinner/pantry/.history/`.

### Tool 7: `breadwinner_dossier`
- **Arguments:**
  - `action`: `"list"` | `"get"` | `"save"`
  - `rel_path`?: string
  - `content`?: string
- **Actions:** Lists, reads, or writes long-form technical teardowns and articles in `~/.breadwinner/pantry/dossier/` with automated snapshot creation.

### Tool 8: `breadwinner_personas`
- **Arguments:**
  - `action`: `"list"` | `"get"` | `"set"`
  - `slug`?: string
  - `persona_data`?: dict
- **Actions:** Exposes and manages tailoring personas stored in `~/.breadwinner/personas/<slug>.yaml`.

---

---

## 10. Cross-Platform Windows & Path Ingestion Invariant

### 10.1 The PowerShell Call Operator & Drag-and-Drop Failure
When users drag files into Windows PowerShell or paste paths with spaces, PowerShell formats the input using its execution call operator:
```powershell
& 'C:\Users\Asus\Documents\Resume_UK\Master CV.docx' 'ANJALI PARMAR_Updated.docx'
```
In `clean_user_input_path` (`ingestor.py:30`), the code stripped surrounding quotes (`'` and `"`), but left the leading `&` intact. Consequently, `Path("& 'C:\\...").exists()` returned `False`.

### 10.2 `shlex.split` POSIX Escaping & Windows Drive Letter Blindspot
Two further platform bugs crippled Windows ingestion:
1. **POSIX Escaping in `parse_dropped_sources` (`ingestor.py:1923`):** Running `shlex.split(raw_str)` under POSIX mode interprets backslashes `\` as escape characters. `C:\Users\Asus\Documents` had its slashes stripped, producing `C:UsersAsusDocuments` which does not exist on disk.
2. **POSIX-Biased Path Recognition (`ingestor.py:1925`):** The engine checked if paths start with Unix prefixes (`/`, `~`, `http://`), completely ignoring Windows drive letters (`C:\`, `D:\`).

### 10.3 The Silent Fallback Flaw
When file paths failed `.exists()` due to the above bugs, `discover_all_ingredients` (`discovery.py:164`) silently treated the entire string as user bio notes:
```
[X] Manual Notes / Bio (90 chars): "& 'c:\Users\Asus\Documents\Docum...'"
```
When baked, the LLM received a bundle of filenames rather than document text. Under the anti-hallucination invariant, the LLM correctly refused to synthesize content, outputting an empty profile.

### 10.4 The Windows Ingestion Fix Specification
Barley must implement four mandatory platform fixes:
1. **Sanitize PowerShell Call Operator:** `clean_user_input_path()` must strip leading `&`, whitespace, and PowerShell command prefixes before evaluating filesystem targets.
2. **Windows-Aware Path Splitting:** `parse_dropped_sources()` must run `shlex.split(raw_str, posix=False)` on Windows platforms or when Windows drive letters are detected.
3. **Windows Drive Letter Support:** Add regex `^[a-zA-Z]:[\\/]` and UNC prefix `\\\\` to all path validation checks.
4. **Explicit Path-Like Error Gate:** If an input matches file path characteristics (e.g. ends in `.docx`, `.pdf`, `.txt` or contains directory separators) but fails `.exists()`, Breadwinner **must never silently convert it to personal notes**. It must surface an explicit warning: `[MISSING FILE] Could not locate file at: <path>`.

### 10.5 Windows Root Launcher (`breadwinner.bat` & `install.ps1`)
To prevent the friction of typing `.\.venv\Scripts\breadwinner.exe`, the repository must include root native launchers:
- **`breadwinner.bat` (Root Launcher):**
  ```bat
  @echo off
  set "SCRIPT_DIR=%~dp0"
  if exist "%SCRIPT_DIR%.venv\Scripts\breadwinner.exe" (
      "%SCRIPT_DIR%.venv\Scripts\breadwinner.exe" %*
  ) else (
      echo Error: Virtual environment not found in %SCRIPT_DIR%.venv
      echo Run 'powershell -ExecutionPolicy Bypass -File install.ps1' to set up Breadwinner.
      exit /b 1
  )
  ```
- **`install.ps1` (1-Click Windows Bootstrap):**
  - Detects Python (`py -3.11`, `py -3.12`, or `python`).
  - Creates `.venv` and executes `pip install -e .`.
  - Optionally registers `%USERPROFILE%\.local\bin` or the repo root to User `PATH`.

---

## 11. Cross-Platform Documentation Standard (`README.md`)

All Breadwinner quickstart and operational documentation must feature dedicated, platform-separated tabs or blocks (macOS/Linux vs. Windows PowerShell):

### 11.1 Quickstart Matrix
```markdown
### Installation

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

py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
.\breadwinner.bat
```
<!-- tabs:end -->
```

---

## 12. Implementation Plan for Barley

### 12.1 Execution & Git Release Protocol
To maintain absolute stability and continuous delivery:
1. **Strictly Sequential Phases:** Barley must complete, test, and verify each phase before moving to the next.
2. **Deterministic Verification:** Every phase must pass existing and new test coverage (`pytest tests/ -v`).
3. **Continuous Release to `main`:** After each phase is verified, stage changes, commit with semantic conventional messages (e.g. `feat(contract): implement JobContract and disk persistence`), and push immediately to `origin/main`.

### 12.2 Phase Checklist

- [ ] **Phase 1: Bug Fix & Contract Persistence**
  - Fix `cli.py` to always persist `job_description.txt` and `portal_answers.md` alongside generated files.
  - Create `breadwinner.core.contract` defining the `JobContract` Pydantic model and serialization.
  - Test & push to `main`.

- [ ] **Phase 2: Database Migration**
  - Apply `002_job_contracts_and_provenance.sql` to `tracker.db`.
  - Update `JobRecord` in `src/breadwinner/db/repository.py` with `contract_path`, `ats_score`, `xyz_score`, and `date_applied` handling.
  - Test & push to `main`.

- [ ] **Phase 3: The 6-Pillar Metric Engine**
  - Implement Domain Evidence Recall, Page 1 Rule parsing, and true-impact metric filters in `src/breadwinner/core/curator.py` and `density.py`.
  - Upgrade `provenance.py` to enforce the binary institution and employer verification gate.
  - Test & push to `main`.

- [ ] **Phase 4: FastMCP Server**
  - Add `fastmcp` dependency to `pyproject.toml`.
  - Implement `src/breadwinner/mcp/server.py` exposing the 8 specified tools.
  - Expose 3-tier pantry management and persona tools.
  - Add `breadwinner mcp` command to CLI.
  - Test & push to `main`.

- [ ] **Phase 5: The Multi-Archetype Template Suite**
  - Add `src/breadwinner/templates/resume/executive.html.jinja2` for Mid-to-Senior Staff/Principal Engineers (Summary ➔ Skills ➔ Experience ➔ Projects/OSS ➔ Education ➔ Certifications).
  - Add `src/breadwinner/templates/resume/systems_research.html.jinja2` for ML Systems & Applied AI Researchers (Summary ➔ Research & Benchmarks ➔ Systems/OSS Frameworks ➔ Experience ➔ Education).
  - Add `src/breadwinner/templates/resume/compact_1page.html.jinja2` for early career and strict single-page constraints (Education ➔ Skills ➔ Experience ➔ Projects).
  - Add `src/breadwinner/templates/resume/consultant.html.jinja2` for technical consultants and fractional leads (Value Proposition ➔ Client Engagements & ROI ➔ Technical Architecture ➔ Education).
  - Register all templates in `TemplateRenderer` (`src/breadwinner/core/renderer.py`) and allow selection via CLI, TUI, and MCP.
  - Test & push to `main`.

- [ ] **Phase 6: Cross-Platform Windows Ingestion & Root Launchers**
  - Implement PowerShell prefix stripping (`&`) and `posix=False` Windows path splitting in `src/breadwinner/core/ingestor.py`.
  - Add drive-letter regex (`^[a-zA-Z]:[\\/]`) to `parse_dropped_sources`.
  - Add `[MISSING FILE]` warning gate in `src/breadwinner/ui/discovery.py` to prevent treating broken paths as personal notes.
  - Add `breadwinner.bat` and `install.ps1` to the project root.
  - Update `README.md` with side-by-side macOS/Linux and Windows PowerShell setup guides.
  - Test & push to `main`.



