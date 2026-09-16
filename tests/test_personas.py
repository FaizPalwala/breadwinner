"""Unit tests for persona management."""

import pytest
from breadwinner.core.persona import PersonaManager


def test_built_in_personas():
    personas = PersonaManager.list_personas()
    assert "tech_ai" in personas
    assert "bridging_admin" in personas
    assert "hospitality" in personas


def test_persona_loading():
    p_tech = PersonaManager.load_persona("tech_ai")
    assert p_tech.slug == "tech_ai"
    assert "XYZ" in p_tech.system_directives or "hard metrics" in p_tech.system_directives.lower()

    # Aliases
    p_admin = PersonaManager.load_persona("admin")
    assert p_admin.slug == "bridging_admin"

    p_serv = PersonaManager.load_persona("service")
    assert p_serv.slug == "hospitality"


def test_invalid_persona():
    with pytest.raises(ValueError):
        PersonaManager.load_persona("non_existent_persona_xyz")


def test_user_persona_override_or_built_in(tmp_path):
    # Test that custom directory overrides built-in persona
    custom_dir = tmp_path / "custom_personas"
    custom_dir.mkdir()
    custom_file = custom_dir / "tech_ai.yaml"
    custom_file.write_text(
        "name: Custom Engineer\nslug: tech_ai\ndescription: Custom\ntone: Direct\n"
        "system_directives: Custom directives\ncover_letter_directives: Custom letter\n"
    )

    loaded = PersonaManager.load_persona("tech_ai", custom_dir=custom_dir)
    assert loaded.name == "Custom Engineer"
    assert loaded.system_directives == "Custom directives"


