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
        from breadwinner.config import settings
        self.pantry_dir = Path(pantry_dir or settings.pantry_dir).resolve()
        self.profile_path = self.pantry_dir / "profile.json"
        self.profile_yaml_path = self.pantry_dir / "profile.yaml"
        self.context_path = self.pantry_dir / "context.md"
        self.source_path = self.pantry_dir / "source.json"
        self.dossier_dir = self.pantry_dir / "dossier"
        self.history_dir = self.pantry_dir / ".history"

    def clear(self) -> None:
        """Purge all stored profiles, context, source metadata, dossiers, and history."""
        for f in [self.profile_path, self.profile_yaml_path, self.context_path, self.source_path]:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass
        if self.history_dir.exists():
            shutil.rmtree(self.history_dir, ignore_errors=True)
        if self.dossier_dir.exists():
            shutil.rmtree(self.dossier_dir, ignore_errors=True)

    def is_initialized(self) -> bool:
        """Check if Pantry has a valid canonical profile."""
        return self.profile_path.exists() or self.profile_yaml_path.exists()

    def load_profile(self) -> CandidateProfile:
        """Load the canonical CandidateProfile from profile.json or profile.yaml."""
        if self.profile_path.exists():
            data = json.loads(self.profile_path.read_text(encoding="utf-8"))
            adapter = JsonResumeAdapter(data)
            profile = adapter.load_profile()
        elif self.profile_yaml_path.exists():
            profile = CandidateProfile.from_yaml(self.profile_yaml_path.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(f"Pantry profile.json not found in {self.pantry_dir}")

        # Inject context.md into raw_context if present
        if self.context_path.exists():
            profile.raw_context["personal_context"] = self.context_path.read_text(encoding="utf-8")

        return profile

    def load_profile_yaml(self) -> str:
        """Load clean YAML representation of the canonical profile."""
        if self.profile_yaml_path.exists():
            return self.profile_yaml_path.read_text(encoding="utf-8")
        if self.profile_path.exists():
            prof = self.load_profile()
            yaml_str = prof.to_yaml()
            self.profile_yaml_path.write_text(yaml_str, encoding="utf-8")
            return yaml_str
        return ""

    def save_profile_yaml(self, yaml_text: str, trigger: str = "yaml_save") -> CandidateProfile:
        """Validate, save YAML and sync canonical JSON Resume with snapshot protection."""
        new_profile = CandidateProfile.from_yaml(yaml_text)
        self.save_pantry(new_profile, trigger=trigger)
        return new_profile

    def list_dossier_files(self) -> List[Dict[str, Any]]:
        """List all deep knowledge dossier documents (dissertations, architectures, READMEs)."""
        if not self.dossier_dir.exists():
            return []

        files: List[Dict[str, Any]] = []
        for p in sorted(self.dossier_dir.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                rel = p.relative_to(self.dossier_dir)
                size_kb = round(p.stat().st_size / 1024, 1)
                title = p.stem.replace("_", " ").title()
                files.append({
                    "name": p.name,
                    "rel_path": str(rel),
                    "title": title,
                    "path": str(p),
                    "size_kb": size_kb,
                    "updated_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat()
                })
        return files

    def load_dossier_file(self, rel_path: str) -> str:
        """Read content of a deep dossier document."""
        target = (self.dossier_dir / rel_path).resolve()
        if not str(target).startswith(str(self.dossier_dir.resolve())):
            raise ValueError("Access outside dossier directory forbidden.")
        if not target.exists():
            raise FileNotFoundError(f"Dossier file not found: {rel_path}")
        return target.read_text(encoding="utf-8")

    def save_dossier_file(self, rel_path: str, content: str, trigger: str = "dossier_save") -> Path:
        """Write content to a deep dossier document with automated rollback snapshot."""
        self.dossier_dir.mkdir(parents=True, exist_ok=True)
        target = (self.dossier_dir / rel_path).resolve()
        if not str(target).startswith(str(self.dossier_dir.resolve())):
            raise ValueError("Access outside dossier directory forbidden.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.strip() + "\n", encoding="utf-8")
        self.create_snapshot(trigger=trigger)
        return target

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
        """Save candidate profile, optional context, sync YAML, and create an automated rollback snapshot."""
        self.pantry_dir.mkdir(parents=True, exist_ok=True)
        self.dossier_dir.mkdir(parents=True, exist_ok=True)

        # 1. Export JSON Resume
        json_data = profile.to_json_resume()
        self.profile_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

        # 2. Export clean YAML
        self.profile_yaml_path.write_text(profile.to_yaml(), encoding="utf-8")

        # 3. Save context.md if provided
        if context is not None:
            self.context_path.write_text(context.strip() + "\n", encoding="utf-8")
        elif not self.context_path.exists():
            # Create starter context if none exists (clean structure without fabricated PII or assumptions)
            default_context = (
                "# Personal Directives & Guardrails\n\n"
                "## Engineering Philosophy & Narrative\n"
                "(Document your core technical principles, career narrative, and domain strengths here)\n\n"
                "## Target Roles & Preferences\n"
                "(Specify target role scope and technical directions here)\n\n"
                "## Work Boundaries & Logistics\n"
                "(Specify work authorization, notice period, or location constraints here)\n"
            )
            self.context_path.write_text(default_context, encoding="utf-8")

        # 4. Save any dossier documents attached to raw_context
        dossier_docs = profile.raw_context.get("dossier_documents", {})
        if isinstance(dossier_docs, dict):
            for rel_path, doc_content in dossier_docs.items():
                try:
                    target = (self.dossier_dir / rel_path).resolve()
                    if str(target).startswith(str(self.dossier_dir.resolve())):
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(doc_content.strip() + "\n", encoding="utf-8")
                except Exception:
                    pass

        # 5. Save source metadata if provided
        if source_info:
            source_info["last_updated"] = datetime.now().isoformat()
            self.source_path.write_text(json.dumps(source_info, indent=2), encoding="utf-8")

        # 6. Create snapshot
        self.create_snapshot(trigger=trigger)

        return self.pantry_dir

    def create_snapshot(self, trigger: str = "manual") -> str:
        """Create a timestamped historical snapshot for rollback and auditing."""
        self.history_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S_%f")
        safe_trigger = "".join(c for c in trigger if c.isalnum() or c in "-_")
        snapshot_id = f"{timestamp}_{safe_trigger}"
        snap_dir = self.history_dir / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        if self.profile_path.exists():
            shutil.copy2(self.profile_path, snap_dir / "profile.json")
        if self.profile_yaml_path.exists():
            shutil.copy2(self.profile_yaml_path, snap_dir / "profile.yaml")
        if self.context_path.exists():
            shutil.copy2(self.context_path, snap_dir / "context.md")
        if self.source_path.exists():
            shutil.copy2(self.source_path, snap_dir / "source.json")
        if self.dossier_dir.exists():
            snap_dossier = snap_dir / "dossier"
            if snap_dossier.exists():
                shutil.rmtree(snap_dossier)
            shutil.copytree(self.dossier_dir, snap_dossier)

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
        for snap_dir in sorted(self.history_dir.iterdir(), key=lambda p: p.name, reverse=True):
            if snap_dir.is_dir() and (snap_dir / "meta.json").exists():
                try:
                    meta = json.loads((snap_dir / "meta.json").read_text(encoding="utf-8"))
                    snapshots.append(meta)
                except Exception:
                    pass
        # Ensure strict sort by timestamp descending
        snapshots.sort(key=lambda s: s.get("timestamp", s.get("id", "")), reverse=True)
        return snapshots

    def revert_snapshot(self, snapshot_id: str) -> bool:
        """Revert the Pantry state to a specific historical snapshot."""
        snap_dir = self.history_dir / snapshot_id
        if not snap_dir.exists() or not (snap_dir / "profile.json").exists():
            return False

        # Create a pre-revert snapshot first so revert is itself reversible
        self.create_snapshot(trigger=f"pre_revert_from_{snapshot_id}")

        shutil.copy2(snap_dir / "profile.json", self.profile_path)
        if (snap_dir / "profile.yaml").exists():
            shutil.copy2(snap_dir / "profile.yaml", self.profile_yaml_path)
        if (snap_dir / "context.md").exists():
            shutil.copy2(snap_dir / "context.md", self.context_path)
        if (snap_dir / "source.json").exists():
            shutil.copy2(snap_dir / "source.json", self.source_path)
        if (snap_dir / "dossier").exists():
            if self.dossier_dir.exists():
                shutil.rmtree(self.dossier_dir)
            shutil.copytree(snap_dir / "dossier", self.dossier_dir)

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
