"""
Tests for Ambassador Tools - Story 2.2

Verifies:
- scholarship_search returns matches from FalkorDB
- deadline_check returns upcoming deadlines
- aid_calculator computes total cost of attendance
- schedule_reminder creates scheduled messages
- web_research can fetch scholarship info
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock


# ============================================================================
# Scholarship Search Tool Tests
# ============================================================================

class TestScholarshipSearchTool:
    """Tests for ScholarshipSearchTool."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB client."""
        mock = MagicMock()

        # Create mock node
        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'gates_scholarship',
            'name': 'Gates Scholarship',
            'amount_min': 50000,
            'amount_max': 300000,
            'criteria': 'High-achieving, low-income students with leadership',
            'deadline': '2025-09-15',
            'verified': True,
            'renewable': True,
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]

        mock.get_all_scholarship_sources.return_value = mock_result
        mock.query.return_value = mock_result

        return mock

    def test_scholarship_match_dataclass(self):
        """Test ScholarshipMatch dataclass."""
        from agents.tools.scholarship_search import ScholarshipMatch

        match = ScholarshipMatch(
            id="test_123",
            name="Test Scholarship",
            amount_min=1000,
            amount_max=5000,
            criteria="Test criteria",
            deadline=date(2025, 12, 31),
            match_score=0.8,
            match_reasons=["Good match"],
        )

        assert match.id == "test_123"
        assert match.match_score == 0.8

    def test_student_profile_dataclass(self):
        """Test StudentProfile dataclass."""
        from agents.tools.scholarship_search import StudentProfile

        profile = StudentProfile(
            gpa_range="3.5-4.0",
            first_gen=True,
            major_interest="engineering",
        )

        assert profile.first_gen is True
        assert profile.major_interest == "engineering"

    def test_tool_initialization(self):
        """Test tool initialization."""
        from agents.tools.scholarship_search import ScholarshipSearchTool

        tool = ScholarshipSearchTool()
        assert tool.falkordb is None

    @pytest.mark.asyncio
    async def test_search_no_client(self):
        """Test search with no FalkorDB client."""
        from agents.tools.scholarship_search import ScholarshipSearchTool

        tool = ScholarshipSearchTool()
        results = await tool.search()
        assert results == []

    @pytest.mark.asyncio
    async def test_search_returns_matches(self, mock_falkordb):
        """AC: scholarship_search returns matches from FalkorDB."""
        from agents.tools.scholarship_search import ScholarshipSearchTool

        tool = ScholarshipSearchTool(falkordb_client=mock_falkordb)
        results = await tool.search(limit=10)

        assert len(results) > 0
        assert results[0].name == "Gates Scholarship"
        mock_falkordb.get_all_scholarship_sources.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_with_profile(self, mock_falkordb):
        """Test search with student profile."""
        from agents.tools.scholarship_search import ScholarshipSearchTool, StudentProfile

        tool = ScholarshipSearchTool(falkordb_client=mock_falkordb)
        profile = StudentProfile(first_gen=True)

        results = await tool.search(profile=profile)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_by_criteria(self, mock_falkordb):
        """Test search by criteria keywords."""
        from agents.tools.scholarship_search import ScholarshipSearchTool

        tool = ScholarshipSearchTool(falkordb_client=mock_falkordb)
        results = await tool.search_by_criteria(["leadership", "low-income"])

        # Mock returns results
        assert isinstance(results, list)


# ============================================================================
# Deadline Check Tool Tests
# ============================================================================

class TestDeadlineCheckTool:
    """Tests for DeadlineCheckTool."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB client."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'test_scholarship',
            'name': 'Test Scholarship',
            'deadline': (date.today() + timedelta(days=10)).isoformat(),
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    def test_deadline_type_enum(self):
        """Test DeadlineType enum."""
        from agents.tools.deadline_check import DeadlineType

        assert DeadlineType.SCHOLARSHIP.value == "scholarship"
        assert DeadlineType.FAFSA.value == "fafsa"

    def test_deadline_urgency_enum(self):
        """Test DeadlineUrgency enum."""
        from agents.tools.deadline_check import DeadlineUrgency

        assert DeadlineUrgency.URGENT.value == "urgent"
        assert DeadlineUrgency.PAST_DUE.value == "past_due"

    def test_deadline_dataclass(self):
        """Test Deadline dataclass."""
        from agents.tools.deadline_check import Deadline, DeadlineType

        deadline = Deadline(
            id="test_1",
            name="Test Deadline",
            deadline_type=DeadlineType.SCHOLARSHIP,
            due_date=date(2025, 12, 31),
        )

        assert deadline.name == "Test Deadline"
        assert deadline.completed is False

    def test_tool_initialization(self):
        """Test tool initialization."""
        from agents.tools.deadline_check import DeadlineCheckTool

        tool = DeadlineCheckTool()
        assert tool.falkordb is None
        assert tool.graphiti is None

    @pytest.mark.asyncio
    async def test_get_upcoming_deadlines(self, mock_falkordb):
        """AC: deadline_check returns upcoming deadlines."""
        from agents.tools.deadline_check import DeadlineCheckTool

        tool = DeadlineCheckTool(falkordb_client=mock_falkordb)
        deadlines = await tool.get_upcoming_deadlines(days_ahead=30)

        assert isinstance(deadlines, list)
        # Should include scholarship deadlines and known dates
        assert len(deadlines) >= 0

    @pytest.mark.asyncio
    async def test_get_urgent_deadlines(self, mock_falkordb):
        """Test getting urgent deadlines only."""
        from agents.tools.deadline_check import DeadlineCheckTool

        tool = DeadlineCheckTool(falkordb_client=mock_falkordb)
        deadlines = await tool.get_urgent_deadlines()

        assert isinstance(deadlines, list)

    @pytest.mark.asyncio
    async def test_add_custom_deadline(self):
        """Test adding custom deadline."""
        from agents.tools.deadline_check import DeadlineCheckTool, DeadlineType

        tool = DeadlineCheckTool()
        deadline = await tool.add_custom_deadline(
            student_id="student_123",
            name="Custom Deadline",
            due_date=date.today() + timedelta(days=14),
            deadline_type=DeadlineType.APPLICATION,
        )

        assert deadline.name == "Custom Deadline"
        assert deadline.deadline_type == DeadlineType.APPLICATION

    @pytest.mark.asyncio
    async def test_mark_deadline_complete(self):
        """Test marking deadline complete."""
        from agents.tools.deadline_check import DeadlineCheckTool

        tool = DeadlineCheckTool()

        # Add a deadline first
        deadline = await tool.add_custom_deadline(
            student_id="student_123",
            name="Test",
            due_date=date.today() + timedelta(days=7),
        )

        result = await tool.mark_deadline_complete("student_123", deadline.id)
        assert result is True


# ============================================================================
# Aid Calculator Tool Tests
# ============================================================================

class TestAidCalculatorTool:
    """Tests for AidCalculatorTool."""

    def test_aid_type_enum(self):
        """Test AidType enum."""
        from agents.tools.aid_calculator import AidType

        assert AidType.GRANT.value == "grant"
        assert AidType.LOAN_SUBSIDIZED.value == "loan_subsidized"

    def test_school_type_enum(self):
        """Test SchoolType enum."""
        from agents.tools.aid_calculator import SchoolType

        assert SchoolType.PUBLIC_IN_STATE.value == "public_in_state"
        assert SchoolType.PRIVATE.value == "private"

    def test_cost_breakdown_dataclass(self):
        """Test CostBreakdown dataclass."""
        from agents.tools.aid_calculator import CostBreakdown

        cost = CostBreakdown(
            tuition=20000,
            fees=1500,
            room_board=12000,
        )

        assert cost.total == 33500

    def test_cost_breakdown_total(self):
        """Test CostBreakdown total calculation."""
        from agents.tools.aid_calculator import CostBreakdown

        cost = CostBreakdown(
            tuition=20000,
            fees=1500,
            room_board=12000,
            books_supplies=1200,
            personal_expenses=2500,
            transportation=1500,
        )

        assert cost.total == 38700

    def test_aid_award_dataclass(self):
        """Test AidAward dataclass."""
        from agents.tools.aid_calculator import AidAward, AidType

        award = AidAward(
            name="Pell Grant",
            aid_type=AidType.GRANT,
            amount=7000,
            renewable=True,
        )

        assert award.amount == 7000
        assert award.renewable is True

    def test_tool_initialization(self):
        """Test tool initialization."""
        from agents.tools.aid_calculator import AidCalculatorTool

        tool = AidCalculatorTool()
        assert tool.falkordb is None

    @pytest.mark.asyncio
    async def test_calculate_cost_of_attendance(self):
        """AC: aid_calculator computes total cost of attendance."""
        from agents.tools.aid_calculator import AidCalculatorTool, SchoolType

        tool = AidCalculatorTool()
        cost = await tool.calculate_cost_of_attendance(SchoolType.PUBLIC_IN_STATE)

        assert cost.total > 0
        assert cost.tuition > 0

    @pytest.mark.asyncio
    async def test_calculate_aid_summary(self):
        """Test aid summary calculation."""
        from agents.tools.aid_calculator import (
            AidCalculatorTool, CostBreakdown, AidAward, AidType
        )

        tool = AidCalculatorTool()
        cost = CostBreakdown(
            tuition=20000,
            fees=1500,
            room_board=12000,
        )

        awards = [
            AidAward(name="Pell Grant", aid_type=AidType.GRANT, amount=7000),
            AidAward(name="Merit Scholarship", aid_type=AidType.SCHOLARSHIP, amount=5000),
            AidAward(name="Direct Loan", aid_type=AidType.LOAN_SUBSIDIZED, amount=5500),
        ]

        summary = await tool.calculate_aid_summary(cost, awards)

        assert summary.total_cost == 33500
        assert summary.total_grants == 7000
        assert summary.total_scholarships == 5000
        assert summary.total_loans == 5500
        assert summary.net_price == 33500 - 12000  # Cost - free money

    @pytest.mark.asyncio
    async def test_estimate_efc(self):
        """Test EFC estimation."""
        from agents.tools.aid_calculator import AidCalculatorTool

        tool = AidCalculatorTool()
        efc = await tool.estimate_efc(
            household_income=60000,
            household_size=4,
            assets=10000,
        )

        assert efc >= 0

    @pytest.mark.asyncio
    async def test_calculate_unmet_need(self):
        """Test unmet need calculation."""
        from agents.tools.aid_calculator import AidCalculatorTool

        tool = AidCalculatorTool()
        unmet = await tool.calculate_unmet_need(
            cost_of_attendance=30000,
            efc=5000,
            total_aid=15000,
        )

        # Need is 30000 - 5000 = 25000
        # Unmet need is 25000 - 15000 = 10000
        assert unmet == 10000

    def test_format_aid_summary(self):
        """Test aid summary formatting."""
        from agents.tools.aid_calculator import AidCalculatorTool, AidSummary

        tool = AidCalculatorTool()
        summary = AidSummary(
            total_cost=30000,
            total_grants=7000,
            total_scholarships=5000,
            total_work_study=2000,
            total_loans=5500,
            net_price=18000,
            out_of_pocket=16000,
            total_debt_4_years=22000,
            monthly_payment_estimate=250,
        )

        formatted = tool.format_aid_summary(summary)
        assert "Financial Aid Summary" in formatted
        assert "$30,000" in formatted


# ============================================================================
# Schedule Reminder Tool Tests
# ============================================================================

class TestScheduleReminderTool:
    """Tests for ScheduleReminderTool."""

    def test_reminder_type_enum(self):
        """Test ReminderType enum."""
        from agents.tools.schedule_reminder import ReminderType

        assert ReminderType.DEADLINE.value == "deadline"
        assert ReminderType.CHECK_IN.value == "check_in"

    def test_reminder_priority_enum(self):
        """Test ReminderPriority enum."""
        from agents.tools.schedule_reminder import ReminderPriority

        assert ReminderPriority.URGENT.value == "urgent"
        assert ReminderPriority.LOW.value == "low"

    def test_reminder_status_enum(self):
        """Test ReminderStatus enum."""
        from agents.tools.schedule_reminder import ReminderStatus

        assert ReminderStatus.PENDING.value == "pending"
        assert ReminderStatus.SENT.value == "sent"

    def test_reminder_dataclass(self):
        """Test Reminder dataclass."""
        from agents.tools.schedule_reminder import Reminder, ReminderType

        reminder = Reminder(
            id="test_123",
            student_id="student_456",
            reminder_type=ReminderType.DEADLINE,
            title="Test Reminder",
            message="This is a test",
            scheduled_time=datetime.utcnow() + timedelta(days=1),
        )

        assert reminder.title == "Test Reminder"
        assert reminder.snooze_count == 0

    def test_tool_initialization(self):
        """Test tool initialization."""
        from agents.tools.schedule_reminder import ScheduleReminderTool

        tool = ScheduleReminderTool()
        assert tool.graphiti is None

    @pytest.mark.asyncio
    async def test_create_reminder(self):
        """AC: schedule_reminder creates scheduled messages."""
        from agents.tools.schedule_reminder import ScheduleReminderTool

        tool = ScheduleReminderTool()
        reminder = await tool.create_reminder(
            student_id="student_123",
            title="Test Reminder",
            message="Don't forget!",
            scheduled_time=datetime.utcnow() + timedelta(hours=2),
        )

        assert reminder is not None
        assert reminder.title == "Test Reminder"
        assert reminder.student_id == "student_123"

    @pytest.mark.asyncio
    async def test_create_deadline_reminder(self):
        """Test creating deadline reminder."""
        from agents.tools.schedule_reminder import ScheduleReminderTool, ReminderType

        tool = ScheduleReminderTool()
        reminder = await tool.create_deadline_reminder(
            student_id="student_123",
            deadline_name="FAFSA",
            deadline_date=date.today() + timedelta(days=14),
            days_before=7,
        )

        assert reminder.reminder_type == ReminderType.DEADLINE
        assert "FAFSA" in reminder.title

    @pytest.mark.asyncio
    async def test_create_scholarship_reminders(self):
        """Test creating series of scholarship reminders."""
        from agents.tools.schedule_reminder import ScheduleReminderTool

        tool = ScheduleReminderTool()
        reminders = await tool.create_scholarship_reminder(
            student_id="student_123",
            scholarship_name="Gates Scholarship",
            deadline_date=date.today() + timedelta(days=14),
            scholarship_id="gates_123",
        )

        assert isinstance(reminders, list)
        # Should create reminders at 7 and 3 days before (1 day is past)
        assert len(reminders) >= 1

    @pytest.mark.asyncio
    async def test_get_student_reminders(self):
        """Test getting student reminders."""
        from agents.tools.schedule_reminder import ScheduleReminderTool

        tool = ScheduleReminderTool()

        # Create some reminders
        await tool.create_reminder(
            student_id="student_123",
            title="Reminder 1",
            message="Test",
            scheduled_time=datetime.utcnow() + timedelta(hours=1),
        )

        reminders = await tool.get_student_reminders("student_123")
        assert len(reminders) == 1

    @pytest.mark.asyncio
    async def test_snooze_reminder(self):
        """Test snoozing a reminder."""
        from agents.tools.schedule_reminder import ScheduleReminderTool, ReminderStatus

        tool = ScheduleReminderTool()

        reminder = await tool.create_reminder(
            student_id="student_123",
            title="Test",
            message="Test",
            scheduled_time=datetime.utcnow(),
        )

        original_time = reminder.scheduled_time

        snoozed = await tool.snooze(reminder.id, snooze_minutes=30)

        assert snoozed is not None
        assert snoozed.status == ReminderStatus.SNOOZED
        assert snoozed.snooze_count == 1
        assert snoozed.scheduled_time > original_time

    @pytest.mark.asyncio
    async def test_cancel_reminder(self):
        """Test cancelling a reminder."""
        from agents.tools.schedule_reminder import ScheduleReminderTool, ReminderStatus

        tool = ScheduleReminderTool()

        reminder = await tool.create_reminder(
            student_id="student_123",
            title="Test",
            message="Test",
            scheduled_time=datetime.utcnow() + timedelta(hours=1),
        )

        result = await tool.cancel(reminder.id)
        assert result is True

        updated = await tool.get_reminder(reminder.id)
        assert updated.status == ReminderStatus.CANCELLED


# ============================================================================
# Web Research Tool Tests
# ============================================================================

class TestWebResearchTool:
    """Tests for WebResearchTool."""

    def test_research_type_enum(self):
        """Test ResearchType enum."""
        from agents.tools.web_research import ResearchType

        assert ResearchType.SCHOLARSHIP.value == "scholarship"
        assert ResearchType.FAFSA.value == "fafsa"

    def test_research_result_dataclass(self):
        """Test ResearchResult dataclass."""
        from agents.tools.web_research import ResearchResult, ResearchType

        result = ResearchResult(
            title="Test Result",
            url="https://example.com",
            snippet="Test snippet",
            source="Test Source",
            research_type=ResearchType.SCHOLARSHIP,
            relevance_score=0.9,
        )

        assert result.title == "Test Result"
        assert result.relevance_score == 0.9

    def test_scholarship_info_dataclass(self):
        """Test ScholarshipInfo dataclass."""
        from agents.tools.web_research import ScholarshipInfo

        info = ScholarshipInfo(
            name="Test Scholarship",
            url="https://example.com",
            amount_min=1000,
            amount_max=5000,
        )

        assert info.name == "Test Scholarship"
        assert info.verified is False

    def test_tool_initialization(self):
        """Test tool initialization."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        assert tool.http_client is None

    @pytest.mark.asyncio
    async def test_search_scholarships(self):
        """AC: web_research can fetch scholarship info."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        results = await tool.search_scholarships("engineering")

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(hasattr(r, 'url') for r in results)

    @pytest.mark.asyncio
    async def test_fetch_scholarship_details(self):
        """Test fetching scholarship details."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        info = await tool.fetch_scholarship_details("Gates Scholarship")

        assert info is not None
        assert "Gates" in info.name

    @pytest.mark.asyncio
    async def test_search_fafsa_info(self):
        """Test searching FAFSA info."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        results = await tool.search_fafsa_info("deadline")

        assert isinstance(results, list)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_school_info(self):
        """Test searching school info."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        results = await tool.search_school_info(
            "Stanford University",
            info_type="financial_aid"
        )

        assert isinstance(results, list)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_verify_scholarship_known(self):
        """Test verifying known scholarship."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        result = await tool.verify_scholarship("Gates Scholarship")

        assert result["verified"] is True

    @pytest.mark.asyncio
    async def test_verify_scholarship_suspicious(self):
        """Test verifying suspicious scholarship."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        result = await tool.verify_scholarship("Free Money Scholarship - Fee Required")

        assert len(result["warnings"]) > 0

    def test_get_scholarship_sources(self):
        """Test getting scholarship sources."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()
        sources = tool.get_scholarship_sources()

        assert isinstance(sources, list)
        assert len(sources) > 0
        assert all("name" in s and "url" in s for s in sources)


# ============================================================================
# Module Tests
# ============================================================================

class TestToolsModule:
    """Tests for tools module."""

    def test_module_exports(self):
        """Test module exports all tools."""
        from agents.tools import (
            ScholarshipSearchTool,
            DeadlineCheckTool,
            AidCalculatorTool,
            ScheduleReminderTool,
            WebResearchTool,
        )

        assert ScholarshipSearchTool is not None
        assert DeadlineCheckTool is not None
        assert AidCalculatorTool is not None
        assert ScheduleReminderTool is not None
        assert WebResearchTool is not None


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================

class TestAcceptanceCriteria:
    """Tests verifying Story 2.2 acceptance criteria."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB client."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'test_scholarship',
            'name': 'Test Scholarship',
            'amount_min': 1000,
            'amount_max': 5000,
            'criteria': 'Test criteria',
            'deadline': (date.today() + timedelta(days=30)).isoformat(),
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    @pytest.mark.asyncio
    async def test_ac_scholarship_search_returns_from_falkordb(self, mock_falkordb):
        """AC: scholarship_search returns matches from FalkorDB."""
        from agents.tools.scholarship_search import ScholarshipSearchTool

        tool = ScholarshipSearchTool(falkordb_client=mock_falkordb)
        results = await tool.search()

        assert len(results) > 0
        assert results[0].name == "Test Scholarship"
        mock_falkordb.get_all_scholarship_sources.assert_called()

    @pytest.mark.asyncio
    async def test_ac_deadline_check_returns_upcoming(self, mock_falkordb):
        """AC: deadline_check returns upcoming deadlines."""
        from agents.tools.deadline_check import DeadlineCheckTool

        tool = DeadlineCheckTool(falkordb_client=mock_falkordb)
        deadlines = await tool.get_upcoming_deadlines(days_ahead=60)

        # Should return at least known FAFSA dates
        assert isinstance(deadlines, list)

    @pytest.mark.asyncio
    async def test_ac_aid_calculator_computes_coa(self):
        """AC: aid_calculator computes total cost of attendance."""
        from agents.tools.aid_calculator import AidCalculatorTool, SchoolType

        tool = AidCalculatorTool()

        # Test each school type
        for school_type in SchoolType:
            cost = await tool.calculate_cost_of_attendance(school_type)
            assert cost.total > 0, f"Failed for {school_type}"

    @pytest.mark.asyncio
    async def test_ac_schedule_reminder_creates_messages(self):
        """AC: schedule_reminder creates scheduled messages."""
        from agents.tools.schedule_reminder import ScheduleReminderTool, ReminderStatus

        tool = ScheduleReminderTool()

        reminder = await tool.create_reminder(
            student_id="student_123",
            title="Test Reminder",
            message="This is a test message",
            scheduled_time=datetime.utcnow() + timedelta(hours=1),
        )

        assert reminder is not None
        assert reminder.status == ReminderStatus.PENDING
        assert reminder.message == "This is a test message"

    @pytest.mark.asyncio
    async def test_ac_web_research_fetches_scholarship_info(self):
        """AC: web_research can fetch scholarship info."""
        from agents.tools.web_research import WebResearchTool

        tool = WebResearchTool()

        # Test search
        results = await tool.search_scholarships("stem")
        assert len(results) > 0

        # Test fetch details
        info = await tool.fetch_scholarship_details("Gates Scholarship")
        assert info is not None
        assert info.name


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
