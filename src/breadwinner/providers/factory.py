"""Factory for resolving and instantiating the requested LLM provider."""

import json
from typing import Optional, Dict, Any

from breadwinner.config import settings
from breadwinner.providers.base import BaseLLMProvider
from breadwinner.providers.openai_compatible import OpenAICompatibleProvider
from breadwinner.providers.anthropic import AnthropicProvider


class MockLLMProvider(BaseLLMProvider):
    """Offline mock provider for testing and environments without an active API key."""

    def generate_text(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if "directive" in system_prompt.lower() or "narrative strategist" in system_prompt.lower():
            return (
                "- STRATEGIC HOOK: Lead with candidate's proven experience with scalable systems.\n"
                "- CORE PROOF POINT: Emphasize 1M QPS distributed cache and zero-downtime migrations.\n"
                "- TACTICAL FRAMING: Position candidate as a senior systems engineer."
            )
        return (
            "Dear Hiring Team,\n\n"
            "I am writing to express my strong interest in this role. With extensive engineering experience "
            "scaling distributed platforms in production and a solid foundation in computer science, "
            "I look forward to contributing to your team's technical goals.\n\n"
            "Sincerely,\nCandidate"
        )


    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        if "ingestion auditor" in system_prompt.lower() or "metric gaps" in system_prompt.lower() or "gap-filling" in system_prompt.lower() or "gap interview" in system_prompt.lower():
            return {
                "questions": [
                    {
                        "id": "gap_metric_scale",
                        "title": "Quantifying High-Throughput System Scale",
                        "prompt": "In your recent backend role, what were the peak QPS, data volumes, or latency metrics achieved?",
                        "placeholder": "e.g., Scaled ingest pipeline to 150k events/sec with sub-25ms p99 latency."
                    },
                    {
                        "id": "gap_architecture_tradeoffs",
                        "title": "Architectural Tradeoffs & System Decisions",
                        "prompt": "For your primary distributed project, what trade-offs were made between consistency, availability, and latency?",
                        "placeholder": "e.g., Chose Raft over Paxos for operational simplicity; accepted eventual consistency on read replicas."
                    },
                    {
                        "id": "gap_market_logistics",
                        "title": "Market Logistics & Work Boundaries",
                        "prompt": "What are your exact work authorization, notice period, and hybrid/remote constraints?",
                        "placeholder": "e.g., UK citizen, no sponsorship needed, 1-month notice period, remote or London hybrid."
                    }
                ]
            }

        if "strategy question" in system_prompt.lower() or "discovery question" in system_prompt.lower() or "tailoring problem-solver" in system_prompt.lower():
            return {
                "questions": [
                    {
                        "id": "hook",
                        "title": "Strategic Hook & Alignment",
                        "question": "What specific aspect of the company's product resonates with you?",
                        "placeholder": "e.g., Excited by real-time infrastructure..."
                    },
                    {
                        "id": "proof",
                        "title": "Primary Superpower & Proof Point",
                        "question": "Which past project best proves you are the ideal candidate?",
                        "placeholder": "e.g., Scaling high-throughput queue to 1M QPS..."
                    },
                    {
                        "id": "tactics",
                        "title": "Tactical Framing & Tone Nuances",
                        "question": "Are there specific skills or constraints to emphasize or downplay?",
                        "placeholder": "e.g., Emphasize systems architecture over frontend..."
                    }
                ]
            }

        if "deconstructor" in system_prompt.lower() or "job description deconstructor" in system_prompt.lower() or "technical entity extraction" in system_prompt.lower():
            return {
                "job_title": "Senior Platform Engineer",
                "company": "Cloud Corp",
                "domain": "Platform & Distributed Systems",
                "hard_must_haves": [
                    "5+ years backend engineering in Go or Python",
                    "Production Kubernetes and container orchestration experience",
                    "High-throughput event streaming with Kafka or RabbitMQ"
                ],
                "nice_to_haves": [
                    "Experience with eBPF or low-level Linux profiling",
                    "Terraform and multi-cloud infrastructure"
                ],
                "technical_stack": ["Go", "Python", "Kubernetes", "Docker", "Kafka", "AWS", "Redis"],
                "scale_constraints": ["1M QPS", "sub-10ms latency", "petabyte-scale data"],
                "core_responsibilities": [
                    "Architect and scale distributed event pipelines",
                    "Optimize platform latency and infrastructure resilience"
                ],
                "keywords": ["Go", "Kubernetes", "Kafka", "Docker", "Distributed Systems", "AWS"]
            }

        if ("career engineering compiler" not in system_prompt.lower() and "tailoring engine" not in system_prompt.lower()) and ("reusable narrative persona" in system_prompt.lower() or ("synthesize" in system_prompt.lower() and "persona" in system_prompt.lower()) or "persona architect" in system_prompt.lower()):
            return {
                "name": "Target Role Strategist",
                "slug": "target_role_strategist",
                "description": "Synthesized strategy for high-impact technical roles.",
                "market": "UK/EU",
                "logistics": {
                    "visa_status": "Citizen (No visa needed)",
                    "notice_period": "1 month",
                    "location": "London hybrid or Remote"
                },
                "archetype": "Senior Platform Engineer",
                "tone": "Authoritative, systems-first, quantitative.",
                "system_directives": "Focus on high throughput and reliable systems architecture.\nPRESERVE HARD METRICS.",
                "cover_letter_directives": "Lead with the engineering hook, provide two hard metrics, and close cleanly.",
                "banned_words": ["spearheaded", "synergy"]
            }

        if "project ingestion" in system_prompt.lower() or "project_name" in user_prompt:
            return {
                "project_name": "Breadwinner Ingestion Engine",
                "author_name": "Jane Doe",
                "author_title": "Staff Engineer",
                "summary": "High-throughput career knowledge compiler with two-ledger architecture.",
                "tech_stack": ["Python", "SQLite", "Textual"],
                "url": "https://github.com/example/engine",
                "github_url": "https://github.com/example/engine",
                "highlights": ["Zero data leakage", "Anti-hallucination metric preservation"],
                "deep_dossier_markdown": "# Project Deep Dive: Breadwinner Ingestion Engine\n\n## Architecture & System Design\nHigh-throughput two-ledger compiler with deterministic verification."
            }

        if "career engineering compiler" in system_prompt.lower() or "resume tailoring engine" in system_prompt.lower() or "tailor candidate work experience" in system_prompt.lower():
            return {
                "match_score": 88,
                "matched_skills": ["Python", "Java", "Distributed Systems", "Cloud", "Agile"],
                "missing_skills": ["Kafka", "GraphQL"],
                "rationale": "Candidate has strong engineering background matching 88% of core requirements.",
                "strategic_recommendations": [
                    "Highlight distributed systems and backend engineering experience.",
                    "Emphasize relevant technical projects and quantitative impact."
                ],
                "tailored_summary": (
                    "Software Engineer with experience architecting reliable distributed services and backend platforms. "
                    "Specializing in scalable architecture, data pipelines, and high availability."
                ),
                "tailored_bullets": [
                    "Delivered end-to-end platform features and resolved critical production incidents across release cycles.",
                    "Architected data remediation pipelines processing high-volume record ingestion with zero data loss.",
                    "Built distributed backend services maintaining high availability and extensive automated test coverage."
                ],
                "portal_answers": {
                    "why_us": "Your team's mission and engineering challenges align with my background in building resilient software systems.",
                    "challenge": "Architected an automated remediation workflow to resolve systemic validation errors, reducing failure backlog by 40%."
                }
            }

        if "data extractor" in system_prompt.lower() or "candidate portfolio" in system_prompt.lower() or "lead career architect" in system_prompt.lower() or "anti-hallucination compiler" in system_prompt.lower() or "full_name" in user_prompt:
            return {
                "full_name": "Jane Doe",
                "title": "Staff Engineer",
                "email": "jane.doe@example.com",
                "phone": "+1-555-0100",
                "location": "London, UK",
                "summary": "Experienced software architect specializing in distributed platforms.",
                "experiences": [
                    {
                        "company": "Cloud Corp",
                        "role": "Staff Engineer",
                        "start_date": "2021",
                        "end_date": "Present",
                        "bullets": [
                            "Architected distributed cache handling 1M QPS with sub-10ms latency."
                        ]
                    }
                ],
                "education": [
                    {
                        "degree": "B.Sc. Computer Science",
                        "institution": "University of London",
                        "graduation_year": "2020",
                        "coursework": ["Distributed Systems", "Algorithms"]
                    }
                ],
                "projects": [
                    {
                        "name": "High-Throughput Queue",
                        "description": "Distributed task queue in Go",
                        "tech_stack": ["Go", "Redis"],
                        "highlights": ["1M QPS throughput", "Zero packet loss"]
                    }
                ],
                "skills": [
                    {
                        "category": "Languages",
                        "skills": ["Go", "Python", "SQL"]
                    },
                    {
                        "category": "AI/ML & Research",
                        "skills": ["PyTorch"]
                    },
                    {
                        "category": "Backend & Distributed Systems",
                        "skills": ["Redis", "PostgreSQL"]
                    },
                    {
                        "category": "Cloud & Infrastructure",
                        "skills": ["Kubernetes", "Docker", "AWS"]
                    },
                    {
                        "category": "Frontend & Web",
                        "skills": ["React"]
                    }
                ],
                "context_diary": "# Personal Directives & Guardrails\n\n## Engineering Philosophy & Narrative\nHigh-performance systems engineering grounded in empirical benchmarks.\n\n## Technical Strengths & Focus Areas\n- Distributed caching\n- High throughput queues\n\n## Work Preferences & Boundary Directives\n- High autonomy and architectural ownership",
                "dossier_documents": {
                    "research_dissertation.md": "# Academic Research & Dissertation\n\n## Executive Summary\nDistributed systems architecture and fault tolerance.",
                    "engineering_voice_and_philosophy.md": "# Engineering Voice, Mental Models & Technical Philosophy\n\n## Systems Principles\nEmpirical benchmarks over marketing claims."
                }
            }

        return {
            "match_score": 88,
            "matched_skills": ["Python", "Java", "Distributed Systems", "Cloud", "Agile"],
            "missing_skills": ["Kafka", "GraphQL"],
            "rationale": "Candidate has strong engineering background matching 88% of core requirements.",
            "strategic_recommendations": [
                "Highlight distributed systems and backend engineering experience.",
                "Emphasize relevant technical projects and quantitative impact."
            ],
            "tailored_summary": (
                "Software Engineer with experience architecting reliable distributed services and backend platforms. "
                "Specializing in scalable architecture, data pipelines, and high availability."
            ),
            "tailored_bullets": [
                "Delivered end-to-end platform features and resolved critical production incidents across release cycles.",
                "Architected data remediation pipelines processing high-volume record ingestion with zero data loss.",
                "Built distributed backend services maintaining high availability and extensive automated test coverage."
            ],
            "portal_answers": {
                "why_us": "Your team's mission and engineering challenges align with my background in building resilient software systems.",
                "challenge": "Architected an automated remediation workflow to resolve systemic validation errors, reducing failure backlog by 40%."
            }
        }



def get_llm_provider(
    provider_name: Optional[str] = None,
    model_override: Optional[str] = None
) -> BaseLLMProvider:
    """Instantiate and return the configured LLM provider."""
    provider = (provider_name or settings.breadwinner_llm_provider).lower()

    if provider == "gemini":
        key = settings.gemini_api_key
        # Gemini provides standard OpenAI compatibility endpoint
        return OpenAICompatibleProvider(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=key or "missing-key",
            model=model_override or settings.gemini_model
        )

    elif provider == "lmstudio":
        return OpenAICompatibleProvider(
            base_url=settings.lmstudio_base_url,
            api_key="lm-studio",
            model=model_override or settings.lmstudio_model
        )

    elif provider == "groq":
        return OpenAICompatibleProvider(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.groq_api_key or "missing-key",
            model=model_override or settings.groq_model
        )

    elif provider == "ollama":
        return OpenAICompatibleProvider(
            base_url=settings.ollama_base_url,
            api_key="ollama",
            model=model_override or settings.ollama_model
        )

    elif provider == "openai":
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key or "missing-key",
            model=model_override or settings.openai_model
        )

    elif provider == "deepseek":
        return OpenAICompatibleProvider(
            base_url="https://api.deepseek.com",
            api_key=settings.deepseek_api_key or "missing-key",
            model=model_override or settings.deepseek_model
        )

    elif provider == "openrouter":
        return OpenAICompatibleProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key or "missing-key",
            model=model_override or settings.openrouter_model
        )

    elif provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key or "missing-key",
            model=model_override or settings.anthropic_model
        )

    elif provider == "mistral":
        return OpenAICompatibleProvider(
            base_url="https://api.mistral.ai/v1",
            api_key=settings.mistral_api_key or "missing-key",
            model=model_override or settings.mistral_model
        )

    elif provider == "mock":
        return MockLLMProvider()


    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
