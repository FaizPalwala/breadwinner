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


def test_application_class_personas():
    personas = PersonaManager.list_personas()
    assert "uk_eu_tech" in personas
    assert "india_tech" in personas
    assert "us_remote_c2c" in personas
    assert "staff_architect" in personas
    assert "founding_engineer" in personas

    p_uk = PersonaManager.load_persona("uk")
    assert p_uk.slug == "uk_eu_tech"
    assert p_uk.market == "UK/EU"
    assert "Right-to-Work" in str(p_uk.logistics)
    assert len(p_uk.banned_words) > 0

    p_in = PersonaManager.load_persona("india")
    assert p_in.slug == "india_tech"
    assert p_in.market == "India"
    assert "notice_period" in p_in.logistics

    p_c2c = PersonaManager.load_persona("c2c")
    assert p_c2c.slug == "us_remote_c2c"
    assert p_c2c.market == "US Remote / C2C"

    p_staff = PersonaManager.load_persona("staff")
    assert p_staff.slug == "staff_architect"
    assert p_staff.archetype == "Staff / Principal Systems Architect"

    p_founding = PersonaManager.load_persona("founding")
    assert p_founding.slug == "founding_engineer"
    assert "0-to-1" in p_founding.archetype


