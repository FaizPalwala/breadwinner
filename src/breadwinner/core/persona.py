"""Persona and narrative controller."""

from pathlib import Path
from typing import Dict, Any, Optional
import yaml
from pydantic import BaseModel


class Persona(BaseModel):
    name: str
    slug: str
    description: str
    tone: str
    system_directives: str
    cover_letter_directives: str


class PersonaManager:
    """Manages loading and resolving narrative personas."""

    @classmethod
    def get_built_in_dir(cls) -> Path:
        return Path(__file__).parent.parent / "personas"

    @classmethod
    def get_user_dir(cls) -> Path:
        return Path("user_personas")

    @classmethod
    def load_persona(cls, persona_name: str, custom_dir: Optional[Path] = None) -> Persona:
        """Load persona by name (checking user_personas first, then built-in)."""
        # 1. If path directly given
        p_path = Path(persona_name)
        if p_path.is_file():
            return cls._load_file(p_path)

        # 2. Check custom dir if provided
        if custom_dir and (custom_dir / f"{persona_name}.yaml").is_file():
            return cls._load_file(custom_dir / f"{persona_name}.yaml")

        # 3. Check local user_personas directory
        user_file = cls.get_user_dir() / f"{persona_name}.yaml"
        if user_file.is_file():
            return cls._load_file(user_file)

        # 4. Check built-in personas
        built_in = cls.get_built_in_dir() / f"{persona_name}.yaml"
        if built_in.is_file():
            return cls._load_file(built_in)

        # Fallback aliases
        alias_map = {
            "tech": "tech_ai",
            "ai": "tech_ai",
            "sde": "tech_ai",
            "admin": "bridging_admin",
            "parttime": "bridging_admin",
            "service": "hospitality"
        }
        if persona_name in alias_map:
            return cls.load_persona(alias_map[persona_name], custom_dir)

        raise ValueError(f"Persona '{persona_name}' not found. Available: tech_ai, bridging_admin, hospitality")

    @classmethod
    def _load_file(cls, path: Path) -> Persona:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Persona(**data)

    @classmethod
    def list_personas(cls) -> Dict[str, str]:
        """Return dict of available personas (user custom personas override built-in)."""
        result = {}
        # Built-in first
        for p_file in cls.get_built_in_dir().glob("*.yaml"):
            try:
                p = cls._load_file(p_file)
                result[p.slug] = p.description
            except Exception:
                pass

        # User custom personas override or add
        if cls.get_user_dir().exists():
            for p_file in cls.get_user_dir().glob("*.yaml"):
                try:
                    p = cls._load_file(p_file)
                    result[p.slug] = f"{p.description} [bold green](Customized)[/bold green]"
                except Exception:
                    pass

        return result
