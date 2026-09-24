"""Pantry: Canonical career knowledge base manager with versioning, diffing, and external sync."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from breadwinner.core.models import (
    CandidateProfile,
    WorkExperience,
    Education,
    Project,
    SkillCategory
)
from breadwinner.core.portfolio import JsonResumeAdapter
from breadwinner.core.ingestor import UniversalIngestor
from breadwinner.providers.base import BaseLLMProvider


class PantryManager:
    """Manages the candidate's canonical career context, snapshots, and two-way sync."""

    def __init__(self, pantry_dir: Optional[Path] = None):
        self.pantry_dir = Path(pantry_dir or "./pantry").resolve()
        self.profile_path = self.pantry_dir / "profile.json"
        self.context_path = self.pantry_dir / "context.md"
        self.source_path = self.pantry_dir / "source.json"
        self.history_dir = self.pantry_dir / ".history"

    def is_initialized(self) -> bool:
        """Check if Pantry has a valid canonical profile."""
        return self.profile_path.exists()

    def load_profile(self) -> CandidateProfile:
        """Load the canonical CandidateProfile from profile.json."""
        if not self.profile_path.exists():
            raise FileNotFoundError(f"Pantry profile.json not found in {self.pantry_dir}")

        data = json.loads(self.profile_path.read_text(encoding="utf-8"))
        adapter = JsonResumeAdapter(data)
        profile = adapter.load_profile()

        # Inject context.md into raw_context if present
        if self.context_path.exists():
            profile.raw_context["personal_context"] = self.context_path.read_text(encoding="utf-8")

        return profile

    def load_context(self) -> str:
        """Load qualitative personal context and guardrails."""
        if self.context_path.exists():
            return self.context_path.read_text(encoding="utf-8")
        return ""

    def load_source_metadata(self) -> Dict[str, Any]:
        """Load upstream linked source information (e.g. portfolio URL or path)."""
        if self.source_path.exists():
            try:
                return json.loads(self.source_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save_pantry(
        self,
        profile: CandidateProfile,
        context: Optional[str] = None,
        source_info: Optional[Dict[str, Any]] = None,
        trigger: str = "update"
    ) -> Path:
        """Save candidate profile, optional context, and create an automated rollback snapshot."""
        self.pantry_dir.mkdir(parents=True, exist_ok=True)

        # 1. Export JSON Resume
        json_data = profile.to_json_resume()
        self.profile_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

        # 2. Save context.md if provided
        if context is not None:
            self.context_path.write_text(context.strip() + "\n", encoding="utf-8")
        elif not self.context_path.exists():
            # Create starter context if none exists
            default_context = (
                "# Personal Directives & Guardrails\n\n"
                "## Target Roles & Preferences\n"
                "- Open to senior and staff level technical positions.\n\n"
                "## Work Boundaries & Logistics\n"
                "- Location: Hybrid or Remote.\n"
            )
            self.context_path.write_text(default_context, encoding="utf-8")

        # 3. Save source metadata if provided
        if source_info:
            source_info["last_updated"] = datetime.now().isoformat()
            self.source_path.write_text(json.dumps(source_info, indent=2), encoding="utf-8")

        # 4. Create snapshot
        self.create_snapshot(trigger=trigger)

        return self.pantry_dir

    def create_snapshot(self, trigger: str = "manual") -> str:
        """Create a timestamped historical snapshot for rollback and auditing."""
        self.history_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_trigger = "".join(c for c in trigger if c.isalnum() or c in "-_")
        snapshot_id = f"{timestamp}_{safe_trigger}"
        snap_dir = self.history_dir / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        if self.profile_path.exists():
            shutil.copy2(self.profile_path, snap_dir / "profile.json")
        if self.context_path.exists():
            shutil.copy2(self.context_path, snap_dir / "context.md")
        if self.source_path.exists():
            shutil.copy2(self.source_path, snap_dir / "source.json")

        meta = {
            "id": snapshot_id,
            "timestamp": timestamp,
            "trigger": trigger
        }
        (snap_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return snapshot_id

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots in reverse chronological order."""
        if not self.history_dir.exists():
            return []

        snapshots = []
        for snap_dir in sorted(self.history_dir.iterdir(), reverse=True):
            if snap_dir.is_dir() and (snap_dir / "meta.json").exists():
                try:
                    meta = json.loads((snap_dir / "meta.json").read_text(encoding="utf-8"))
                    snapshots.append(meta)
                except Exception:
                    pass
        return snapshots

    def revert_snapshot(self, snapshot_id: str) -> bool:
        """Revert the Pantry state to a specific historical snapshot."""
        snap_dir = self.history_dir / snapshot_id
        if not snap_dir.exists() or not (snap_dir / "profile.json").exists():
            return False

        # Create a pre-revert snapshot first so revert is itself reversible
        self.create_snapshot(trigger=f"pre_revert_from_{snapshot_id}")

        shutil.copy2(snap_dir / "profile.json", self.profile_path)
        if (snap_dir / "context.md").exists():
            shutil.copy2(snap_dir / "context.md", self.context_path)
        if (snap_dir / "source.json").exists():
            shutil.copy2(snap_dir / "source.json", self.source_path)

        return True

    def compute_diff(self, new_profile: CandidateProfile) -> Dict[str, Any]:
        """Compare a newly ingested profile against current canonical Pantry."""
        if not self.is_initialized():
            return {
                "is_new": True,
                "added_experiences": [e.company for e in new_profile.experiences],
                "added_projects": [p.name for p in new_profile.projects],
                "summary_changed": bool(new_profile.summary),
                "bullet_diffs": []
            }

        curr = self.load_profile()
        diff: Dict[str, Any] = {
            "is_new": False,
            "added_experiences": [],
            "modified_experiences": [],
            "added_projects": [],
            "summary_changed": curr.summary != new_profile.summary,
            "old_summary": curr.summary,
            "new_summary": new_profile.summary,
            "bullet_diffs": []
        }

        # Check experiences
        curr_comps = {e.company.lower(): e for e in curr.experiences}
        for n_exp in new_profile.experiences:
            c_key = n_exp.company.lower()
            if c_key not in curr_comps:
                diff["added_experiences"].append(f"{n_exp.role} @ {n_exp.company}")
            else:
                o_exp = curr_comps[c_key]
                # Check for new or changed bullets
                old_set = set(o_exp.bullets)
                new_bullets = [b for b in n_exp.bullets if b not in old_set]
                if new_bullets:
                    diff["modified_experiences"].append({
                        "company": n_exp.company,
                        "new_bullets": new_bullets
                    })

        # Check projects
        curr_projs = {p.name.lower() for p in curr.projects}
        for n_proj in new_profile.projects:
            if n_proj.name.lower() not in curr_projs:
                diff["added_projects"].append(n_proj.name)

        return diff

    def sync_from_linked_source(self, provider: BaseLLMProvider) -> Tuple[Dict[str, Any], CandidateProfile]:
        """Fetch upstream linked portfolio source (URL or directory), compute diff, and return new profile."""
        meta = self.load_source_metadata()
        source = meta.get("source")
        if not source:
            raise IngestionError("No upstream portfolio source linked. Use 'breadwinner pantry ingest' first.")

        # Ingest fresh copy
        new_profile = UniversalIngestor.ingest(source, provider)
        diff = self.compute_diff(new_profile)
        return diff, new_profile
