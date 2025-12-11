"""
Tests for Graphiti Integration - Story 1.2

Verifies:
- Can add episodes (conversations)
- Can add temporal facts
- Can query "what did we know at time X"
- Can detect fact invalidation
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock


class TestGraphitiClientInitialization:
    """Tests for GraphitiClient initialization."""

    def test_client_initialization_defaults(self):
        """Test client initializes with default values."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        assert client.host == "localhost"
        assert client.port == 6379
        assert client.database == "student_ambassador_temporal"

    def test_client_initialization_custom(self):
        """Test client initializes with custom values."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient(
            host="custom-host",
            port=6380,
            database="custom_db"
        )
        assert client.host == "custom-host"
        assert client.port == 6380
        assert client.database == "custom_db"

    def test_is_available_property(self):
        """Test is_available reflects graphiti import status."""
        from db.graphiti_client import GraphitiClient, GRAPHITI_AVAILABLE

        client = GraphitiClient()
        assert client.is_available == GRAPHITI_AVAILABLE


class TestGraphitiClientWithMocks:
    """Tests for GraphitiClient operations using mocks."""

    @pytest.fixture
    def mock_graphiti(self):
        """Create a mock Graphiti instance."""
        mock = AsyncMock()
        episode_result = Mock()
        episode_result.uuid = "episode-123"
        mock.add_episode = AsyncMock(return_value=episode_result)
        mock.search = AsyncMock(return_value=[])
        mock.build_indices_and_constraints = AsyncMock()
        mock.close = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_add_episode(self, mock_graphiti):
        """Test adding a conversation episode."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        result = await client.add_episode(
            name="test_episode",
            episode_body="User asked about scholarships",
            source_description="sms_session"
        )

        assert result == "episode-123"
        mock_graphiti.add_episode.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_episode_not_initialized(self):
        """Test add_episode returns None when not initialized."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._initialized = False

        result = await client.add_episode(
            name="test_episode",
            episode_body="Test content"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_add_conversation(self, mock_graphiti):
        """Test adding a formatted conversation."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        messages = [
            {"role": "user", "content": "Find scholarships for me"},
            {"role": "assistant", "content": "I found 3 scholarships"}
        ]

        result = await client.add_conversation(
            student_id="student_123",
            messages=messages,
            channel="sms"
        )

        assert result == "episode-123"
        call_args = mock_graphiti.add_episode.call_args
        assert "user: Find scholarships for me" in call_args.kwargs['episode_body']
        assert "assistant: I found 3 scholarships" in call_args.kwargs['episode_body']

    @pytest.mark.asyncio
    async def test_add_fact(self, mock_graphiti):
        """Test adding a temporal fact."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        result = await client.add_fact(
            subject="Stanford",
            predicate="average_aid_package",
            obj="$58,000",
            source="school_database"
        )

        assert result == "episode-123"
        call_args = mock_graphiti.add_episode.call_args
        assert "Stanford average_aid_package $58,000" in call_args.kwargs['episode_body']

    @pytest.mark.asyncio
    async def test_add_scholarship_fact(self, mock_graphiti):
        """Test adding a scholarship-specific fact."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        result = await client.add_scholarship_fact(
            scholarship_name="Gates Scholarship",
            attribute="deadline",
            value="2025-09-15"
        )

        assert result == "episode-123"

    @pytest.mark.asyncio
    async def test_add_school_fact(self, mock_graphiti):
        """Test adding a school-specific fact."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        result = await client.add_school_fact(
            school_name="Harvard",
            attribute="acceptance_rate",
            value="3.4%"
        )

        assert result == "episode-123"


class TestSearchOperations:
    """Tests for search and query operations."""

    @pytest.fixture
    def mock_search_results(self):
        """Create mock search results with temporal data."""
        results = [
            Mock(
                fact="Stanford meets 100% of demonstrated need",
                name="aid_policy",
                valid_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                invalid_at=None,
                created_at=datetime(2020, 1, 15, tzinfo=timezone.utc),
                score=0.95
            ),
            Mock(
                fact="Stanford deadline is January 2",
                name="deadline",
                valid_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                invalid_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                created_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
                score=0.88
            )
        ]
        return results

    @pytest.mark.asyncio
    async def test_search(self, mock_search_results):
        """Test basic search functionality."""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=mock_search_results)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        results = await client.search("Stanford aid policy")

        assert len(results) == 2
        assert results[0]['fact'] == "Stanford meets 100% of demonstrated need"
        assert results[0]['score'] == 0.95

    @pytest.mark.asyncio
    async def test_search_not_initialized(self):
        """Test search returns empty when not initialized."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._initialized = False

        results = await client.search("test query")

        assert results == []

    @pytest.mark.asyncio
    async def test_query_at_time(self, mock_search_results):
        """Test bi-temporal query at specific point in time."""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=mock_search_results)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        # Query at a time when both facts were valid
        point_in_time = datetime(2024, 6, 1, tzinfo=timezone.utc)
        results = await client.query_at_time("Stanford", point_in_time)

        # Both facts should be valid at this time
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_query_at_time_filters_invalid(self, mock_search_results):
        """Test query_at_time filters out invalidated facts."""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=mock_search_results)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        # Query at a time after the deadline fact was invalidated
        point_in_time = datetime(2025, 6, 1, tzinfo=timezone.utc)
        results = await client.query_at_time("Stanford", point_in_time)

        # Only the aid policy fact should be valid
        assert len(results) == 1
        assert "need" in results[0]['fact']

    @pytest.mark.asyncio
    async def test_detect_invalidated_facts(self, mock_search_results):
        """Test detecting invalidated facts."""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=mock_search_results)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        invalidated = await client.detect_invalidated_facts("Stanford")

        # Only the deadline fact has an invalid_at date
        assert len(invalidated) == 1
        assert "deadline" in invalidated[0]['fact']


class TestStudentHistory:
    """Tests for student history retrieval."""

    @pytest.mark.asyncio
    async def test_get_student_history(self):
        """Test retrieving student conversation history."""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=[
            Mock(fact="User discussed FAFSA", name="conv1", valid_at=None, invalid_at=None, created_at=None, score=0.9),
            Mock(fact="User asked about Stanford", name="conv2", valid_at=None, invalid_at=None, created_at=None, score=0.85)
        ])

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        history = await client.get_student_history("student_123")

        assert len(history) == 2
        mock_graphiti.search.assert_called_once()
        call_kwargs = mock_graphiti.search.call_args.kwargs
        assert call_kwargs['group_ids'] == ["student_123"]


class TestHealthCheck:
    """Tests for health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test health check when connected."""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=[])

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        status = await client.health_check()

        assert status['initialized'] is True
        assert status['connected'] is True
        assert status['database'] == "student_ambassador_temporal"

    @pytest.mark.asyncio
    async def test_health_check_not_initialized(self):
        """Test health check when not initialized."""
        from db.graphiti_client import GraphitiClient

        client = GraphitiClient()
        client._initialized = False

        status = await client.health_check()

        assert status['initialized'] is False
        assert status['connected'] is False

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """Test health check when connection fails."""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(side_effect=Exception("Connection failed"))

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        status = await client.health_check()

        assert status['initialized'] is True
        assert status['connected'] is False
        assert 'error' in status


class TestDataclasses:
    """Tests for data model classes."""

    def test_episode_dataclass(self):
        """Test Episode dataclass."""
        from db.graphiti_client import Episode

        episode = Episode(
            id="ep-123",
            name="scholarship_discussion",
            body="User asked about Gates Scholarship",
            source="sms",
            source_description="SMS conversation",
            reference_time=datetime.now(),
            entities_extracted=["Gates Scholarship", "user"],
            relationships_extracted=[("user", "asked_about", "Gates Scholarship")]
        )

        assert episode.id == "ep-123"
        assert episode.name == "scholarship_discussion"
        assert len(episode.entities_extracted) == 2

    def test_temporal_fact_dataclass(self):
        """Test TemporalFact dataclass."""
        from db.graphiti_client import TemporalFact

        fact = TemporalFact(
            subject="Stanford",
            predicate="average_aid_package",
            obj="$58,000",
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="school_database",
            confidence=0.95
        )

        assert fact.subject == "Stanford"
        assert fact.predicate == "average_aid_package"
        assert fact.valid_to is None
        assert fact.confidence == 0.95


class TestGetGraphitiClient:
    """Tests for get_graphiti_client factory function."""

    def test_get_graphiti_client_defaults(self):
        """Test factory function with defaults."""
        from db.graphiti_client import get_graphiti_client

        client = get_graphiti_client()
        assert client.host == "localhost"
        assert client.port == 6379

    def test_get_graphiti_client_custom(self):
        """Test factory function with custom values."""
        from db.graphiti_client import get_graphiti_client

        client = get_graphiti_client(
            host="custom-host",
            port=6380,
            database="custom_db"
        )
        assert client.host == "custom-host"
        assert client.port == 6380
        assert client.database == "custom_db"

    @patch.dict('os.environ', {'FALKORDB_HOST': 'env-host', 'FALKORDB_PORT': '7000'})
    def test_get_graphiti_client_from_env(self):
        """Test factory function reads from environment."""
        from db.graphiti_client import get_graphiti_client

        client = get_graphiti_client()
        assert client.host == "env-host"
        assert client.port == 7000


class TestAcceptanceCriteria:
    """
    Tests verifying Story 1.2 acceptance criteria:
    - Can add episodes (conversations)
    - Can add temporal facts
    - Can query "what did we know at time X"
    - Can detect fact invalidation
    """

    @pytest.mark.asyncio
    async def test_ac_add_episodes(self):
        """AC: Can add episodes (conversations)"""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        episode_result = Mock()
        episode_result.uuid = "ep-123"
        mock_graphiti.add_episode = AsyncMock(return_value=episode_result)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        # Test adding a raw episode
        episode_id = await client.add_episode(
            name="scholarship_discovery_session",
            episode_body="Student: I need help finding scholarships for computer science\n"
                        "Ambassador: I'll help you find relevant scholarships based on your profile.",
            source_description="voice_session"
        )
        assert episode_id is not None

        # Test adding a formatted conversation
        messages = [
            {"role": "student", "content": "What scholarships can I apply for?"},
            {"role": "ambassador", "content": "Based on your GPA and interests, I found 5 matches."}
        ]
        conv_id = await client.add_conversation(
            student_id="anon_student_456",
            messages=messages,
            channel="sms"
        )
        assert conv_id is not None

    @pytest.mark.asyncio
    async def test_ac_add_temporal_facts(self):
        """AC: Can add temporal facts"""
        from db.graphiti_client import GraphitiClient

        mock_graphiti = AsyncMock()
        fact_result = Mock()
        fact_result.uuid = "fact-123"
        mock_graphiti.add_episode = AsyncMock(return_value=fact_result)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        # Add a scholarship fact with temporal validity
        fact_id = await client.add_fact(
            subject="Gates_Scholarship",
            predicate="deadline",
            obj="2025-09-15",
            valid_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            source="scholarship_database",
            confidence=1.0
        )
        assert fact_id is not None

        # Add a school fact
        school_fact_id = await client.add_school_fact(
            school_name="Stanford",
            attribute="average_aid_package",
            value="$58,000"
        )
        assert school_fact_id is not None

    @pytest.mark.asyncio
    async def test_ac_query_at_time(self):
        """AC: Can query 'what did we know at time X'"""
        from db.graphiti_client import GraphitiClient

        # Create mock results with temporal data
        mock_results = [
            Mock(
                fact="Gates Scholarship deadline is September 15, 2025",
                name="deadline_fact",
                valid_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                invalid_at=None,
                created_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
                score=0.95
            ),
            Mock(
                fact="Gates Scholarship deadline was October 1, 2024",
                name="old_deadline",
                valid_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                invalid_at=datetime(2024, 12, 31, tzinfo=timezone.utc),
                created_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
                score=0.88
            )
        ]

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=mock_results)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        # Query at a time in 2024 - should get old deadline
        point_2024 = datetime(2024, 6, 1, tzinfo=timezone.utc)
        results_2024 = await client.query_at_time("Gates Scholarship deadline", point_2024)

        # Should only return the fact valid in 2024
        assert len(results_2024) == 1
        assert "October 1, 2024" in results_2024[0]['fact']

        # Query at a time in 2025 - should get new deadline
        point_2025 = datetime(2025, 3, 1, tzinfo=timezone.utc)
        results_2025 = await client.query_at_time("Gates Scholarship deadline", point_2025)

        # Should only return the fact valid in 2025
        assert len(results_2025) == 1
        assert "September 15, 2025" in results_2025[0]['fact']

    @pytest.mark.asyncio
    async def test_ac_detect_fact_invalidation(self):
        """AC: Can detect fact invalidation"""
        from db.graphiti_client import GraphitiClient

        # Mock results with some invalidated facts
        mock_results = [
            Mock(
                fact="Old scholarship amount was $5,000",
                name="old_amount",
                valid_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                invalid_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                created_at=datetime(2023, 1, 5, tzinfo=timezone.utc),
                score=0.9
            ),
            Mock(
                fact="Current scholarship amount is $7,500",
                name="current_amount",
                valid_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                invalid_at=None,
                created_at=datetime(2024, 1, 5, tzinfo=timezone.utc),
                score=0.95
            ),
            Mock(
                fact="Old deadline was March 1",
                name="old_deadline",
                valid_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                invalid_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                created_at=datetime(2023, 1, 5, tzinfo=timezone.utc),
                score=0.85
            )
        ]

        mock_graphiti = AsyncMock()
        mock_graphiti.search = AsyncMock(return_value=mock_results)

        client = GraphitiClient()
        client._graphiti = mock_graphiti
        client._initialized = True

        # Detect invalidated facts
        invalidated = await client.detect_invalidated_facts("Test Scholarship")

        # Should find 2 invalidated facts
        assert len(invalidated) == 2

        # All returned facts should have invalid_at set
        for fact in invalidated:
            assert fact['invalid_at'] is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
