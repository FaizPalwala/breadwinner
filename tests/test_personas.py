"""Unit tests for Persona management, starter template, and AI brain-dump synthesis."""

import pytest
from breadwinner.core.persona import (
    Persona,
    PersonaManager,
    synthesize_persona_from_braindump
)
from breadwinner.providers.factory import MockLLMProvider


def test_base_starter_persona():
    personas = PersonaManager.list_personas()
    assert "tech_ai" in personas

    # Built-in starter template
    starter_path = PersonaManager.get_built_in_dir() / "tech_ai.yaml"
    assert starter_path.is_file()
    p_builtin = PersonaManager._load_file(starter_path)
    assert p_builtin.slug == "tech_ai"
    assert "XYZ" in p_builtin.system_directives or "hard metrics" in p_builtin.system_directives.lower()
    assert p_builtin.market == "Global"
    assert len(p_builtin.banned_words) > 0

    # Test load_persona resolution
    p_tech = PersonaManager.load_persona("tech_ai")
    assert p_tech.slug == "tech_ai"

    # Test starter / default aliases
    p_starter = PersonaManager.load_persona("starter")
    assert p_starter.slug == "tech_ai"

    p_default = PersonaManager.load_persona("default")
    assert p_default.slug == "tech_ai"


def test_invalid_persona():
    with pytest.raises(ValueError):
        PersonaManager.load_persona("non_existent_persona_xyz")


def test_user_persona_override_or_built_in(tmp_path):
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


def test_synthesize_persona_from_braindump_mock_provider():
    mock = MockLLMProvider()
    braindump = (
        "Looking for high-scale backend platform roles in London or remote UK. "
        "British citizen, no visa sponsorship needed. Notice period is 1 month. "
        "Want authoritative systems-first tone emphasizing 1M QPS and zero downtime. "
        "Ban corporate fluff like spearheaded or synergy."
    )
    p = synthesize_persona_from_braindump(braindump, name_hint="London Platform Lead", provider=mock)
    assert isinstance(p, Persona)
    assert p.name == "London Platform Lead"
    assert p.market == "UK/EU"
    assert "visa_status" in p.logistics
    assert "notice_period" in p.logistics
    assert "spearheaded" in p.banned_words


def test_synthesize_persona_from_braindump_fallback_heuristic():
    braindump = (
        "Targeting senior platform engineer roles in London or remote UK. "
        "British citizen, no visa needed. 3 months notice. Minimum £115k base. "
        "Emphasize Go, Kubernetes, and high-throughput streaming."
    )
    p = synthesize_persona_from_braindump(braindump, name_hint="UK Senior Platform", provider=None)
    assert isinstance(p, Persona)
    assert p.slug == "uk_senior_platform"
    assert p.market == "UK/EU"
    assert "notice_period" in p.logistics
    assert "3 months" in p.logistics["notice_period"]
    assert "GOOGLE XYZ FORMULA" in p.system_directives


def test_save_and_load_synthesized_persona(tmp_path):
    p = Persona(
        name="Fintech Quant Lead",
        slug="fintech_quant_lead",
        description="For HFT and algorithmic trading",
        tone="Precise, quantitative",
        system_directives="XYZ formula",
        cover_letter_directives="3 paragraphs",
        market="UK/EU",
        logistics={"notice_period": "3 months"},
        archetype="Lead Systems Architect",
        banned_words=["spearheaded"]
    )
    saved = PersonaManager.save_persona(p, custom_dir=tmp_path)
    assert saved.exists()

    loaded = PersonaManager.load_persona("fintech_quant_lead", custom_dir=tmp_path)
    assert loaded.name == "Fintech Quant Lead"
    assert loaded.market == "UK/EU"
    assert loaded.logistics["notice_period"] == "3 months"

    # Delete
    deleted = PersonaManager.delete_persona("fintech_quant_lead", custom_dir=tmp_path)
    assert deleted is True
    assert not saved.exists()
