"""
Tests for Specialist Agents - Stories 3.1 and 3.2

Story 3.1 - Scholarship Scout:
- Scout runs on schedule
- Scout finds new scholarships
- Scout matches scholarships to anonymized profiles
- Ambassador can query Scout via A2A

Story 3.2 - Appeal Strategist:
- Strategist can query commons for school negotiation patterns
- Strategist can identify effective arguments
- Strategist can generate appeal letter draft
- All inputs are anonymized
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock


# ============================================================================
# Scholarship Scout Tests
# ============================================================================

class TestScholarshipScoutAgent:
    """Tests for ScholarshipScoutAgent."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB client."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'test_scholarship',
            'name': 'Test Scholarship',
            'url': 'https://example.com/scholarship',
            'amount_min': 1000,
            'amount_max': 5000,
            'criteria': 'First-generation STEM students',
            'deadline': (date.today() + timedelta(days=30)).isoformat(),
            'verified': True,
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    def test_crawl_status_enum(self):
        """Test CrawlStatus enum."""
        from agents.specialists.scholarship_scout import CrawlStatus

        assert CrawlStatus.COMPLETED.value == "completed"
        assert CrawlStatus.FAILED.value == "failed"

    def test_legitimacy_status_enum(self):
        """Test LegitimacyStatus enum."""
        from agents.specialists.scholarship_scout import LegitimacyStatus

        assert LegitimacyStatus.VERIFIED.value == "verified"
        assert LegitimacyStatus.SCAM.value == "scam"

    def test_crawl_result_dataclass(self):
        """Test CrawlResult dataclass."""
        from agents.specialists.scholarship_scout import CrawlResult, CrawlStatus

        result = CrawlResult(
            source_url="https://example.com",
            scholarships_found=10,
            new_scholarships=5,
            updated_scholarships=5,
            status=CrawlStatus.COMPLETED,
        )

        assert result.scholarships_found == 10
        assert result.status == CrawlStatus.COMPLETED

    def test_scout_initialization(self):
        """Test scout agent initialization."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent()
        assert scout.falkordb is None
        assert scout._is_running is False

    def test_scout_model_name(self):
        """Test scout uses correct model."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent()
        assert "haiku" in scout.model_name.lower()  # Uses Haiku for cost efficiency

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping scout."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent()

        await scout.start()
        assert scout._is_running is True

        await scout.stop()
        assert scout._is_running is False

    @pytest.mark.asyncio
    async def test_run_crawl_cycle(self, mock_falkordb):
        """AC: Scout runs on schedule (via crawl cycle)."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent, CrawlStatus

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()

        results = await scout.run_crawl_cycle()

        assert len(results) > 0
        assert any(r.status == CrawlStatus.COMPLETED for r in results)

    @pytest.mark.asyncio
    async def test_finds_new_scholarships(self, mock_falkordb):
        """AC: Scout finds new scholarships."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()

        # First crawl should find new scholarships
        results = await scout.run_crawl_cycle()

        total_new = sum(r.new_scholarships for r in results)
        assert total_new > 0

    @pytest.mark.asyncio
    async def test_matches_to_profiles(self, mock_falkordb):
        """AC: Scout matches scholarships to anonymized profiles."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()
        await scout.run_crawl_cycle()

        matches = await scout.match_to_profiles(
            profile_ids=["profile_123"],
            min_score=0.5,
        )

        assert "profile_123" in matches
        assert isinstance(matches["profile_123"], list)

    @pytest.mark.asyncio
    async def test_legitimacy_verification(self, mock_falkordb):
        """Test scholarship legitimacy verification."""
        from agents.specialists.scholarship_scout import (
            ScholarshipScoutAgent, LegitimacyStatus
        )

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)

        # Test verified scholarship
        verified = await scout._verify_legitimacy({
            'name': 'Gates Scholarship',
            'criteria': 'High-achieving students',
            'verified': True,
        })
        assert verified == LegitimacyStatus.VERIFIED

        # Test suspicious scholarship
        suspicious = await scout._verify_legitimacy({
            'name': 'Easy Money Scholarship - Fee Required',
            'criteria': 'Everyone wins!',
        })
        assert suspicious in (LegitimacyStatus.SUSPICIOUS, LegitimacyStatus.SCAM)

    @pytest.mark.asyncio
    async def test_a2a_query_scholarships(self, mock_falkordb):
        """AC: Ambassador can query Scout via A2A - scholarship search."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()
        await scout.run_crawl_cycle()

        results = await scout.query_scholarships(
            query="STEM",
            limit=5,
        )

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_a2a_get_matches(self, mock_falkordb):
        """AC: Ambassador can query Scout via A2A - get matches."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()
        await scout.run_crawl_cycle()
        await scout.match_to_profiles(["profile_123"])

        matches = await scout.get_matches_for_profile("profile_123")
        assert isinstance(matches, list)

    @pytest.mark.asyncio
    async def test_a2a_verify_scholarship(self, mock_falkordb):
        """AC: Ambassador can query Scout via A2A - verify scholarship."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()
        await scout.run_crawl_cycle()

        result = await scout.verify_scholarship("test_scholarship")
        assert 'legitimacy' in result or 'found' in result

    def test_get_stats(self, mock_falkordb):
        """Test getting scout stats."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        stats = scout.get_stats()

        assert 'is_running' in stats
        assert 'total_scholarships' in stats


# ============================================================================
# Appeal Strategist Tests
# ============================================================================

class TestAppealStrategistAgent:
    """Tests for AppealStrategistAgent."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB client."""
        mock = MagicMock()

        # Mock school node
        school_node = MagicMock()
        school_node.properties = {
            'id': 'stanford',
            'name': 'Stanford University',
            'type': 'private',
        }

        # Mock behavior node
        behavior_node = MagicMock()
        behavior_node.properties = {
            'id': 'negotiates_competing',
            'pattern': 'negotiates_with_competing_offers',
            'description': 'School negotiates when presented with competing offers',
        }

        mock_result = MagicMock()
        mock_result.result_set = [[school_node, [{'behavior': behavior_node, 'confidence': 0.8, 'sample_size': 50}]]]
        mock.query.return_value = mock_result

        return mock

    def test_strategy_type_enum(self):
        """Test StrategyType enum."""
        from agents.specialists.appeal_strategist import StrategyType

        assert StrategyType.COMPETING_OFFER.value == "competing_offer"
        assert StrategyType.CHANGED_CIRCUMSTANCES.value == "changed_circumstances"

    def test_argument_type_enum(self):
        """Test ArgumentType enum."""
        from agents.specialists.appeal_strategist import ArgumentType

        assert ArgumentType.FINANCIAL_HARDSHIP.value == "financial_hardship"
        assert ArgumentType.COMPETING_OFFERS.value == "competing_offers"

    def test_school_behavior_dataclass(self):
        """Test SchoolBehavior dataclass."""
        from agents.specialists.appeal_strategist import SchoolBehavior, ArgumentType

        behavior = SchoolBehavior(
            school_id="stanford",
            school_name="Stanford University",
            negotiates=True,
            responds_to_competing_offers=True,
            typical_increase_percent=12.0,
            typical_increase_amount=3000.0,
            success_rate=0.4,
            sample_size=100,
            common_arguments=[ArgumentType.COMPETING_OFFERS],
            best_timing="Within 2 weeks",
        )

        assert behavior.negotiates is True
        assert behavior.success_rate == 0.4

    def test_strategist_initialization(self):
        """Test strategist initialization."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()
        assert strategist.falkordb is None

    def test_strategist_model_name(self):
        """Test strategist uses correct model."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()
        assert "sonnet" in strategist.model_name.lower()  # Uses Sonnet for reasoning

    @pytest.mark.asyncio
    async def test_analyze_school(self, mock_falkordb):
        """AC: Strategist can query commons for school negotiation patterns."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent(falkordb_client=mock_falkordb)

        result = await strategist.analyze_school("stanford")

        assert 'negotiates' in result or 'found' in result

    @pytest.mark.asyncio
    async def test_get_strategies(self):
        """AC: Strategist can identify effective arguments."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()

        strategies = await strategist.get_strategies(
            school_id="stanford",
            context={'has_competing_offer': True},
        )

        assert len(strategies) > 0
        assert any('competing' in s.get('type', '') for s in strategies)

    @pytest.mark.asyncio
    async def test_draft_appeal(self):
        """AC: Strategist can generate appeal letter draft."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()

        draft = await strategist.draft_appeal(
            school_id="stanford",
            student_context={
                'school_name': 'Stanford University',
                'has_competing_offer': True,
                'competing_school': 'MIT',
                'competing_amount': '$50,000',
            },
        )

        assert 'full_text' in draft
        assert 'strategy_used' in draft
        assert len(draft['full_text']) > 100

    @pytest.mark.asyncio
    async def test_draft_appeal_changed_circumstances(self):
        """Test appeal draft for changed circumstances."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()

        draft = await strategist.draft_appeal(
            school_id="stanford",
            student_context={
                'school_name': 'Stanford University',
                'changed_circumstances': True,
                'circumstance_description': 'job loss',
            },
        )

        assert 'full_text' in draft
        assert 'change' in draft['full_text'].lower() or 'circumstance' in draft['full_text'].lower()

    @pytest.mark.asyncio
    async def test_get_success_patterns(self, mock_falkordb):
        """Test getting success patterns."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent(falkordb_client=mock_falkordb)

        patterns = await strategist.get_success_patterns()

        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert all('success_rate' in p for p in patterns)

    @pytest.mark.asyncio
    async def test_all_inputs_anonymized(self):
        """AC: All inputs are anonymized."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()

        # Draft should work with anonymized context (no real names/IDs)
        draft = await strategist.draft_appeal(
            school_id="school_123",  # Anonymized ID
            student_context={
                'school_name': 'Target School',  # Generic
                # No PII included
            },
        )

        # Should still produce a valid draft
        assert 'full_text' in draft
        assert len(draft['full_text']) > 50

    def test_get_stats(self):
        """Test getting strategist stats."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()
        stats = strategist.get_stats()

        assert 'schools_analyzed' in stats
        assert 'strategies_available' in stats


# ============================================================================
# A2A Protocol Tests
# ============================================================================

class TestA2AProtocol:
    """Tests for A2A Protocol."""

    def test_a2a_action_enum(self):
        """Test A2AAction enum."""
        from agents.specialists.a2a_protocol import A2AAction

        assert A2AAction.SEARCH_SCHOLARSHIPS.value == "search_scholarships"
        assert A2AAction.DRAFT_APPEAL.value == "draft_appeal"

    def test_a2a_status_enum(self):
        """Test A2AStatus enum."""
        from agents.specialists.a2a_protocol import A2AStatus

        assert A2AStatus.COMPLETED.value == "completed"
        assert A2AStatus.FAILED.value == "failed"

    def test_a2a_request_creation(self):
        """Test A2ARequest creation."""
        from agents.specialists.a2a_protocol import A2ARequest, A2AAction

        request = A2ARequest.create(
            source="ambassador",
            target="scholarship_scout",
            action=A2AAction.SEARCH_SCHOLARSHIPS,
            params={'query': 'STEM'},
        )

        assert request.source_agent == "ambassador"
        assert request.target_agent == "scholarship_scout"
        assert request.params['query'] == 'STEM'

    def test_a2a_response_success(self):
        """Test A2AResponse success creation."""
        from agents.specialists.a2a_protocol import A2AResponse, A2AStatus

        response = A2AResponse.success(
            request_id="test_123",
            data={'scholarships': []},
            processing_time_ms=50.0,
        )

        assert response.status == A2AStatus.COMPLETED
        assert response.processing_time_ms == 50.0

    def test_a2a_response_failure(self):
        """Test A2AResponse failure creation."""
        from agents.specialists.a2a_protocol import A2AResponse, A2AStatus

        response = A2AResponse.failure(
            request_id="test_123",
            error="Agent not found",
        )

        assert response.status == A2AStatus.FAILED
        assert response.error == "Agent not found"

    def test_protocol_initialization(self):
        """Test protocol initialization."""
        from agents.specialists.a2a_protocol import A2AProtocol

        protocol = A2AProtocol()
        assert len(protocol._agents) == 0

    def test_register_agent(self):
        """Test registering an agent."""
        from agents.specialists.a2a_protocol import A2AProtocol
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        protocol = A2AProtocol()
        scout = ScholarshipScoutAgent()

        protocol.register_agent("scholarship_scout", scout)

        assert "scholarship_scout" in protocol.get_registered_agents()

    @pytest.mark.asyncio
    async def test_send_request_to_scout(self):
        """Test sending request to scholarship scout."""
        from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AAction, A2AStatus
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        protocol = A2AProtocol()
        scout = ScholarshipScoutAgent()
        await scout.start()

        protocol.register_agent("scholarship_scout", scout)

        request = A2ARequest.create(
            source="ambassador",
            target="scholarship_scout",
            action=A2AAction.GET_SCOUT_STATS,
        )

        response = await protocol.send_request(request)

        assert response.status == A2AStatus.COMPLETED
        assert 'is_running' in response.data

    @pytest.mark.asyncio
    async def test_send_request_to_strategist(self):
        """Test sending request to appeal strategist."""
        from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AAction, A2AStatus
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        protocol = A2AProtocol()
        strategist = AppealStrategistAgent()

        protocol.register_agent("appeal_strategist", strategist)

        request = A2ARequest.create(
            source="ambassador",
            target="appeal_strategist",
            action=A2AAction.GET_STRATEGIES,
            params={'school_id': 'stanford', 'context': {}},
        )

        response = await protocol.send_request(request)

        assert response.status == A2AStatus.COMPLETED
        assert 'strategies' in response.data

    @pytest.mark.asyncio
    async def test_send_request_unregistered_agent(self):
        """Test sending request to unregistered agent."""
        from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AAction, A2AStatus

        protocol = A2AProtocol()

        request = A2ARequest.create(
            source="ambassador",
            target="nonexistent_agent",
            action=A2AAction.HEALTH_CHECK,
        )

        response = await protocol.send_request(request)

        assert response.status == A2AStatus.FAILED
        assert "not registered" in response.error

    def test_get_stats(self):
        """Test getting protocol stats."""
        from agents.specialists.a2a_protocol import A2AProtocol

        protocol = A2AProtocol()
        stats = protocol.get_stats()

        assert 'registered_agents' in stats
        assert 'total_requests' in stats
        assert 'success_rate' in stats


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Tests for A2A convenience functions."""

    def test_create_scholarship_search_request(self):
        """Test creating scholarship search request."""
        from agents.specialists.a2a_protocol import (
            create_scholarship_search_request, A2AAction
        )

        request = create_scholarship_search_request(
            source="ambassador",
            query="engineering",
            profile_id="profile_123",
        )

        assert request.target_agent == "scholarship_scout"
        assert request.action == A2AAction.SEARCH_SCHOLARSHIPS
        assert request.params['query'] == "engineering"

    def test_create_verify_scholarship_request(self):
        """Test creating verify scholarship request."""
        from agents.specialists.a2a_protocol import (
            create_verify_scholarship_request, A2AAction
        )

        request = create_verify_scholarship_request(
            source="ambassador",
            scholarship_id="scholarship_123",
        )

        assert request.action == A2AAction.VERIFY_SCHOLARSHIP

    def test_create_draft_appeal_request(self):
        """Test creating draft appeal request."""
        from agents.specialists.a2a_protocol import (
            create_draft_appeal_request, A2AAction
        )

        request = create_draft_appeal_request(
            source="ambassador",
            school_id="stanford",
            student_context={'has_competing_offer': True},
        )

        assert request.target_agent == "appeal_strategist"
        assert request.action == A2AAction.DRAFT_APPEAL


# ============================================================================
# Module Tests
# ============================================================================

class TestSpecialistsModule:
    """Tests for specialists module."""

    def test_module_exports(self):
        """Test module exports all required classes."""
        from agents.specialists import (
            ScholarshipScoutAgent,
            AppealStrategistAgent,
            A2AProtocol,
            A2ARequest,
            A2AResponse,
        )

        assert ScholarshipScoutAgent is not None
        assert AppealStrategistAgent is not None
        assert A2AProtocol is not None
        assert A2ARequest is not None
        assert A2AResponse is not None


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================

class TestAcceptanceCriteria:
    """Tests verifying Stories 3.1 and 3.2 acceptance criteria."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'test_scholarship',
            'name': 'Test STEM Scholarship',
            'amount_max': 10000,
            'criteria': 'First-generation STEM students',
            'deadline': (date.today() + timedelta(days=30)).isoformat(),
            'verified': True,
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result
        mock.query.return_value = mock_result

        return mock

    @pytest.mark.asyncio
    async def test_ac_scout_runs_on_schedule(self, mock_falkordb):
        """AC 3.1: Scout runs on schedule."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)

        # Start the scout
        await scout.start()
        assert scout._is_running is True

        # Run a crawl cycle
        results = await scout.run_crawl_cycle()

        # Should complete successfully
        assert len(results) > 0
        assert scout._last_crawl is not None

    @pytest.mark.asyncio
    async def test_ac_scout_finds_new_scholarships(self, mock_falkordb):
        """AC 3.1: Scout finds new scholarships."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()

        results = await scout.run_crawl_cycle()

        total_found = sum(r.scholarships_found for r in results)
        assert total_found > 0

    @pytest.mark.asyncio
    async def test_ac_scout_matches_to_profiles(self, mock_falkordb):
        """AC 3.1: Scout matches scholarships to anonymized profiles."""
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()
        await scout.run_crawl_cycle()

        matches = await scout.match_to_profiles(["anon_profile_123"])

        assert "anon_profile_123" in matches

    @pytest.mark.asyncio
    async def test_ac_ambassador_queries_scout_via_a2a(self, mock_falkordb):
        """AC 3.1: Ambassador can query Scout via A2A."""
        from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AAction, A2AStatus
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        # Set up protocol and scout
        protocol = A2AProtocol()
        scout = ScholarshipScoutAgent(falkordb_client=mock_falkordb)
        await scout.start()
        await scout.run_crawl_cycle()

        protocol.register_agent("scholarship_scout", scout)

        # Ambassador queries scout
        request = A2ARequest.create(
            source="ambassador",
            target="scholarship_scout",
            action=A2AAction.SEARCH_SCHOLARSHIPS,
            params={'query': 'STEM', 'limit': 5},
        )

        response = await protocol.send_request(request)

        assert response.status == A2AStatus.COMPLETED
        assert 'scholarships' in response.data

    @pytest.mark.asyncio
    async def test_ac_strategist_queries_school_patterns(self, mock_falkordb):
        """AC 3.2: Strategist can query commons for school negotiation patterns."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent(falkordb_client=mock_falkordb)

        result = await strategist.analyze_school("stanford")

        # Should return analysis with negotiation info
        assert 'found' in result or 'negotiates' in result

    @pytest.mark.asyncio
    async def test_ac_strategist_identifies_arguments(self):
        """AC 3.2: Strategist can identify effective arguments."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()

        strategies = await strategist.get_strategies(
            school_id="stanford",
            context={'has_competing_offer': True},
        )

        # Should identify competing offer as effective
        assert len(strategies) > 0
        assert any(s.get('key_points') for s in strategies)

    @pytest.mark.asyncio
    async def test_ac_strategist_generates_draft(self):
        """AC 3.2: Strategist can generate appeal letter draft."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent

        strategist = AppealStrategistAgent()

        draft = await strategist.draft_appeal(
            school_id="stanford",
            student_context={
                'school_name': 'Stanford University',
                'has_competing_offer': True,
            },
        )

        # Should generate a complete draft
        assert 'full_text' in draft
        assert len(draft['full_text']) > 200
        assert 'tips' in draft

    @pytest.mark.asyncio
    async def test_ac_all_inputs_anonymized(self):
        """AC 3.2: All inputs are anonymized."""
        from agents.specialists.appeal_strategist import AppealStrategistAgent
        from agents.specialists.scholarship_scout import ScholarshipScoutAgent

        # Strategist works with anonymized context
        strategist = AppealStrategistAgent()
        draft = await strategist.draft_appeal(
            school_id="school_anon_123",  # Anonymized
            student_context={},  # No PII
        )
        assert 'full_text' in draft

        # Scout works with anonymized profiles
        scout = ScholarshipScoutAgent()
        matches = await scout.match_to_profiles(
            profile_ids=["anon_profile_456"],  # Anonymized
        )
        assert "anon_profile_456" in matches


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
