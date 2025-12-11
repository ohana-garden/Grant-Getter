"""Ambassador Agent - Main student-facing agent.

The Ambassador Agent is the primary interface for students. It:
- Receives and responds to student messages
- Maintains conversation history via Graphiti
- Delegates to specialist agents when needed
- Triggers proactive outreach based on events
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass

from agents.config import (
    AgentConfig,
    ambassador_config,
    ModelType,
    MemoryType,
    ProactiveTrigger,
    get_model_name,
    AGENT_CONFIGS,
)

# Try to import Agent Zero - use mock if not available
try:
    from agent_zero import Agent, AgentContext
    AGENT_ZERO_AVAILABLE = True
except ImportError:
    AGENT_ZERO_AVAILABLE = False
    Agent = None
    AgentContext = None

# Try to import Anthropic client
try:
    from anthropic import Anthropic, AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None
    AsyncAnthropic = None

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A conversation message."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AgentResponse:
    """Response from the ambassador agent."""
    content: str
    metadata: Dict[str, Any] = None
    delegated_to: Optional[str] = None
    tools_used: List[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.tools_used is None:
            self.tools_used = []


class AmbassadorAgent:
    """Main ambassador agent for student interactions.

    The ambassador agent handles all direct student communication,
    maintains conversation history through Graphiti, and delegates
    to specialist agents when needed.
    """

    def __init__(
        self,
        config: AgentConfig = None,
        graphiti_client=None,
        falkordb_client=None,
        student_id: Optional[str] = None,
    ):
        """Initialize the ambassador agent.

        Args:
            config: Agent configuration (defaults to ambassador_config)
            graphiti_client: Graphiti client for temporal memory
            falkordb_client: FalkorDB client for commons queries
            student_id: ID of the student this agent serves
        """
        self.config = config or ambassador_config
        self.graphiti = graphiti_client
        self.falkordb = falkordb_client
        self.student_id = student_id

        # Conversation state
        self._conversation_history: List[Message] = []
        self._session_start = datetime.utcnow()

        # Model clients
        self._primary_client = None
        self._fallback_client = None

        # Tool registry
        self._tools: Dict[str, Callable] = {}

        # Sub-agent instances
        self._sub_agents: Dict[str, 'AmbassadorAgent'] = {}

        # Initialize clients if available
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize API clients for model access."""
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if ANTHROPIC_AVAILABLE and api_key:
            self._primary_client = AsyncAnthropic(api_key=api_key)
            if self.config.fallback_model:
                self._fallback_client = self._primary_client
            logger.info(f"Initialized Anthropic client for {self.config.name}")
        else:
            logger.warning(
                "Anthropic client not available. "
                "Set ANTHROPIC_API_KEY environment variable."
            )

    @property
    def model_name(self) -> str:
        """Get the primary model name."""
        return get_model_name(self.config.model)

    @property
    def fallback_model_name(self) -> Optional[str]:
        """Get the fallback model name."""
        if self.config.fallback_model:
            return get_model_name(self.config.fallback_model)
        return None

    async def initialize(self) -> bool:
        """Initialize the agent and its memory systems.

        Returns:
            True if initialization successful
        """
        try:
            # Initialize Graphiti if configured
            if self.graphiti and self.config.memory:
                if self.config.memory.memory_type == MemoryType.GRAPHITI:
                    await self.graphiti.initialize()
                    logger.info("Graphiti memory initialized")

            # Load conversation history for this student
            if self.student_id and self.graphiti:
                await self._load_conversation_history()

            return True
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}")
            return False

    async def _load_conversation_history(self):
        """Load recent conversation history from Graphiti."""
        if not self.graphiti or not self.student_id:
            return

        try:
            history = await self.graphiti.get_student_history(
                self.student_id,
                limit=50
            )

            # Convert to Message objects
            for entry in history:
                self._conversation_history.append(Message(
                    role="assistant" if entry.get('is_assistant') else "user",
                    content=entry.get('fact', ''),
                    timestamp=entry.get('valid_at'),
                    metadata={'source': 'history'}
                ))

            logger.info(f"Loaded {len(history)} history entries for student {self.student_id}")
        except Exception as e:
            logger.warning(f"Could not load conversation history: {e}")

    async def process_message(
        self,
        message: str,
        channel: str = "web",
        metadata: Dict[str, Any] = None,
    ) -> AgentResponse:
        """Process an incoming message and generate a response.

        Args:
            message: The user's message
            channel: Communication channel (web, sms, voice)
            metadata: Additional message metadata

        Returns:
            AgentResponse with the assistant's reply
        """
        metadata = metadata or {}

        # Record user message
        user_msg = Message(
            role="user",
            content=message,
            metadata={'channel': channel, **metadata}
        )
        self._conversation_history.append(user_msg)

        # Store in Graphiti if available
        if self.graphiti and self.student_id:
            await self._store_episode(user_msg, channel)

        # Generate response
        try:
            response = await self._generate_response(message, channel)
        except Exception as e:
            logger.error(f"Primary model failed: {e}")

            # Try fallback model
            if self.fallback_model_name:
                logger.info("Attempting fallback model...")
                response = await self._generate_response(
                    message, channel, use_fallback=True
                )
            else:
                raise

        # Record assistant response
        assistant_msg = Message(
            role="assistant",
            content=response.content,
            metadata={'channel': channel, 'tools_used': response.tools_used}
        )
        self._conversation_history.append(assistant_msg)

        # Store response in Graphiti
        if self.graphiti and self.student_id:
            await self._store_episode(assistant_msg, channel)

        return response

    async def _generate_response(
        self,
        message: str,
        channel: str,
        use_fallback: bool = False,
    ) -> AgentResponse:
        """Generate a response using the configured model.

        Args:
            message: User message to respond to
            channel: Communication channel
            use_fallback: Whether to use fallback model

        Returns:
            AgentResponse with generated content
        """
        model = self.fallback_model_name if use_fallback else self.model_name

        # Check for delegation needs
        delegation = await self._check_delegation_needed(message)
        if delegation:
            return await self._delegate_to_agent(delegation, message)

        # Build conversation context
        messages = self._build_messages_for_api()

        # Call model API if available
        if self._primary_client:
            try:
                response = await self._primary_client.messages.create(
                    model=model,
                    max_tokens=self.config.max_tokens,
                    system=self.config.system_prompt,
                    messages=messages,
                )

                content = response.content[0].text if response.content else ""

                return AgentResponse(
                    content=content,
                    metadata={
                        'model': model,
                        'channel': channel,
                        'tokens_used': response.usage.output_tokens if response.usage else 0,
                    }
                )
            except Exception as e:
                logger.error(f"API call failed: {e}")
                raise

        # Fallback response if no client available
        return AgentResponse(
            content=self._generate_fallback_response(message),
            metadata={'model': 'fallback', 'channel': channel}
        )

    def _build_messages_for_api(self) -> List[Dict[str, str]]:
        """Build message list for API call."""
        messages = []

        # Include recent conversation history
        recent_history = self._conversation_history[-20:]  # Last 20 messages

        for msg in recent_history:
            if msg.role in ("user", "assistant"):
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        return messages

    async def _check_delegation_needed(self, message: str) -> Optional[str]:
        """Check if message should be delegated to a specialist agent.

        Args:
            message: User message to analyze

        Returns:
            Agent name to delegate to, or None
        """
        message_lower = message.lower()

        # Simple keyword-based delegation (in production, use NLU)
        # Check for scholarship-related queries
        scholarship_keywords = [
            "find scholarship", "scholarship search", "match scholarship",
            "find me scholarship", "scholarships for", "scholarship match",
            "look for scholarship", "search scholarship"
        ]
        if any(kw in message_lower for kw in scholarship_keywords):
            return "scholarship_scout"

        # Check for appeal/negotiation queries
        appeal_keywords = [
            "appeal", "negotiate", "counter offer", "increase aid",
            "more money", "better offer", "financial aid appeal"
        ]
        if any(kw in message_lower for kw in appeal_keywords):
            return "appeal_strategist"

        # Check for deadline queries
        deadline_keywords = [
            "deadline", "due date", "when is", "calendar",
            "upcoming deadline", "dates for"
        ]
        if any(kw in message_lower for kw in deadline_keywords):
            return "deadline_sentinel"

        # Check for document processing queries
        document_keywords = [
            "upload document", "parse award", "read transcript",
            "parse my award", "analyze document", "award letter",
            "document analyst"
        ]
        if any(kw in message_lower for kw in document_keywords):
            return "document_analyst"

        return None

    async def _delegate_to_agent(
        self,
        agent_name: str,
        message: str,
    ) -> AgentResponse:
        """Delegate message processing to a specialist agent.

        Args:
            agent_name: Name of agent to delegate to
            message: Message to process

        Returns:
            Response from the specialist agent
        """
        logger.info(f"Delegating to {agent_name}")

        # Get or create sub-agent
        if agent_name not in self._sub_agents:
            if agent_name not in AGENT_CONFIGS:
                return AgentResponse(
                    content=f"I don't have access to a {agent_name} specialist right now.",
                    metadata={'error': 'unknown_agent'}
                )

            sub_config = AGENT_CONFIGS[agent_name]
            self._sub_agents[agent_name] = AmbassadorAgent(
                config=sub_config,
                graphiti_client=self.graphiti,
                falkordb_client=self.falkordb,
                student_id=self.student_id,
            )

        sub_agent = self._sub_agents[agent_name]

        # Process with sub-agent
        response = await sub_agent.process_message(message)
        response.delegated_to = agent_name

        return response

    async def _store_episode(self, message: Message, channel: str):
        """Store a message as an episode in Graphiti.

        Args:
            message: Message to store
            channel: Communication channel
        """
        if not self.graphiti:
            return

        try:
            await self.graphiti.add_episode(
                name=f"{self.student_id}_{message.timestamp.isoformat()}",
                episode_body=message.content,
                source_description=f"{channel}_conversation",
                group_id=self.student_id,
            )
        except Exception as e:
            logger.warning(f"Failed to store episode: {e}")

    def _generate_fallback_response(self, message: str) -> str:
        """Generate a fallback response when API is unavailable.

        Args:
            message: User message

        Returns:
            Fallback response string
        """
        return (
            "I'm having trouble connecting to my services right now. "
            "Could you try again in a moment? If this continues, "
            "please check that all services are running properly."
        )

    def register_tool(self, name: str, handler: Callable[..., Awaitable[Any]]):
        """Register a tool for the agent to use.

        Args:
            name: Tool name (must be in config.tools)
            handler: Async function to handle tool calls
        """
        if name not in self.config.tools:
            logger.warning(f"Tool {name} not in agent config, registering anyway")
        self._tools[name] = handler
        logger.info(f"Registered tool: {name}")

    async def check_triggers(self) -> List[Dict[str, Any]]:
        """Check proactive triggers and return actions to take.

        Returns:
            List of triggered actions with context
        """
        triggered_actions = []

        for trigger in self.config.proactive_triggers:
            if await self._evaluate_trigger(trigger):
                triggered_actions.append({
                    'action': trigger.action,
                    'condition': trigger.condition,
                    'priority': trigger.priority,
                })

        # Sort by priority (lower number = higher priority)
        triggered_actions.sort(key=lambda x: x['priority'])

        return triggered_actions

    async def _evaluate_trigger(self, trigger: ProactiveTrigger) -> bool:
        """Evaluate if a trigger condition is met.

        Args:
            trigger: The trigger to evaluate

        Returns:
            True if trigger condition is met
        """
        # In production, this would evaluate conditions against real data
        # For now, return False (triggers require Story 2.3)
        return False

    async def close(self):
        """Clean up agent resources."""
        # Close sub-agents
        for sub_agent in self._sub_agents.values():
            await sub_agent.close()
        self._sub_agents.clear()

        logger.info(f"Closed agent: {self.config.name}")

    def get_conversation_history(self) -> List[Message]:
        """Get the current conversation history.

        Returns:
            List of Message objects
        """
        return self._conversation_history.copy()


# =============================================================================
# Module-level factory function
# =============================================================================

_ambassador_instance: Optional[AmbassadorAgent] = None


async def get_ambassador(
    student_id: str,
    graphiti_client=None,
    falkordb_client=None,
) -> AmbassadorAgent:
    """Get or create an ambassador agent for a student.

    Args:
        student_id: Student ID to get ambassador for
        graphiti_client: Optional Graphiti client
        falkordb_client: Optional FalkorDB client

    Returns:
        Initialized AmbassadorAgent instance
    """
    global _ambassador_instance

    # Create new instance for this student
    agent = AmbassadorAgent(
        config=ambassador_config,
        graphiti_client=graphiti_client,
        falkordb_client=falkordb_client,
        student_id=student_id,
    )

    await agent.initialize()

    return agent
