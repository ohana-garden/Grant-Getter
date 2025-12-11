"""
Tests for Proactive Triggers - Story 2.3

Verifies:
- System detects deadline within 7 days, queues reminder
- System detects new scholarship match, queues conversation
- System detects 5 days inactive, queues check-in
"""

import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, MagicMock, AsyncMock


# ============================================================================
# Scanner Tests
# ============================================================================

class TestDeadlineScanner:
    """Tests for DeadlineScanner."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB with upcoming deadlines."""
        mock = MagicMock()

        # Create mock deadline within 7 days
        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'test_scholarship',
            'name': 'Test Scholarship',
            'deadline': (date.today() + timedelta(days=5)).isoformat(),
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    @pytest.fixture
    def mock_falkordb_urgent(self):
        """Create mock FalkorDB with urgent deadline."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'urgent_scholarship',
            'name': 'Urgent Scholarship',
            'deadline': (date.today() + timedelta(days=1)).isoformat(),
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    def test_trigger_priority_enum(self):
        """Test TriggerPriority enum."""
        from agents.triggers.scanner import TriggerPriority

        assert TriggerPriority.CRITICAL.value == 1
        assert TriggerPriority.HIGH.value == 2

    def test_scan_result_dataclass(self):
        """Test ScanResult dataclass."""
        from agents.triggers.scanner import ScanResult, TriggerPriority

        result = ScanResult(
            trigger_type="test",
            student_id="student_123",
            priority=TriggerPriority.HIGH,
            data={'key': 'value'},
        )

        assert result.trigger_type == "test"
        assert result.priority == TriggerPriority.HIGH

    def test_scanner_initialization(self):
        """Test scanner initialization."""
        from agents.triggers.scanner import DeadlineScanner

        scanner = DeadlineScanner()
        assert scanner.falkordb is None

    @pytest.mark.asyncio
    async def test_scan_detects_7_day_deadline(self, mock_falkordb):
        """AC: System detects deadline within 7 days."""
        from agents.triggers.scanner import DeadlineScanner, TriggerPriority

        scanner = DeadlineScanner(falkordb_client=mock_falkordb)
        results = await scanner.scan()

        assert len(results) > 0
        assert results[0].trigger_type == "deadline_approaching"
        assert results[0].priority == TriggerPriority.HIGH

    @pytest.mark.asyncio
    async def test_scan_detects_24_hour_deadline(self, mock_falkordb_urgent):
        """AC: System detects deadline within 24 hours as CRITICAL."""
        from agents.triggers.scanner import DeadlineScanner, TriggerPriority

        scanner = DeadlineScanner(falkordb_client=mock_falkordb_urgent)
        results = await scanner.scan()

        assert len(results) > 0
        assert results[0].priority == TriggerPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_scan_for_specific_student(self, mock_falkordb):
        """Test scanning for specific student."""
        from agents.triggers.scanner import DeadlineScanner

        scanner = DeadlineScanner(falkordb_client=mock_falkordb)
        results = await scanner.scan(student_ids=["student_123"])

        # Should return results for the specific student
        for result in results:
            assert result.student_id == "student_123"

    def test_reset_triggers(self, mock_falkordb):
        """Test resetting trigger tracking."""
        from agents.triggers.scanner import DeadlineScanner

        scanner = DeadlineScanner(falkordb_client=mock_falkordb)
        scanner._triggered_deadlines["student_123"] = {"test_deadline"}

        scanner.reset_triggers("student_123")
        assert "student_123" not in scanner._triggered_deadlines


class TestScholarshipMatchScanner:
    """Tests for ScholarshipMatchScanner."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB with scholarships."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'new_scholarship',
            'name': 'New Scholarship',
            'amount_max': 15000,
            'verified': True,
            'renewable': True,
            'deadline': '2025-12-31',
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    def test_scanner_initialization(self):
        """Test scanner initialization."""
        from agents.triggers.scanner import ScholarshipMatchScanner

        scanner = ScholarshipMatchScanner()
        assert scanner.falkordb is None

    @pytest.mark.asyncio
    async def test_scan_detects_new_match(self, mock_falkordb):
        """AC: System detects new scholarship match."""
        from agents.triggers.scanner import ScholarshipMatchScanner

        scanner = ScholarshipMatchScanner(falkordb_client=mock_falkordb)
        results = await scanner.scan(
            student_ids=["student_123"],
            min_match_score=0.5,
        )

        assert len(results) > 0
        assert results[0].trigger_type == "new_scholarship_match"

    @pytest.mark.asyncio
    async def test_scan_skips_known_matches(self, mock_falkordb):
        """Test that known matches are skipped."""
        from agents.triggers.scanner import ScholarshipMatchScanner

        scanner = ScholarshipMatchScanner(falkordb_client=mock_falkordb)

        # Mark scholarship as known
        scanner.add_known_match("student_123", "new_scholarship")

        results = await scanner.scan(
            student_ids=["student_123"],
            min_match_score=0.5,
        )

        # Should not return the known scholarship
        assert len(results) == 0

    def test_reset_matches(self, mock_falkordb):
        """Test resetting match tracking."""
        from agents.triggers.scanner import ScholarshipMatchScanner

        scanner = ScholarshipMatchScanner(falkordb_client=mock_falkordb)
        scanner._previous_matches["student_123"] = {"scholarship_1"}

        scanner.reset_matches("student_123")
        assert "student_123" not in scanner._previous_matches


class TestEngagementTracker:
    """Tests for EngagementTracker."""

    def test_tracker_initialization(self):
        """Test tracker initialization."""
        from agents.triggers.scanner import EngagementTracker

        tracker = EngagementTracker()
        assert tracker.graphiti is None

    def test_record_interaction(self):
        """Test recording student interaction."""
        from agents.triggers.scanner import EngagementTracker

        tracker = EngagementTracker()
        tracker.record_interaction("student_123")

        assert "student_123" in tracker._last_interaction

    def test_get_inactive_days(self):
        """Test getting inactive days."""
        from agents.triggers.scanner import EngagementTracker

        tracker = EngagementTracker()
        tracker.record_interaction(
            "student_123",
            datetime.utcnow() - timedelta(days=7)
        )

        days = tracker.get_inactive_days("student_123")
        assert days >= 7

    @pytest.mark.asyncio
    async def test_scan_detects_5_day_inactive(self):
        """AC: System detects 5 days inactive."""
        from agents.triggers.scanner import EngagementTracker, TriggerPriority

        tracker = EngagementTracker()

        # Set last interaction 6 days ago
        tracker.record_interaction(
            "student_123",
            datetime.utcnow() - timedelta(days=6)
        )

        results = await tracker.scan(["student_123"])

        assert len(results) == 1
        assert results[0].trigger_type == "student_inactive"
        assert results[0].data['trigger_level'] == "warning"

    @pytest.mark.asyncio
    async def test_scan_detects_14_day_inactive(self):
        """Test detecting 14 day inactivity as critical."""
        from agents.triggers.scanner import EngagementTracker, TriggerPriority

        tracker = EngagementTracker()

        # Set last interaction 15 days ago
        tracker.record_interaction(
            "student_123",
            datetime.utcnow() - timedelta(days=15)
        )

        results = await tracker.scan(["student_123"])

        assert len(results) == 1
        assert results[0].data['trigger_level'] == "critical"

    @pytest.mark.asyncio
    async def test_scan_active_student_no_trigger(self):
        """Test that active students don't trigger."""
        from agents.triggers.scanner import EngagementTracker

        tracker = EngagementTracker()

        # Set recent interaction
        tracker.record_interaction("student_123")

        results = await tracker.scan(["student_123"])
        assert len(results) == 0


# ============================================================================
# Notification Queue Tests
# ============================================================================

class TestNotificationQueue:
    """Tests for NotificationQueue."""

    def test_notification_status_enum(self):
        """Test NotificationStatus enum."""
        from agents.triggers.notification_queue import NotificationStatus

        assert NotificationStatus.QUEUED.value == "queued"
        assert NotificationStatus.SENT.value == "sent"

    def test_notification_channel_enum(self):
        """Test NotificationChannel enum."""
        from agents.triggers.notification_queue import NotificationChannel

        assert NotificationChannel.SMS.value == "sms"
        assert NotificationChannel.IN_APP.value == "in_app"

    def test_notification_dataclass(self):
        """Test Notification dataclass."""
        from agents.triggers.notification_queue import (
            Notification, NotificationChannel, NotificationStatus
        )

        notification = Notification(
            id="test_123",
            student_id="student_456",
            title="Test",
            message="Test message",
            channel=NotificationChannel.SMS,
            priority=1,
            trigger_type="test",
        )

        assert notification.status == NotificationStatus.QUEUED
        assert notification.retry_count == 0

    def test_queue_initialization(self):
        """Test queue initialization."""
        from agents.triggers.notification_queue import NotificationQueue

        queue = NotificationQueue()
        assert queue.get_queue_size() == 0

    def test_enqueue_notification(self):
        """Test enqueuing a notification."""
        from agents.triggers.notification_queue import NotificationQueue

        queue = NotificationQueue()
        notification = queue.enqueue(
            student_id="student_123",
            title="Test",
            message="Test message",
            priority=2,
        )

        assert notification is not None
        assert queue.get_queue_size() == 1

    def test_dequeue_by_priority(self):
        """Test that dequeue returns highest priority first."""
        from agents.triggers.notification_queue import NotificationQueue

        queue = NotificationQueue()

        # Add low priority first
        queue.enqueue(
            student_id="student_1",
            title="Low",
            message="Low priority",
            priority=5,
        )

        # Add high priority second
        queue.enqueue(
            student_id="student_2",
            title="High",
            message="High priority",
            priority=1,
        )

        # Dequeue should return high priority
        notification = queue.dequeue()
        assert notification.priority == 1
        assert notification.title == "High"

    def test_mark_sent(self):
        """Test marking notification as sent."""
        from agents.triggers.notification_queue import (
            NotificationQueue, NotificationStatus
        )

        queue = NotificationQueue()
        notification = queue.enqueue(
            student_id="student_123",
            title="Test",
            message="Test",
            priority=1,
        )

        result = queue.mark_sent(notification.id)
        assert result is True
        assert notification.status == NotificationStatus.SENT

    def test_cancel_notification(self):
        """Test cancelling a notification."""
        from agents.triggers.notification_queue import (
            NotificationQueue, NotificationStatus
        )

        queue = NotificationQueue()
        notification = queue.enqueue(
            student_id="student_123",
            title="Test",
            message="Test",
            priority=1,
        )

        result = queue.cancel(notification.id)
        assert result is True
        assert notification.status == NotificationStatus.CANCELLED

    def test_get_student_notifications(self):
        """Test getting notifications for a student."""
        from agents.triggers.notification_queue import NotificationQueue

        queue = NotificationQueue()

        queue.enqueue(student_id="student_123", title="1", message="m", priority=1)
        queue.enqueue(student_id="student_123", title="2", message="m", priority=2)
        queue.enqueue(student_id="student_456", title="3", message="m", priority=1)

        notifications = queue.get_student_notifications("student_123")
        assert len(notifications) == 2

    def test_get_stats(self):
        """Test getting queue statistics."""
        from agents.triggers.notification_queue import NotificationQueue

        queue = NotificationQueue()
        queue.enqueue(student_id="s1", title="1", message="m", priority=1)
        queue.enqueue(student_id="s2", title="2", message="m", priority=2)

        stats = queue.get_stats()
        assert stats['total'] == 2
        assert stats['queue_size'] == 2


# ============================================================================
# Trigger Engine Tests
# ============================================================================

class TestTriggerEngine:
    """Tests for TriggerEngine."""

    @pytest.fixture
    def mock_falkordb(self):
        """Create mock FalkorDB."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'test_scholarship',
            'name': 'Test Scholarship',
            'deadline': (date.today() + timedelta(days=5)).isoformat(),
            'amount_max': 10000,
            'verified': True,
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    def test_action_type_enum(self):
        """Test ActionType enum."""
        from agents.triggers.trigger_engine import ActionType

        assert ActionType.SEND_REMINDER.value == "send_reminder"
        assert ActionType.QUEUE_CONVERSATION.value == "queue_conversation"

    def test_trigger_action_dataclass(self):
        """Test TriggerAction dataclass."""
        from agents.triggers.trigger_engine import TriggerAction, ActionType
        from agents.triggers.notification_queue import NotificationChannel

        action = TriggerAction(
            action_type=ActionType.SEND_REMINDER,
            student_id="student_123",
            priority=2,
            message_template="Test message",
        )

        assert action.action_type == ActionType.SEND_REMINDER
        assert action.channel == NotificationChannel.IN_APP

    def test_engine_initialization(self):
        """Test engine initialization."""
        from agents.triggers.trigger_engine import TriggerEngine

        engine = TriggerEngine()
        assert engine.deadline_scanner is not None
        assert engine.scholarship_scanner is not None
        assert engine.engagement_tracker is not None
        assert engine.notification_queue is not None

    @pytest.mark.asyncio
    async def test_run_all_scans(self, mock_falkordb):
        """Test running all scans."""
        from agents.triggers.trigger_engine import TriggerEngine

        engine = TriggerEngine(falkordb_client=mock_falkordb)
        actions = await engine.run_all_scans(["student_123"])

        # Should return actions from deadline scan
        assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_execute_actions(self, mock_falkordb):
        """Test executing triggered actions."""
        from agents.triggers.trigger_engine import (
            TriggerEngine, TriggerAction, ActionType
        )

        engine = TriggerEngine(falkordb_client=mock_falkordb)

        actions = [
            TriggerAction(
                action_type=ActionType.SEND_REMINDER,
                student_id="student_123",
                priority=2,
                message_template="Test message",
            ),
        ]

        result = await engine.execute_actions(actions)

        assert result['queued'] == 1
        assert engine.notification_queue.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_run_scan_cycle(self, mock_falkordb):
        """Test full scan cycle."""
        from agents.triggers.trigger_engine import TriggerEngine

        engine = TriggerEngine(falkordb_client=mock_falkordb)
        result = await engine.run_scan_cycle(["student_123"])

        assert 'triggers_found' in result
        assert 'notifications_queued' in result
        assert 'queue_size' in result

    def test_record_student_activity(self):
        """Test recording student activity."""
        from agents.triggers.trigger_engine import TriggerEngine

        engine = TriggerEngine()
        engine.record_student_activity("student_123")

        days = engine.engagement_tracker.get_inactive_days("student_123")
        assert days == 0

    def test_add_known_scholarship(self):
        """Test adding known scholarship."""
        from agents.triggers.trigger_engine import TriggerEngine

        engine = TriggerEngine()
        engine.add_known_scholarship("student_123", "scholarship_456")

        assert "scholarship_456" in engine.scholarship_scanner._previous_matches.get("student_123", set())

    def test_get_queue_stats(self):
        """Test getting queue stats."""
        from agents.triggers.trigger_engine import TriggerEngine

        engine = TriggerEngine()
        stats = engine.get_queue_stats()

        assert 'total' in stats
        assert 'queue_size' in stats


# ============================================================================
# Module Tests
# ============================================================================

class TestTriggersModule:
    """Tests for triggers module."""

    def test_module_exports(self):
        """Test module exports all required classes."""
        from agents.triggers import (
            DeadlineScanner,
            ScholarshipMatchScanner,
            EngagementTracker,
            NotificationQueue,
            Notification,
            TriggerEngine,
            TriggerAction,
        )

        assert DeadlineScanner is not None
        assert ScholarshipMatchScanner is not None
        assert EngagementTracker is not None
        assert NotificationQueue is not None
        assert Notification is not None
        assert TriggerEngine is not None
        assert TriggerAction is not None


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================

class TestAcceptanceCriteria:
    """Tests verifying Story 2.3 acceptance criteria."""

    @pytest.fixture
    def mock_falkordb_7day(self):
        """Create mock with 7-day deadline."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'deadline_test',
            'name': 'Test Deadline',
            'deadline': (date.today() + timedelta(days=5)).isoformat(),
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    @pytest.fixture
    def mock_falkordb_scholarship(self):
        """Create mock with scholarship."""
        mock = MagicMock()

        mock_node = MagicMock()
        mock_node.properties = {
            'id': 'new_match',
            'name': 'New Match Scholarship',
            'amount_max': 20000,
            'verified': True,
            'renewable': True,
            'deadline': '2025-12-31',
        }

        mock_result = MagicMock()
        mock_result.result_set = [[mock_node]]
        mock.get_all_scholarship_sources.return_value = mock_result

        return mock

    @pytest.mark.asyncio
    async def test_ac_deadline_within_7_days_queues_reminder(self, mock_falkordb_7day):
        """AC: System detects deadline within 7 days, queues reminder."""
        from agents.triggers.trigger_engine import TriggerEngine

        engine = TriggerEngine(falkordb_client=mock_falkordb_7day)

        # Run scan cycle
        result = await engine.run_scan_cycle(["student_123"])

        # Should have detected the deadline and queued reminder
        assert result['triggers_found'] >= 1
        assert result['notifications_queued'] >= 1

        # Check the notification is in queue
        notifications = engine.notification_queue.get_student_notifications("student_123")
        assert len(notifications) >= 1

    @pytest.mark.asyncio
    async def test_ac_new_scholarship_match_queues_conversation(self, mock_falkordb_scholarship):
        """AC: System detects new scholarship match, queues conversation."""
        from agents.triggers.trigger_engine import TriggerEngine, ActionType

        engine = TriggerEngine(falkordb_client=mock_falkordb_scholarship)

        # Run scholarship scan
        actions = await engine.run_scholarship_scan(["student_123"])

        # Should have found a match
        assert len(actions) >= 1
        assert any(a.action_type == ActionType.NOTIFY_SCHOLARSHIP for a in actions)

        # Execute actions
        await engine.execute_actions(actions)

        # Check notification is queued
        assert engine.notification_queue.get_queue_size() >= 1

    @pytest.mark.asyncio
    async def test_ac_5_days_inactive_queues_checkin(self):
        """AC: System detects 5 days inactive, queues check-in."""
        from agents.triggers.trigger_engine import TriggerEngine, ActionType

        engine = TriggerEngine()

        # Set last interaction 6 days ago
        engine.engagement_tracker.record_interaction(
            "student_123",
            datetime.utcnow() - timedelta(days=6)
        )

        # Run engagement scan
        actions = await engine.run_engagement_scan(["student_123"])

        # Should have detected inactivity
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.SEND_CHECK_IN

        # Execute action
        await engine.execute_actions(actions)

        # Check notification is queued
        notifications = engine.notification_queue.get_student_notifications("student_123")
        assert len(notifications) == 1
        assert "check" in notifications[0].title.lower() or "miss" in notifications[0].title.lower()


# ============================================================================
# Create Engine Function Test
# ============================================================================

class TestCreateTriggerEngine:
    """Test the create_trigger_engine function."""

    def test_create_trigger_engine(self):
        """Test creating trigger engine with factory function."""
        from agents.triggers.trigger_engine import create_trigger_engine

        engine = create_trigger_engine()
        assert engine is not None
        assert engine.deadline_scanner is not None

    def test_create_with_clients(self):
        """Test creating with FalkorDB and Graphiti clients."""
        from agents.triggers.trigger_engine import create_trigger_engine

        mock_falkordb = MagicMock()
        mock_graphiti = AsyncMock()

        engine = create_trigger_engine(
            falkordb_client=mock_falkordb,
            graphiti_client=mock_graphiti,
        )

        assert engine.deadline_scanner.falkordb == mock_falkordb
        assert engine.scholarship_scanner.falkordb == mock_falkordb


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
