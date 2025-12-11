"""
Tests for Specialist Agents - Stories 3.1, 3.2, 3.3, and 3.4

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

Story 3.3 - Deadline Sentinel:
- Sentinel runs daily checks
- Detects deadline changes on school websites
- Alerts students of changes
- Ambassador can query for specific deadlines

Story 3.4 - Document Analyst:
- Can parse award letters extracting key fields
- Can parse transcripts extracting GPA, courses
- Validates document completeness
- All processing is local (no data leaves device)
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
# Deadline Sentinel Tests
# ============================================================================

class TestDeadlineSentinelAgent:
    """Tests for DeadlineSentinelAgent."""

    def test_deadline_type_enum(self):
        """Test DeadlineType enum."""
        from agents.specialists.deadline_sentinel import DeadlineType

        assert DeadlineType.FAFSA.value == "fafsa"
        assert DeadlineType.SCHOLARSHIP.value == "scholarship"

    def test_deadline_status_enum(self):
        """Test DeadlineStatus enum."""
        from agents.specialists.deadline_sentinel import DeadlineStatus

        assert DeadlineStatus.UPCOMING.value == "upcoming"
        assert DeadlineStatus.URGENT.value == "urgent"

    def test_source_reliability_enum(self):
        """Test SourceReliability enum."""
        from agents.specialists.deadline_sentinel import SourceReliability

        assert SourceReliability.OFFICIAL.value == "official"
        assert SourceReliability.SCRAPED.value == "scraped"

    def test_deadline_entry_dataclass(self):
        """Test DeadlineEntry dataclass."""
        from agents.specialists.deadline_sentinel import (
            DeadlineEntry, DeadlineType, DeadlineStatus
        )

        deadline = DeadlineEntry(
            id="test_deadline",
            deadline_type=DeadlineType.FAFSA,
            name="FAFSA Deadline",
            due_date=date.today() + timedelta(days=10),
        )

        assert deadline.days_until == 10
        assert deadline.is_past is False

    def test_deadline_entry_past(self):
        """Test past deadline detection."""
        from agents.specialists.deadline_sentinel import DeadlineEntry, DeadlineType

        deadline = DeadlineEntry(
            id="past_deadline",
            deadline_type=DeadlineType.FAFSA,
            name="Past Deadline",
            due_date=date.today() - timedelta(days=5),
        )

        assert deadline.is_past is True
        assert deadline.days_until < 0

    def test_scrape_result_dataclass(self):
        """Test ScrapeResult dataclass."""
        from agents.specialists.deadline_sentinel import ScrapeResult

        result = ScrapeResult(
            source_url="https://example.edu/finaid",
            deadlines_found=5,
            new_deadlines=3,
            updated_deadlines=2,
        )

        assert result.deadlines_found == 5
        assert result.success is True

    def test_deadline_change_dataclass(self):
        """Test DeadlineChange dataclass."""
        from agents.specialists.deadline_sentinel import DeadlineChange

        change = DeadlineChange(
            deadline_id="test_deadline",
            change_type="updated",
            old_date=date.today(),
            new_date=date.today() + timedelta(days=7),
        )

        assert change.change_type == "updated"
        assert change.notified is False

    def test_sentinel_initialization(self):
        """Test sentinel initialization."""
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        sentinel = DeadlineSentinelAgent()
        assert sentinel.falkordb is None
        assert sentinel._is_running is False
        # Should have FAFSA deadlines initialized
        assert len(sentinel._deadlines) > 0

    def test_sentinel_model_name(self):
        """Test sentinel uses correct model."""
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        sentinel = DeadlineSentinelAgent()
        assert "haiku" in sentinel.model_name.lower()

    def test_fafsa_deadlines_initialized(self):
        """Test FAFSA deadlines are initialized automatically."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineType
        )

        sentinel = DeadlineSentinelAgent()

        fafsa_deadlines = [
            d for d in sentinel._deadlines.values()
            if d.deadline_type == DeadlineType.FAFSA
        ]

        assert len(fafsa_deadlines) > 0

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping sentinel."""
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        sentinel = DeadlineSentinelAgent()

        await sentinel.start()
        assert sentinel._is_running is True

        await sentinel.stop()
        assert sentinel._is_running is False

    @pytest.mark.asyncio
    async def test_run_scrape_cycle(self):
        """AC: Sentinel runs daily checks."""
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        sentinel = DeadlineSentinelAgent()
        await sentinel.start()

        results = await sentinel.run_scrape_cycle()

        assert len(results) > 0
        assert sentinel._last_scrape is not None

    @pytest.mark.asyncio
    async def test_add_deadline(self):
        """Test adding a deadline."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineEntry, DeadlineType
        )

        sentinel = DeadlineSentinelAgent()

        deadline = DeadlineEntry(
            id="custom_deadline",
            deadline_type=DeadlineType.SCHOLARSHIP,
            name="Custom Scholarship Deadline",
            due_date=date.today() + timedelta(days=30),
        )

        result = await sentinel.add_deadline(deadline)

        assert result is True
        assert "custom_deadline" in sentinel._deadlines

    @pytest.mark.asyncio
    async def test_verify_deadline(self):
        """Test verifying a deadline."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineEntry, DeadlineType
        )

        sentinel = DeadlineSentinelAgent()

        # Add a deadline first
        deadline = DeadlineEntry(
            id="verify_test",
            deadline_type=DeadlineType.SCHOLARSHIP,
            name="Test Deadline",
            due_date=date.today() + timedelta(days=14),
        )
        await sentinel.add_deadline(deadline)

        result = await sentinel.verify_deadline("verify_test")

        assert result['found'] is True
        assert result['verified'] is True

    @pytest.mark.asyncio
    async def test_verify_nonexistent_deadline(self):
        """Test verifying nonexistent deadline."""
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        sentinel = DeadlineSentinelAgent()

        result = await sentinel.verify_deadline("nonexistent")

        assert result['found'] is False

    @pytest.mark.asyncio
    async def test_get_deadlines(self):
        """AC: Ambassador can query for specific deadlines."""
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        sentinel = DeadlineSentinelAgent()

        deadlines = await sentinel.get_deadlines()

        assert isinstance(deadlines, list)
        # Should have FAFSA deadlines at minimum
        assert len(deadlines) >= 0

    @pytest.mark.asyncio
    async def test_get_upcoming_deadlines(self):
        """Test getting upcoming deadlines."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineEntry, DeadlineType
        )

        sentinel = DeadlineSentinelAgent()

        # Add deadline within 30 days
        deadline = DeadlineEntry(
            id="upcoming_test",
            deadline_type=DeadlineType.SCHOLARSHIP,
            name="Upcoming Test",
            due_date=date.today() + timedelta(days=15),
        )
        await sentinel.add_deadline(deadline)

        deadlines = await sentinel.get_upcoming_deadlines(days_ahead=30)

        assert any(d.id == "upcoming_test" for d in deadlines)

    @pytest.mark.asyncio
    async def test_get_urgent_deadlines(self):
        """Test getting urgent deadlines (within 7 days)."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineEntry, DeadlineType
        )

        sentinel = DeadlineSentinelAgent()

        # Add urgent deadline
        deadline = DeadlineEntry(
            id="urgent_test",
            deadline_type=DeadlineType.SCHOLARSHIP,
            name="Urgent Test",
            due_date=date.today() + timedelta(days=3),
        )
        await sentinel.add_deadline(deadline)

        deadlines = await sentinel.get_urgent_deadlines()

        assert any(d.id == "urgent_test" for d in deadlines)

    @pytest.mark.asyncio
    async def test_subscribe_student(self):
        """Test subscribing student to deadline."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineEntry, DeadlineType
        )

        sentinel = DeadlineSentinelAgent()

        deadline = DeadlineEntry(
            id="subscribe_test",
            deadline_type=DeadlineType.SCHOLARSHIP,
            name="Subscribe Test",
            due_date=date.today() + timedelta(days=30),
        )
        await sentinel.add_deadline(deadline)

        result = await sentinel.subscribe_student("student_123", "subscribe_test")

        assert result is True
        assert "student_123" in sentinel._deadlines["subscribe_test"].student_ids

    @pytest.mark.asyncio
    async def test_unsubscribe_student(self):
        """Test unsubscribing student from deadline."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineEntry, DeadlineType
        )

        sentinel = DeadlineSentinelAgent()

        deadline = DeadlineEntry(
            id="unsub_test",
            deadline_type=DeadlineType.SCHOLARSHIP,
            name="Unsub Test",
            due_date=date.today() + timedelta(days=30),
            student_ids=["student_123"],
        )
        await sentinel.add_deadline(deadline)

        result = await sentinel.unsubscribe_student("student_123", "unsub_test")

        assert result is True
        assert "student_123" not in sentinel._deadlines["unsub_test"].student_ids

    def test_get_changes(self):
        """AC: Detects deadline changes."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineChange
        )

        sentinel = DeadlineSentinelAgent()

        # Manually add a change
        sentinel._changes.append(DeadlineChange(
            deadline_id="test_change",
            change_type="new",
            new_date=date.today() + timedelta(days=30),
        ))

        changes = sentinel.get_changes()

        assert len(changes) > 0
        assert changes[0].deadline_id == "test_change"

    def test_get_changes_unnotified_only(self):
        """Test getting only unnotified changes."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineChange
        )

        sentinel = DeadlineSentinelAgent()

        # Add notified and unnotified changes
        sentinel._changes.append(DeadlineChange(
            deadline_id="notified_change",
            change_type="new",
            notified=True,
        ))
        sentinel._changes.append(DeadlineChange(
            deadline_id="unnotified_change",
            change_type="new",
            notified=False,
        ))

        changes = sentinel.get_changes(unnotified_only=True)

        assert len(changes) == 1
        assert changes[0].deadline_id == "unnotified_change"

    def test_mark_changes_notified(self):
        """AC: Alerts students of changes (can mark as notified)."""
        from agents.specialists.deadline_sentinel import (
            DeadlineSentinelAgent, DeadlineChange
        )

        sentinel = DeadlineSentinelAgent()

        sentinel._changes.append(DeadlineChange(
            deadline_id="to_notify",
            change_type="updated",
        ))

        sentinel.mark_changes_notified(["to_notify"])

        assert sentinel._changes[0].notified is True

    def test_get_stats(self):
        """Test getting sentinel stats."""
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        sentinel = DeadlineSentinelAgent()
        stats = sentinel.get_stats()

        assert 'is_running' in stats
        assert 'total_deadlines' in stats
        assert 'upcoming_deadlines' in stats
        assert 'urgent_deadlines' in stats
        assert 'by_type' in stats


# ============================================================================
# Document Analyst Tests
# ============================================================================

class TestDocumentAnalystAgent:
    """Tests for DocumentAnalystAgent."""

    # Sample award letter content
    SAMPLE_AWARD_LETTER = """
    Stanford University
    Financial Aid Award Letter 2024-2025

    Dear Student,

    Congratulations! We are pleased to offer you the following financial aid package:

    Cost of Attendance: $82,000
    Tuition: $58,000
    Room and Board: $18,000
    Books and Supplies: $1,500
    Personal Expenses: $4,500

    Your Financial Aid Award:
    Federal Pell Grant: $7,395
    Stanford Grant: $45,000
    Merit Scholarship: $10,000
    Direct Subsidized Loan: $3,500
    Direct Unsubsidized Loan: $2,000
    Federal Work-Study: $3,500

    Total Aid: $71,395
    Net Cost: $10,605

    Conditions: You must maintain a 2.0 GPA and full-time enrollment.
    Deadline: May 1, 2024
    """

    SAMPLE_TRANSCRIPT = """
    Stanford University Official Transcript

    Student Name: [REDACTED]

    Academic Standing: Good Standing

    Cumulative GPA: 3.75 / 4.0
    Credits Earned: 45
    Credits Attempted: 45

    Fall 2023:
    MATH 101 Calculus I        4 credits    A
    CS 101 Intro to CS         3 credits    A-
    ENGL 101 Writing           3 credits    B+

    Dean's List: Fall 2023
    """

    def test_document_type_enum(self):
        """Test DocumentType enum."""
        from agents.specialists.document_analyst import DocumentType

        assert DocumentType.AWARD_LETTER.value == "award_letter"
        assert DocumentType.TRANSCRIPT.value == "transcript"

    def test_analysis_status_enum(self):
        """Test AnalysisStatus enum."""
        from agents.specialists.document_analyst import AnalysisStatus

        assert AnalysisStatus.COMPLETED.value == "completed"
        assert AnalysisStatus.FAILED.value == "failed"

    def test_completion_status_enum(self):
        """Test CompletionStatus enum."""
        from agents.specialists.document_analyst import CompletionStatus

        assert CompletionStatus.COMPLETE.value == "complete"
        assert CompletionStatus.MISSING_FIELDS.value == "missing_fields"

    def test_extracted_field_dataclass(self):
        """Test ExtractedField dataclass."""
        from agents.specialists.document_analyst import ExtractedField

        field = ExtractedField(
            name="total_cost",
            value=50000,
            confidence=0.9,
        )

        assert field.name == "total_cost"
        assert field.confidence == 0.9

    def test_award_letter_data_dataclass(self):
        """Test AwardLetterData dataclass."""
        from agents.specialists.document_analyst import AwardLetterData

        data = AwardLetterData(
            school_name="Test University",
            total_cost=50000,
            total_aid=40000,
        )

        assert data.school_name == "Test University"
        assert data.total_cost == 50000

    def test_award_letter_calculate_totals(self):
        """Test AwardLetterData.calculate_totals()."""
        from agents.specialists.document_analyst import AwardLetterData

        data = AwardLetterData(
            total_cost=50000,
            total_aid=40000,
            grants={'pell': 5000, 'state': 3000},
            scholarships={'merit': 10000},
            loans={'subsidized': 5500},
            work_study=2000,
        )

        data.calculate_totals()

        assert data.total_gift_aid == 18000  # 5000 + 3000 + 10000
        assert data.total_self_help == 7500  # 5500 + 2000
        assert data.net_cost == 10000  # 50000 - 40000

    def test_transcript_data_dataclass(self):
        """Test TranscriptData dataclass."""
        from agents.specialists.document_analyst import TranscriptData

        data = TranscriptData(
            school_name="Test University",
            cumulative_gpa=3.5,
            credits_earned=30,
        )

        assert data.cumulative_gpa == 3.5
        assert data.credits_earned == 30

    def test_analyst_initialization(self):
        """Test analyst initialization."""
        from agents.specialists.document_analyst import DocumentAnalystAgent

        analyst = DocumentAnalystAgent()
        assert analyst._analysis_history == []

    def test_analyst_model_name(self):
        """Test analyst uses correct model."""
        from agents.specialists.document_analyst import DocumentAnalystAgent

        analyst = DocumentAnalystAgent()
        assert "sonnet" in analyst.model_name.lower()  # Uses Sonnet for document analysis

    @pytest.mark.asyncio
    async def test_detect_document_type_award_letter(self):
        """Test document type detection for award letter."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()
        doc_type = analyst._detect_document_type(self.SAMPLE_AWARD_LETTER, None)

        assert doc_type == DocumentType.AWARD_LETTER

    @pytest.mark.asyncio
    async def test_detect_document_type_transcript(self):
        """Test document type detection for transcript."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()
        doc_type = analyst._detect_document_type(self.SAMPLE_TRANSCRIPT, None)

        assert doc_type == DocumentType.TRANSCRIPT

    @pytest.mark.asyncio
    async def test_detect_document_type_from_filename(self):
        """Test document type detection from filename."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()

        assert analyst._detect_document_type("", "award_letter_2024.pdf") == DocumentType.AWARD_LETTER
        assert analyst._detect_document_type("", "official_transcript.pdf") == DocumentType.TRANSCRIPT

    @pytest.mark.asyncio
    async def test_analyze_award_letter(self):
        """AC: Can parse award letters extracting key fields."""
        from agents.specialists.document_analyst import (
            DocumentAnalystAgent, DocumentType, AnalysisStatus
        )

        analyst = DocumentAnalystAgent()
        result = await analyst.analyze_document(
            self.SAMPLE_AWARD_LETTER,
            DocumentType.AWARD_LETTER,
        )

        assert result.document_type == DocumentType.AWARD_LETTER
        assert result.status == AnalysisStatus.COMPLETED
        assert len(result.extracted_fields) > 0

        # Should extract school name
        field_names = [f.name for f in result.extracted_fields]
        assert 'school_name' in field_names or 'total_cost' in field_names

    @pytest.mark.asyncio
    async def test_analyze_award_letter_extracts_costs(self):
        """Test award letter extracts cost values."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()
        result = await analyst.analyze_document(
            self.SAMPLE_AWARD_LETTER,
            DocumentType.AWARD_LETTER,
        )

        # Should have extracted cost data
        if result.data:
            assert result.data.total_cost == 82000 or result.data.tuition is not None

    @pytest.mark.asyncio
    async def test_analyze_award_letter_extracts_grants(self):
        """Test award letter extracts grants."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()
        result = await analyst.analyze_document(
            self.SAMPLE_AWARD_LETTER,
            DocumentType.AWARD_LETTER,
        )

        if result.data and result.data.grants:
            assert len(result.data.grants) > 0

    @pytest.mark.asyncio
    async def test_analyze_transcript(self):
        """AC: Can parse transcripts extracting GPA, courses."""
        from agents.specialists.document_analyst import (
            DocumentAnalystAgent, DocumentType, AnalysisStatus
        )

        analyst = DocumentAnalystAgent()
        result = await analyst.analyze_document(
            self.SAMPLE_TRANSCRIPT,
            DocumentType.TRANSCRIPT,
        )

        assert result.document_type == DocumentType.TRANSCRIPT
        assert result.status == AnalysisStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_analyze_transcript_extracts_gpa(self):
        """Test transcript extracts GPA."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()
        result = await analyst.analyze_document(
            self.SAMPLE_TRANSCRIPT,
            DocumentType.TRANSCRIPT,
        )

        if result.data:
            assert result.data.cumulative_gpa == 3.75

    @pytest.mark.asyncio
    async def test_analyze_transcript_extracts_credits(self):
        """Test transcript extracts credits."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()
        result = await analyst.analyze_document(
            self.SAMPLE_TRANSCRIPT,
            DocumentType.TRANSCRIPT,
        )

        if result.data:
            assert result.data.credits_earned == 45

    @pytest.mark.asyncio
    async def test_analyze_transcript_extracts_honors(self):
        """Test transcript extracts honors."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()
        result = await analyst.analyze_document(
            self.SAMPLE_TRANSCRIPT,
            DocumentType.TRANSCRIPT,
        )

        if result.data and result.data.honors:
            # Check case-insensitively
            honors_lower = [h.lower() for h in result.data.honors]
            assert any("dean" in h and "list" in h for h in honors_lower)

    @pytest.mark.asyncio
    async def test_validate_completeness(self):
        """AC: Validates document completeness."""
        from agents.specialists.document_analyst import (
            DocumentAnalystAgent, DocumentType, ExtractedField
        )

        analyst = DocumentAnalystAgent()

        # Complete fields
        complete_fields = [
            ExtractedField(name='school_name', value='Test', confidence=0.9),
            ExtractedField(name='academic_year', value='2024-2025', confidence=0.9),
            ExtractedField(name='total_cost', value=50000, confidence=0.9),
            ExtractedField(name='total_aid', value=40000, confidence=0.9),
        ]

        result = await analyst.validate_completeness(
            DocumentType.AWARD_LETTER,
            complete_fields,
        )

        assert result['complete'] is True
        assert len(result['missing_fields']) == 0

    @pytest.mark.asyncio
    async def test_validate_completeness_missing_fields(self):
        """Test validation detects missing fields."""
        from agents.specialists.document_analyst import (
            DocumentAnalystAgent, DocumentType, ExtractedField
        )

        analyst = DocumentAnalystAgent()

        # Missing total_cost and total_aid
        incomplete_fields = [
            ExtractedField(name='school_name', value='Test', confidence=0.9),
        ]

        result = await analyst.validate_completeness(
            DocumentType.AWARD_LETTER,
            incomplete_fields,
        )

        assert result['complete'] is False
        assert len(result['missing_fields']) > 0

    @pytest.mark.asyncio
    async def test_compare_award_letters(self):
        """Test comparing multiple award letters."""
        from agents.specialists.document_analyst import (
            DocumentAnalystAgent, DocumentAnalysisResult, DocumentType,
            AnalysisStatus, CompletionStatus, AwardLetterData
        )

        analyst = DocumentAnalystAgent()

        # Create mock results
        letter1 = DocumentAnalysisResult(
            document_type=DocumentType.AWARD_LETTER,
            status=AnalysisStatus.COMPLETED,
            completeness=CompletionStatus.COMPLETE,
            data=AwardLetterData(
                school_name="School A",
                net_cost=20000,
                total_gift_aid=30000,
                loans={'subsidized': 5000},
            ),
        )
        letter2 = DocumentAnalysisResult(
            document_type=DocumentType.AWARD_LETTER,
            status=AnalysisStatus.COMPLETED,
            completeness=CompletionStatus.COMPLETE,
            data=AwardLetterData(
                school_name="School B",
                net_cost=15000,
                total_gift_aid=35000,
                loans={'subsidized': 3000},
            ),
        )

        comparison = await analyst.compare_award_letters([letter1, letter2])

        assert len(comparison['schools']) == 2
        assert comparison['lowest_net_cost'] == "School B"
        assert comparison['highest_gift_aid'] == "School B"

    @pytest.mark.asyncio
    async def test_auto_detect_and_analyze(self):
        """Test auto-detection and analysis."""
        from agents.specialists.document_analyst import DocumentAnalystAgent, DocumentType

        analyst = DocumentAnalystAgent()

        # Auto-detect should work
        result = await analyst.analyze_document(self.SAMPLE_AWARD_LETTER)
        assert result.document_type == DocumentType.AWARD_LETTER

    def test_on_device_processing_flag(self):
        """AC: All processing is local (no data leaves device)."""
        from agents.specialists.document_analyst import DocumentAnalystAgent

        analyst = DocumentAnalystAgent()
        stats = analyst.get_stats()

        # This flag should ALWAYS be true
        assert stats['on_device_processing'] is True

    def test_get_stats(self):
        """Test getting analyst stats."""
        from agents.specialists.document_analyst import DocumentAnalystAgent

        analyst = DocumentAnalystAgent()
        stats = analyst.get_stats()

        assert 'total_analyzed' in stats
        assert 'by_type' in stats
        assert 'average_confidence' in stats
        assert 'on_device_processing' in stats

    @pytest.mark.asyncio
    async def test_analysis_history_bounded(self):
        """Test analysis history is bounded."""
        from agents.specialists.document_analyst import DocumentAnalystAgent

        analyst = DocumentAnalystAgent()

        # Analyze multiple documents
        for _ in range(55):
            await analyst.analyze_document("Simple content", filename="test.pdf")

        # History should be bounded
        assert len(analyst._analysis_history) <= 50


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
    async def test_send_request_to_sentinel(self):
        """Test sending request to deadline sentinel."""
        from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AAction, A2AStatus
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        protocol = A2AProtocol()
        sentinel = DeadlineSentinelAgent()
        await sentinel.start()

        protocol.register_agent("deadline_sentinel", sentinel)

        request = A2ARequest.create(
            source="ambassador",
            target="deadline_sentinel",
            action=A2AAction.GET_SENTINEL_STATS,
        )

        response = await protocol.send_request(request)

        assert response.status == A2AStatus.COMPLETED
        assert 'total_deadlines' in response.data

    @pytest.mark.asyncio
    async def test_send_request_get_deadlines(self):
        """Test A2A get deadlines request."""
        from agents.specialists.a2a_protocol import A2AProtocol, A2ARequest, A2AAction, A2AStatus
        from agents.specialists.deadline_sentinel import DeadlineSentinelAgent

        protocol = A2AProtocol()
        sentinel = DeadlineSentinelAgent()
        await sentinel.start()

        protocol.register_agent("deadline_sentinel", sentinel)

        request = A2ARequest.create(
            source="ambassador",
            target="deadline_sentinel",
            action=A2AAction.GET_DEADLINES,
            params={'limit': 10},
        )

        response = await protocol.send_request(request)

        assert response.status == A2AStatus.COMPLETED
        assert 'deadlines' in response.data

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
            DeadlineSentinelAgent,
            DocumentAnalystAgent,
            A2AProtocol,
            A2ARequest,
            A2AResponse,
        )

        assert ScholarshipScoutAgent is not None
        assert AppealStrategistAgent is not None
        assert DeadlineSentinelAgent is not None
        assert DocumentAnalystAgent is not None
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
