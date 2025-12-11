"""
Tests for Ambassador Agent - Story 2.1

Verifies:
- Agent can receive message and respond
- Agent has access to conversation history via Graphiti
- Agent can delegate to sub-agents
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, AsyncMock, patch


class TestAgentConfig:
    """Tests for agent configuration classes."""

    def test_model_type_enum(self):
        """Test ModelType enum values."""
        from agents.config import ModelType

        assert ModelType.CLAUDE_SONNET_4.value == "claude-sonnet-4-20250514"
        assert ModelType.CLAUDE_HAIKU_4.value == "claude-haiku-4-20250514"
        assert ModelType.CLAUDE_OPUS_4.value == "claude-opus-4-20250514"

    def test_memory_type_enum(self):
        """Test MemoryType enum values."""
        from agents.config import MemoryType

        assert MemoryType.GRAPHITI.value == "graphiti"
        assert MemoryType.IN_MEMORY.value == "in_memory"

    def test_memory_config_defaults(self):
        """Test MemoryConfig default values."""
        from agents.config import MemoryConfig, MemoryType

        config = MemoryConfig()
        assert config.memory_type == MemoryType.GRAPHITI
        assert config.backend == "falkordb"
        assert config.episodic is True
        assert config.temporal is True
        assert config.host == "localhost"
        assert config.port == 6379

    def test_proactive_trigger(self):
        """Test ProactiveTrigger dataclass."""
        from agents.config import ProactiveTrigger

        trigger = ProactiveTrigger(
            condition="deadline_within_days < 7",
            action="send_reminder",
            priority=2,
        )
        assert trigger.condition == "deadline_within_days < 7"
        assert trigger.action == "send_reminder"
        assert trigger.priority == 2
        assert trigger.cooldown_minutes == 60  # default

    def test_agent_config(self):
        """Test AgentConfig dataclass."""
        from agents.config import AgentConfig, ModelType

        config = AgentConfig(
            name="TestAgent",
            model=ModelType.CLAUDE_SONNET_4,
        )
        assert config.name == "TestAgent"
        assert config.model == ModelType.CLAUDE_SONNET_4
        assert config.fallback_model is None
        assert config.tools == []
        assert config.temperature == 0.7
        assert config.max_tokens == 4096


class TestAmbassadorConfig:
    """Tests for the ambassador agent configuration."""

    def test_ambassador_config_exists(self):
        """Test ambassador config is defined."""
        from agents.config import ambassador_config

        assert ambassador_config is not None
        assert ambassador_config.name == "StudentAmbassador"

    def test_ambassador_uses_sonnet_4(self):
        """Test ambassador uses Claude Sonnet 4."""
        from agents.config import ambassador_config, ModelType

        assert ambassador_config.model == ModelType.CLAUDE_SONNET_4

    def test_ambassador_has_haiku_fallback(self):
        """Test ambassador has Haiku 4 fallback."""
        from agents.config import ambassador_config, ModelType

        assert ambassador_config.fallback_model == ModelType.CLAUDE_HAIKU_4

    def test_ambassador_has_graphiti_memory(self):
        """Test ambassador uses Graphiti memory."""
        from agents.config import ambassador_config, MemoryType

        assert ambassador_config.memory is not None
        assert ambassador_config.memory.memory_type == MemoryType.GRAPHITI
        assert ambassador_config.memory.backend == "falkordb"
        assert ambassador_config.memory.episodic is True
        assert ambassador_config.memory.temporal is True

    def test_ambassador_has_tools(self):
        """Test ambassador has required tools."""
        from agents.config import ambassador_config

        expected_tools = [
            "scholarship_search",
            "deadline_check",
            "aid_calculator",
            "schedule_reminder",
            "web_research",
        ]
        for tool in expected_tools:
            assert tool in ambassador_config.tools

    def test_ambassador_has_proactive_triggers(self):
        """Test ambassador has proactive triggers."""
        from agents.config import ambassador_config

        assert len(ambassador_config.proactive_triggers) > 0

        # Check specific triggers exist
        conditions = [t.condition for t in ambassador_config.proactive_triggers]
        assert "deadline_within_days < 7" in conditions
        assert "deadline_within_days < 1" in conditions
        assert "new_scholarship_match" in conditions
        assert "days_since_interaction > 5" in conditions

    def test_ambassador_has_system_prompt(self):
        """Test ambassador has a system prompt."""
        from agents.config import ambassador_config

        assert ambassador_config.system_prompt
        assert "Student Ambassador" in ambassador_config.system_prompt


class TestSpecialistConfigs:
    """Tests for specialist agent configurations."""

    def test_scholarship_scout_config(self):
        """Test scholarship scout configuration."""
        from agents.config import scholarship_scout_config, ModelType

        assert scholarship_scout_config.name == "ScholarshipScout"
        assert scholarship_scout_config.model == ModelType.CLAUDE_HAIKU_4
        assert "scholarship_db_search" in scholarship_scout_config.tools

    def test_appeal_strategist_config(self):
        """Test appeal strategist configuration."""
        from agents.config import appeal_strategist_config, ModelType

        assert appeal_strategist_config.name == "AppealStrategist"
        assert appeal_strategist_config.model == ModelType.CLAUDE_SONNET_4
        assert "commons_query" in appeal_strategist_config.tools

    def test_deadline_sentinel_config(self):
        """Test deadline sentinel configuration."""
        from agents.config import deadline_sentinel_config, ModelType

        assert deadline_sentinel_config.name == "DeadlineSentinel"
        assert deadline_sentinel_config.model == ModelType.CLAUDE_HAIKU_4
        assert "calendar_manage" in deadline_sentinel_config.tools

    def test_document_analyst_config(self):
        """Test document analyst configuration."""
        from agents.config import document_analyst_config, ModelType

        assert document_analyst_config.name == "DocumentAnalyst"
        assert document_analyst_config.model == ModelType.CLAUDE_SONNET_4
        assert "pdf_parse" in document_analyst_config.tools

    def test_all_configs_in_registry(self):
        """Test all configs are in the registry."""
        from agents.config import AGENT_CONFIGS

        expected = ["ambassador", "scholarship_scout", "appeal_strategist",
                    "deadline_sentinel", "document_analyst"]
        for name in expected:
            assert name in AGENT_CONFIGS


class TestGetModelName:
    """Tests for model name utility."""

    def test_get_model_name(self):
        """Test get_model_name function."""
        from agents.config import get_model_name, ModelType

        assert get_model_name(ModelType.CLAUDE_SONNET_4) == "claude-sonnet-4-20250514"
        assert get_model_name(ModelType.CLAUDE_HAIKU_4) == "claude-haiku-4-20250514"

    def test_get_agent_config(self):
        """Test get_agent_config function."""
        from agents.config import get_agent_config

        config = get_agent_config("ambassador")
        assert config.name == "StudentAmbassador"

    def test_get_agent_config_invalid(self):
        """Test get_agent_config with invalid name."""
        from agents.config import get_agent_config

        with pytest.raises(ValueError, match="Unknown agent"):
            get_agent_config("nonexistent_agent")


class TestMessageDataclass:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Test Message creation."""
        from agents.ambassador import Message

        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None
        assert msg.metadata == {}

    def test_message_with_metadata(self):
        """Test Message with metadata."""
        from agents.ambassador import Message

        msg = Message(
            role="assistant",
            content="Hi there!",
            metadata={"channel": "sms"}
        )
        assert msg.metadata["channel"] == "sms"


class TestAgentResponseDataclass:
    """Tests for AgentResponse dataclass."""

    def test_response_creation(self):
        """Test AgentResponse creation."""
        from agents.ambassador import AgentResponse

        resp = AgentResponse(content="Hello!")
        assert resp.content == "Hello!"
        assert resp.metadata == {}
        assert resp.delegated_to is None
        assert resp.tools_used == []

    def test_response_with_delegation(self):
        """Test AgentResponse with delegation."""
        from agents.ambassador import AgentResponse

        resp = AgentResponse(
            content="Here are your scholarships",
            delegated_to="scholarship_scout",
            tools_used=["scholarship_search"]
        )
        assert resp.delegated_to == "scholarship_scout"
        assert "scholarship_search" in resp.tools_used


class TestAmbassadorAgent:
    """Tests for AmbassadorAgent class."""

    @pytest.fixture
    def mock_graphiti(self):
        """Create mock Graphiti client."""
        mock = AsyncMock()
        mock.initialize.return_value = True
        mock.add_episode.return_value = "episode-123"
        mock.get_student_history.return_value = []
        return mock

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB client."""
        mock = MagicMock()
        mock.health_check.return_value = True
        return mock

    def test_agent_creation(self):
        """Test agent can be created."""
        from agents.ambassador import AmbassadorAgent
        from agents.config import ambassador_config

        agent = AmbassadorAgent()
        assert agent.config == ambassador_config
        assert agent.student_id is None
        assert agent._conversation_history == []

    def test_agent_with_student_id(self):
        """Test agent with student ID."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent(student_id="student_123")
        assert agent.student_id == "student_123"

    def test_agent_with_graphiti(self, mock_graphiti):
        """Test agent with Graphiti client."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent(graphiti_client=mock_graphiti)
        assert agent.graphiti == mock_graphiti

    def test_model_name_property(self):
        """Test model_name property."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()
        assert "claude-sonnet-4" in agent.model_name

    def test_fallback_model_name_property(self):
        """Test fallback_model_name property."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()
        assert "claude-haiku-4" in agent.fallback_model_name

    @pytest.mark.asyncio
    async def test_initialize(self, mock_graphiti):
        """Test agent initialization."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent(
            graphiti_client=mock_graphiti,
            student_id="student_123"
        )

        result = await agent.initialize()
        assert result is True
        mock_graphiti.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_records_history(self, mock_graphiti):
        """Test message processing records in history."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent(
            graphiti_client=mock_graphiti,
            student_id="student_123"
        )

        # Process a message (will use fallback response since no API key)
        response = await agent.process_message("Hello!")

        # Should have 2 messages: user + assistant
        assert len(agent._conversation_history) == 2
        assert agent._conversation_history[0].role == "user"
        assert agent._conversation_history[0].content == "Hello!"
        assert agent._conversation_history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_process_message_stores_episode(self, mock_graphiti):
        """Test message processing stores episode in Graphiti."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent(
            graphiti_client=mock_graphiti,
            student_id="student_123"
        )

        await agent.process_message("Hello!")

        # Should have called add_episode twice (user + assistant)
        assert mock_graphiti.add_episode.call_count == 2

    @pytest.mark.asyncio
    async def test_check_delegation_scholarship(self):
        """Test delegation detection for scholarship queries."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()

        result = await agent._check_delegation_needed("Find me scholarships for engineering")
        assert result == "scholarship_scout"

    @pytest.mark.asyncio
    async def test_check_delegation_appeal(self):
        """Test delegation detection for appeal queries."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()

        result = await agent._check_delegation_needed("I want to appeal my financial aid")
        assert result == "appeal_strategist"

    @pytest.mark.asyncio
    async def test_check_delegation_deadline(self):
        """Test delegation detection for deadline queries."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()

        result = await agent._check_delegation_needed("When is the FAFSA deadline?")
        assert result == "deadline_sentinel"

    @pytest.mark.asyncio
    async def test_check_delegation_document(self):
        """Test delegation detection for document queries."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()

        result = await agent._check_delegation_needed("Please parse my award letter")
        assert result == "document_analyst"

    @pytest.mark.asyncio
    async def test_check_delegation_none(self):
        """Test no delegation for general queries."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()

        result = await agent._check_delegation_needed("How are you today?")
        assert result is None

    def test_register_tool(self):
        """Test tool registration."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()

        async def mock_tool(query: str) -> str:
            return f"Result for {query}"

        agent.register_tool("scholarship_search", mock_tool)
        assert "scholarship_search" in agent._tools

    def test_get_conversation_history(self):
        """Test getting conversation history."""
        from agents.ambassador import AmbassadorAgent, Message

        agent = AmbassadorAgent()
        agent._conversation_history.append(Message(role="user", content="Test"))

        history = agent.get_conversation_history()
        assert len(history) == 1
        assert history[0].content == "Test"

        # Should be a copy, not the original
        history.append(Message(role="assistant", content="Response"))
        assert len(agent._conversation_history) == 1

    @pytest.mark.asyncio
    async def test_close(self):
        """Test agent cleanup."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()
        await agent.close()
        assert agent._sub_agents == {}

    @pytest.mark.asyncio
    async def test_check_triggers_empty(self):
        """Test trigger checking returns empty by default."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent()
        triggers = await agent.check_triggers()
        assert triggers == []


class TestGetAmbassador:
    """Tests for get_ambassador factory function."""

    @pytest.mark.asyncio
    async def test_get_ambassador_creates_agent(self):
        """Test get_ambassador creates new agent."""
        from agents.ambassador import get_ambassador

        mock_graphiti = AsyncMock()
        mock_graphiti.initialize.return_value = True
        mock_graphiti.get_student_history.return_value = []

        agent = await get_ambassador(
            student_id="student_123",
            graphiti_client=mock_graphiti,
        )

        assert agent is not None
        assert agent.student_id == "student_123"

    @pytest.mark.asyncio
    async def test_get_ambassador_initializes(self):
        """Test get_ambassador initializes the agent."""
        from agents.ambassador import get_ambassador

        mock_graphiti = AsyncMock()
        mock_graphiti.initialize.return_value = True
        mock_graphiti.get_student_history.return_value = []

        agent = await get_ambassador(
            student_id="student_456",
            graphiti_client=mock_graphiti,
        )

        mock_graphiti.initialize.assert_called_once()


class TestAcceptanceCriteria:
    """Tests verifying Story 2.1 acceptance criteria."""

    @pytest.mark.asyncio
    async def test_ac_agent_can_receive_message_and_respond(self):
        """AC: Agent can receive message and respond."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent(student_id="test_student")

        response = await agent.process_message("Hello, can you help me?")

        assert response is not None
        assert response.content != ""
        assert isinstance(response.content, str)

    @pytest.mark.asyncio
    async def test_ac_agent_has_graphiti_memory(self):
        """AC: Agent has access to conversation history via Graphiti."""
        from agents.ambassador import AmbassadorAgent
        from agents.config import ambassador_config, MemoryType

        # Verify config
        assert ambassador_config.memory.memory_type == MemoryType.GRAPHITI

        # Verify agent can use Graphiti
        mock_graphiti = AsyncMock()
        mock_graphiti.initialize.return_value = True
        mock_graphiti.get_student_history.return_value = [
            {"fact": "Previous conversation", "is_assistant": True}
        ]

        agent = AmbassadorAgent(
            graphiti_client=mock_graphiti,
            student_id="test_student"
        )

        await agent.initialize()
        await agent._load_conversation_history()

        # History should be loaded
        assert len(agent._conversation_history) > 0

    @pytest.mark.asyncio
    async def test_ac_agent_can_delegate_to_sub_agents(self):
        """AC: Agent can delegate to sub-agents."""
        from agents.ambassador import AmbassadorAgent

        agent = AmbassadorAgent(student_id="test_student")

        # Test delegation detection
        scholarship_delegation = await agent._check_delegation_needed(
            "Find me scholarships for computer science"
        )
        assert scholarship_delegation == "scholarship_scout"

        appeal_delegation = await agent._check_delegation_needed(
            "Help me appeal my financial aid award"
        )
        assert appeal_delegation == "appeal_strategist"

        deadline_delegation = await agent._check_delegation_needed(
            "What are my upcoming deadlines?"
        )
        assert deadline_delegation == "deadline_sentinel"


class TestModuleInit:
    """Tests for module initialization."""

    def test_agents_module_exports(self):
        """Test agents module exports required symbols."""
        from agents import AmbassadorAgent, get_ambassador, ambassador_config, AgentConfig

        assert AmbassadorAgent is not None
        assert get_ambassador is not None
        assert ambassador_config is not None
        assert AgentConfig is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
