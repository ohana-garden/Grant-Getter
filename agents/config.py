"""Agent Configuration for Student Ambassador Platform.

Defines configuration classes and default settings for all agents
including the Ambassador, Scholarship Scout, Appeal Strategist, etc.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class ModelType(Enum):
    """Supported model types."""
    CLAUDE_SONNET_4 = "claude-sonnet-4-20250514"
    CLAUDE_HAIKU_4 = "claude-haiku-4-20250514"
    CLAUDE_OPUS_4 = "claude-opus-4-20250514"


class MemoryType(Enum):
    """Memory backend types."""
    GRAPHITI = "graphiti"
    IN_MEMORY = "in_memory"


@dataclass
class MemoryConfig:
    """Configuration for agent memory system."""
    memory_type: MemoryType = MemoryType.GRAPHITI
    backend: str = "falkordb"
    episodic: bool = True
    temporal: bool = True
    host: str = field(default_factory=lambda: os.getenv("FALKORDB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("FALKORDB_PORT", "6379")))


@dataclass
class ProactiveTrigger:
    """Configuration for a proactive trigger."""
    condition: str
    action: str
    priority: int = 1
    cooldown_minutes: int = 60


@dataclass
class AgentConfig:
    """Base configuration for all agents."""
    name: str
    model: ModelType
    fallback_model: Optional[ModelType] = None
    memory: Optional[MemoryConfig] = None
    tools: List[str] = field(default_factory=list)
    proactive_triggers: List[ProactiveTrigger] = field(default_factory=list)
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096


# =============================================================================
# Ambassador Agent Configuration
# =============================================================================

AMBASSADOR_SYSTEM_PROMPT = """You are a Student Ambassador - a friendly, knowledgeable guide helping
students navigate the college financial aid process. Your role is to:

1. Help students discover and apply for scholarships they're eligible for
2. Guide them through FAFSA and financial aid applications
3. Assist with financial aid appeals and negotiations
4. Track deadlines and send timely reminders
5. Celebrate wins and keep students motivated

You have access to:
- A knowledge graph of scholarships, schools, and success strategies
- Conversation history to maintain context
- Specialist agents for deep research (Scholarship Scout, Appeal Strategist, Deadline Sentinel)
- Tools for calculations, reminders, and document analysis

Guidelines:
- Be encouraging but honest about chances
- Always prioritize the student's best interests
- Never make promises about outcomes
- Protect student privacy - never share PII
- Use plain language, avoid jargon
- Break complex topics into manageable steps
- Celebrate every win, no matter how small

Remember: Many students are first-generation and may feel overwhelmed.
Be patient, supportive, and proactive in offering help."""


ambassador_config = AgentConfig(
    name="StudentAmbassador",
    model=ModelType.CLAUDE_SONNET_4,
    fallback_model=ModelType.CLAUDE_HAIKU_4,
    memory=MemoryConfig(
        memory_type=MemoryType.GRAPHITI,
        backend="falkordb",
        episodic=True,
        temporal=True,
    ),
    tools=[
        "scholarship_search",
        "deadline_check",
        "fafsa_lookup",
        "document_parse",
        "aid_calculator",
        "schedule_reminder",
        "web_research",
        "appeal_draft",
        "negotiation_coach",
        "win_card_generate",
        "debt_compare",
    ],
    proactive_triggers=[
        ProactiveTrigger(
            condition="deadline_within_days < 7",
            action="send_reminder",
            priority=2,
        ),
        ProactiveTrigger(
            condition="deadline_within_days < 1",
            action="send_urgent",
            priority=1,
        ),
        ProactiveTrigger(
            condition="new_scholarship_match",
            action="queue_conversation",
            priority=3,
        ),
        ProactiveTrigger(
            condition="days_since_interaction > 5",
            action="check_in",
            priority=4,
        ),
        ProactiveTrigger(
            condition="disbursement_detected",
            action="process_commission",
            priority=1,
        ),
    ],
    system_prompt=AMBASSADOR_SYSTEM_PROMPT,
    temperature=0.7,
    max_tokens=4096,
)


# =============================================================================
# Specialist Agent Configurations
# =============================================================================

scholarship_scout_config = AgentConfig(
    name="ScholarshipScout",
    model=ModelType.CLAUDE_HAIKU_4,  # Cost optimization for crawling
    tools=[
        "scholarship_db_search",
        "criteria_match",
        "legitimacy_verify",
        "deadline_track",
    ],
    system_prompt="""You are a Scholarship Scout - a specialized agent that searches for
and matches scholarships to student profiles. You work with anonymized data only.

Your responsibilities:
- Search scholarship databases continuously
- Match scholarships to anonymized student profiles
- Verify scholarship legitimacy
- Track deadlines and new opportunities

You never see personally identifiable information. All profiles are anonymized.""",
    temperature=0.3,  # More deterministic for search tasks
)


appeal_strategist_config = AgentConfig(
    name="AppealStrategist",
    model=ModelType.CLAUDE_SONNET_4,  # Needs reasoning capabilities
    tools=[
        "commons_query",
        "success_pattern_analyze",
        "letter_draft",
        "tactic_recommend",
    ],
    system_prompt="""You are an Appeal Strategist - a specialized agent that helps craft
effective financial aid appeals and negotiations.

Your responsibilities:
- Query the commons graph for school negotiation patterns
- Analyze what strategies have worked historically
- Draft appeal letters based on proven templates
- Recommend tactics based on school-specific behavior

You work with anonymized data. Never ask for or use PII.""",
    temperature=0.5,
)


deadline_sentinel_config = AgentConfig(
    name="DeadlineSentinel",
    model=ModelType.CLAUDE_HAIKU_4,
    tools=[
        "calendar_manage",
        "reminder_schedule",
        "deadline_scrape",
    ],
    system_prompt="""You are a Deadline Sentinel - the master keeper of all deadlines.

Your responsibilities:
- Maintain the master deadline calendar
- Scrape deadlines from scholarship and school websites
- Coordinate reminders across all student ambassadors
- Alert when deadlines are approaching""",
    temperature=0.2,  # Highly deterministic for deadline tracking
)


document_analyst_config = AgentConfig(
    name="DocumentAnalyst",
    model=ModelType.CLAUDE_SONNET_4,
    tools=[
        "pdf_parse",
        "award_letter_extract",
        "transcript_analyze",
        "completeness_validate",
    ],
    system_prompt="""You are a Document Analyst - you run on the user's device to
process sensitive documents without sending data to servers.

Your responsibilities:
- Parse PDF documents (award letters, transcripts)
- Extract key fields from award letters
- Analyze transcripts for GPA, courses
- Validate document completeness

CRITICAL: You run on-device. No document content ever leaves the device.""",
    temperature=0.1,  # Very deterministic for document extraction
)


# =============================================================================
# Configuration Registry
# =============================================================================

AGENT_CONFIGS: Dict[str, AgentConfig] = {
    "ambassador": ambassador_config,
    "scholarship_scout": scholarship_scout_config,
    "appeal_strategist": appeal_strategist_config,
    "deadline_sentinel": deadline_sentinel_config,
    "document_analyst": document_analyst_config,
}


def get_agent_config(agent_name: str) -> AgentConfig:
    """Get configuration for a specific agent."""
    if agent_name not in AGENT_CONFIGS:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(AGENT_CONFIGS.keys())}")
    return AGENT_CONFIGS[agent_name]


def get_model_name(model_type: ModelType) -> str:
    """Get the API model name string for a ModelType."""
    return model_type.value
