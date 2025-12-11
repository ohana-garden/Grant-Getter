"""
Graphiti Client for Student Ambassador Platform

Provides temporal knowledge graph capabilities using Graphiti with FalkorDB backend.
Handles episodic memory (conversations) and temporal facts for the ambassador agent.
"""

import os
from datetime import datetime, timezone
from typing import Optional, Any
from dataclasses import dataclass

# Note: graphiti_core requires OPENAI_API_KEY or alternative LLM configuration
# For production, configure with Anthropic Claude as per architecture spec

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EpisodeType
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    Graphiti = None

    # Mock EpisodeType for when graphiti_core is not installed
    class EpisodeType:
        text = "text"
        json = "json"
        message = "message"


@dataclass
class Episode:
    """Represents a conversation episode stored in Graphiti."""
    id: str
    name: str
    body: str
    source: str
    source_description: str
    reference_time: datetime
    entities_extracted: list[str]
    relationships_extracted: list[tuple]


@dataclass
class TemporalFact:
    """Represents a temporal fact with validity period."""
    subject: str
    predicate: str
    obj: str  # 'object' is reserved
    valid_from: datetime
    valid_to: Optional[datetime]
    source: str
    confidence: float


class GraphitiClient:
    """
    Client for Graphiti temporal knowledge graph operations.

    Provides methods for:
    - Adding conversation episodes (episodic memory)
    - Adding temporal facts with validity periods
    - Querying point-in-time knowledge
    - Detecting fact invalidation
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        database: str = "student_ambassador_temporal",
        llm_model: str = "gpt-4o-mini",
        embedder_model: str = "text-embedding-3-small"
    ):
        """
        Initialize Graphiti client with FalkorDB backend.

        Args:
            host: FalkorDB host address
            port: FalkorDB port (default 6379)
            database: Graph database name for temporal data
            llm_model: LLM model for entity extraction
            embedder_model: Model for text embeddings
        """
        self.host = host
        self.port = port
        self.database = database
        self.llm_model = llm_model
        self.embedder_model = embedder_model
        self._graphiti: Optional[Graphiti] = None
        self._initialized = False

    @property
    def is_available(self) -> bool:
        """Check if Graphiti is available."""
        return GRAPHITI_AVAILABLE

    async def initialize(self) -> bool:
        """
        Initialize Graphiti connection and build indices.

        Returns:
            True if initialization successful, False otherwise
        """
        if not GRAPHITI_AVAILABLE:
            return False

        try:
            # Import the FalkorDB driver
            from graphiti_core.driver.falkordb_driver import FalkorDriver

            # Create FalkorDB driver
            driver = FalkorDriver(
                host=self.host,
                port=self.port,
                database=self.database
            )

            # Initialize Graphiti with the driver
            self._graphiti = Graphiti(graph_driver=driver)

            # Build indices (safe to run multiple times)
            await self._graphiti.build_indices_and_constraints()

            self._initialized = True
            return True

        except Exception as e:
            print(f"Failed to initialize Graphiti: {e}")
            return False

    async def close(self) -> None:
        """Close the Graphiti connection."""
        if self._graphiti:
            await self._graphiti.close()
            self._graphiti = None
            self._initialized = False

    # ==========================================================================
    # Episode Operations (Conversation Memory)
    # ==========================================================================

    async def add_episode(
        self,
        name: str,
        episode_body: str,
        source_description: str = "conversation",
        reference_time: Optional[datetime] = None,
        group_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Add a conversation episode to the temporal graph.

        This processes the episode content, extracts entities and relationships,
        and maintains temporal validity of facts.

        Args:
            name: Episode identifier (e.g., "scholarship_discussion_2025_01_15")
            episode_body: Full conversation transcript or text
            source_description: Description of source (e.g., "sms_session", "voice_call")
            reference_time: When this episode occurred (defaults to now)
            group_id: Optional group identifier for the student

        Returns:
            Episode ID if successful, None otherwise
        """
        if not self._initialized or not self._graphiti:
            return None

        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        try:
            result = await self._graphiti.add_episode(
                name=name,
                episode_body=episode_body,
                source=EpisodeType.text,
                source_description=source_description,
                reference_time=reference_time,
                group_id=group_id
            )
            return result.uuid if hasattr(result, 'uuid') else str(result)

        except Exception as e:
            print(f"Failed to add episode: {e}")
            return None

    async def add_conversation(
        self,
        student_id: str,
        messages: list[dict],
        channel: str = "sms",
        session_time: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Add a conversation as an episode.

        Convenience method that formats messages into an episode body.

        Args:
            student_id: Anonymous student identifier
            messages: List of message dicts with 'role' and 'content'
            channel: Communication channel (sms, voice, web)
            session_time: When conversation occurred

        Returns:
            Episode ID if successful
        """
        # Format messages into conversation transcript
        lines = []
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            lines.append(f"{role}: {content}")

        episode_body = "\n".join(lines)
        name = f"conversation_{student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        return await self.add_episode(
            name=name,
            episode_body=episode_body,
            source_description=f"{channel}_conversation",
            reference_time=session_time,
            group_id=student_id
        )

    # ==========================================================================
    # Temporal Fact Operations
    # ==========================================================================

    async def add_fact(
        self,
        subject: str,
        predicate: str,
        obj: str,
        valid_from: Optional[datetime] = None,
        source: str = "system",
        confidence: float = 1.0
    ) -> Optional[str]:
        """
        Add a temporal fact to the knowledge graph.

        Facts are automatically tracked with bi-temporal timestamps:
        - valid_from/valid_to: When the fact was true in the real world
        - created_at: When the fact was recorded in the system

        Args:
            subject: Entity the fact is about (e.g., "Stanford")
            predicate: Relationship type (e.g., "average_aid_package")
            obj: Value or related entity (e.g., "$58,000")
            valid_from: When this fact became true (defaults to now)
            source: Source of the fact
            confidence: Confidence score (0.0-1.0)

        Returns:
            Fact ID if successful
        """
        if not self._initialized or not self._graphiti:
            return None

        if valid_from is None:
            valid_from = datetime.now(timezone.utc)

        # Format as an episode that Graphiti can process
        fact_text = f"{subject} {predicate} {obj}."

        try:
            result = await self._graphiti.add_episode(
                name=f"fact_{subject}_{predicate}_{datetime.now().timestamp()}",
                episode_body=fact_text,
                source=EpisodeType.text,
                source_description=f"fact_from_{source}",
                reference_time=valid_from
            )
            return result.uuid if hasattr(result, 'uuid') else str(result)

        except Exception as e:
            print(f"Failed to add fact: {e}")
            return None

    async def add_scholarship_fact(
        self,
        scholarship_name: str,
        attribute: str,
        value: str,
        valid_from: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Add a fact about a scholarship.

        Args:
            scholarship_name: Name of the scholarship
            attribute: Attribute (deadline, amount, criteria, etc.)
            value: Attribute value

        Returns:
            Fact ID if successful
        """
        return await self.add_fact(
            subject=scholarship_name,
            predicate=attribute,
            obj=value,
            valid_from=valid_from,
            source="scholarship_database"
        )

    async def add_school_fact(
        self,
        school_name: str,
        attribute: str,
        value: str,
        valid_from: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Add a fact about a school.

        Args:
            school_name: Name of the school
            attribute: Attribute (average_aid, acceptance_rate, etc.)
            value: Attribute value

        Returns:
            Fact ID if successful
        """
        return await self.add_fact(
            subject=school_name,
            predicate=attribute,
            obj=value,
            valid_from=valid_from,
            source="school_database"
        )

    # ==========================================================================
    # Query Operations
    # ==========================================================================

    async def search(
        self,
        query: str,
        num_results: int = 10,
        group_ids: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Search the temporal knowledge graph.

        Uses hybrid retrieval combining semantic search, BM25, and graph traversal.

        Args:
            query: Natural language search query
            num_results: Maximum results to return
            group_ids: Optional filter by student group IDs

        Returns:
            List of search results with temporal metadata
        """
        if not self._initialized or not self._graphiti:
            return []

        try:
            results = await self._graphiti.search(
                query=query,
                num_results=num_results,
                group_ids=group_ids
            )

            # Format results
            formatted = []
            for result in results:
                formatted.append({
                    'fact': getattr(result, 'fact', str(result)),
                    'name': getattr(result, 'name', ''),
                    'valid_at': getattr(result, 'valid_at', None),
                    'invalid_at': getattr(result, 'invalid_at', None),
                    'created_at': getattr(result, 'created_at', None),
                    'score': getattr(result, 'score', 0.0)
                })

            return formatted

        except Exception as e:
            print(f"Search failed: {e}")
            return []

    async def query_at_time(
        self,
        query: str,
        point_in_time: datetime,
        num_results: int = 10
    ) -> list[dict]:
        """
        Query what was known at a specific point in time.

        This is a bi-temporal query that returns facts that were:
        1. Valid at the specified time (in the real world)
        2. Known to the system at that time

        Args:
            query: Natural language query
            point_in_time: The point in time to query
            num_results: Maximum results

        Returns:
            List of facts valid at the specified time
        """
        # Note: Full bi-temporal querying may require additional Graphiti configuration
        # This is a simplified implementation
        results = await self.search(query, num_results)

        # Filter to facts valid at the specified time
        filtered = []
        for result in results:
            valid_at = result.get('valid_at')
            invalid_at = result.get('invalid_at')

            # Check if fact was valid at point_in_time
            if valid_at and valid_at <= point_in_time:
                if invalid_at is None or invalid_at > point_in_time:
                    filtered.append(result)

        return filtered

    async def get_student_history(
        self,
        student_id: str,
        limit: int = 50
    ) -> list[dict]:
        """
        Get conversation history for a student.

        Args:
            student_id: The student's anonymous identifier
            limit: Maximum episodes to return

        Returns:
            List of episode summaries
        """
        return await self.search(
            query=f"conversations with student",
            num_results=limit,
            group_ids=[student_id]
        )

    async def detect_invalidated_facts(
        self,
        entity: str
    ) -> list[dict]:
        """
        Detect facts about an entity that have been invalidated.

        Useful for tracking changes like:
        - Scholarship deadline changes
        - School policy updates
        - Aid package modifications

        Args:
            entity: Entity to check for invalidated facts

        Returns:
            List of invalidated facts with invalidation timestamps
        """
        results = await self.search(f"facts about {entity}", num_results=100)

        # Filter to invalidated facts
        invalidated = []
        for result in results:
            if result.get('invalid_at') is not None:
                invalidated.append(result)

        return invalidated

    # ==========================================================================
    # Health & Diagnostics
    # ==========================================================================

    async def health_check(self) -> dict:
        """
        Check Graphiti connection health.

        Returns:
            Health status dictionary
        """
        status = {
            'available': GRAPHITI_AVAILABLE,
            'initialized': self._initialized,
            'connected': False,
            'database': self.database
        }

        if self._initialized and self._graphiti:
            try:
                # Try a simple search to verify connection - call graphiti directly
                await self._graphiti.search(query="health_check", num_results=1)
                status['connected'] = True
            except Exception as e:
                status['error'] = str(e)
                status['connected'] = False

        return status


def get_graphiti_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: str = "student_ambassador_temporal"
) -> GraphitiClient:
    """
    Get a Graphiti client instance using environment variables or defaults.

    Args:
        host: Override host (default: FALKORDB_HOST env or localhost)
        port: Override port (default: FALKORDB_PORT env or 6379)
        database: Graph database name

    Returns:
        Configured GraphitiClient instance
    """
    return GraphitiClient(
        host=host or os.getenv('FALKORDB_HOST', 'localhost'),
        port=port or int(os.getenv('FALKORDB_PORT', '6379')),
        database=database
    )
