"""Trigger Engine - Story 2.3

Coordinates all proactive scanners and maps triggers to actions.
Manages the full lifecycle from detection to notification queuing.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Awaitable
from enum import Enum

from agents.triggers.scanner import (
    DeadlineScanner,
    ScholarshipMatchScanner,
    EngagementTracker,
    ScanResult,
    TriggerPriority,
)
from agents.triggers.notification_queue import (
    NotificationQueue,
    Notification,
    NotificationChannel,
)

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions that can be triggered."""
    SEND_REMINDER = "send_reminder"
    SEND_URGENT_REMINDER = "send_urgent_reminder"
    SEND_CHECK_IN = "send_check_in"
    SEND_REENGAGEMENT = "send_reengagement"
    QUEUE_CONVERSATION = "queue_conversation"
    NOTIFY_SCHOLARSHIP = "notify_scholarship"
    PROCESS_COMMISSION = "process_commission"


@dataclass
class TriggerAction:
    """An action to take in response to a trigger."""
    action_type: ActionType
    student_id: str
    priority: int
    message_template: str
    data: Dict[str, Any] = field(default_factory=dict)
    channel: NotificationChannel = NotificationChannel.IN_APP


# Message templates for different trigger types
MESSAGE_TEMPLATES = {
    "deadline_7_day": (
        "Heads up! The {deadline_name} deadline is coming up in {days_until} days "
        "(due {due_date}). Make sure you're ready!"
    ),
    "deadline_1_day": (
        "URGENT: {deadline_name} is due TOMORROW ({due_date})! "
        "Don't miss this deadline!"
    ),
    "scholarship_match": (
        "Great news! I found a new scholarship that matches your profile: "
        "{scholarship_name}. It's worth up to ${amount_max:,.0f}! "
        "Deadline: {deadline}. Want me to tell you more?"
    ),
    "check_in_5_day": (
        "Hey there! It's been a few days since we chatted. "
        "How's your scholarship search going? Need any help?"
    ),
    "check_in_14_day": (
        "I've missed you! It's been a couple weeks. "
        "Let's catch up on your applications and make sure you're on track. "
        "Any deadlines coming up?"
    ),
}


class TriggerEngine:
    """Coordinates proactive triggers and actions.

    Manages scanners, maps triggers to actions, and queues notifications.
    """

    def __init__(
        self,
        falkordb_client=None,
        graphiti_client=None,
    ):
        """Initialize trigger engine.

        Args:
            falkordb_client: FalkorDB client
            graphiti_client: Graphiti client
        """
        # Initialize scanners
        self.deadline_scanner = DeadlineScanner(
            falkordb_client=falkordb_client,
            graphiti_client=graphiti_client,
        )
        self.scholarship_scanner = ScholarshipMatchScanner(
            falkordb_client=falkordb_client,
            graphiti_client=graphiti_client,
        )
        self.engagement_tracker = EngagementTracker(
            graphiti_client=graphiti_client,
        )

        # Initialize notification queue
        self.notification_queue = NotificationQueue()

        # Custom action handlers
        self._action_handlers: Dict[ActionType, Callable] = {}

        # Track last scan times
        self._last_scan: Dict[str, datetime] = {}

        # Scan intervals (in minutes)
        self.scan_intervals = {
            'deadline': 60,      # Check deadlines every hour
            'scholarship': 360,  # Check matches every 6 hours
            'engagement': 1440,  # Check engagement daily
        }

    async def run_all_scans(
        self,
        student_ids: List[str],
    ) -> List[TriggerAction]:
        """Run all scanners and return triggered actions.

        Args:
            student_ids: Students to scan

        Returns:
            List of TriggerAction objects
        """
        actions = []

        # Run each scanner
        deadline_results = await self.deadline_scanner.scan(student_ids)
        scholarship_results = await self.scholarship_scanner.scan(student_ids)
        engagement_results = await self.engagement_tracker.scan(student_ids)

        # Map results to actions
        all_results = deadline_results + scholarship_results + engagement_results

        for result in all_results:
            action = self._map_trigger_to_action(result)
            if action:
                actions.append(action)

        return actions

    async def run_deadline_scan(
        self,
        student_ids: Optional[List[str]] = None,
    ) -> List[TriggerAction]:
        """Run only the deadline scanner.

        Args:
            student_ids: Students to scan (None = all)

        Returns:
            List of triggered actions
        """
        results = await self.deadline_scanner.scan(student_ids)
        return [self._map_trigger_to_action(r) for r in results if r]

    async def run_scholarship_scan(
        self,
        student_ids: List[str],
    ) -> List[TriggerAction]:
        """Run only the scholarship match scanner.

        Args:
            student_ids: Students to scan

        Returns:
            List of triggered actions
        """
        results = await self.scholarship_scanner.scan(student_ids)
        return [self._map_trigger_to_action(r) for r in results if r]

    async def run_engagement_scan(
        self,
        student_ids: List[str],
    ) -> List[TriggerAction]:
        """Run only the engagement tracker.

        Args:
            student_ids: Students to scan

        Returns:
            List of triggered actions
        """
        results = await self.engagement_tracker.scan(student_ids)
        return [self._map_trigger_to_action(r) for r in results if r]

    def _map_trigger_to_action(
        self,
        scan_result: ScanResult,
    ) -> Optional[TriggerAction]:
        """Map a scan result to an action.

        Args:
            scan_result: Result from a scanner

        Returns:
            TriggerAction or None
        """
        data = scan_result.data

        if scan_result.trigger_type == "deadline_approaching":
            days_until = data.get('days_until', 0)

            if days_until <= 1:
                template = MESSAGE_TEMPLATES["deadline_1_day"]
                action_type = ActionType.SEND_URGENT_REMINDER
            else:
                template = MESSAGE_TEMPLATES["deadline_7_day"]
                action_type = ActionType.SEND_REMINDER

            message = template.format(
                deadline_name=data.get('deadline_name', 'Unknown'),
                days_until=days_until,
                due_date=data.get('due_date', ''),
            )

            return TriggerAction(
                action_type=action_type,
                student_id=scan_result.student_id,
                priority=scan_result.priority.value,
                message_template=message,
                data=data,
                channel=NotificationChannel.SMS if days_until <= 1 else NotificationChannel.IN_APP,
            )

        elif scan_result.trigger_type == "new_scholarship_match":
            template = MESSAGE_TEMPLATES["scholarship_match"]
            message = template.format(
                scholarship_name=data.get('scholarship_name', 'Unknown'),
                amount_max=data.get('amount_max', 0),
                deadline=data.get('deadline', 'TBD'),
            )

            return TriggerAction(
                action_type=ActionType.NOTIFY_SCHOLARSHIP,
                student_id=scan_result.student_id,
                priority=scan_result.priority.value,
                message_template=message,
                data=data,
                channel=NotificationChannel.IN_APP,
            )

        elif scan_result.trigger_type == "student_inactive":
            trigger_level = data.get('trigger_level', 'warning')

            if trigger_level == "critical":
                template = MESSAGE_TEMPLATES["check_in_14_day"]
                action_type = ActionType.SEND_REENGAGEMENT
            else:
                template = MESSAGE_TEMPLATES["check_in_5_day"]
                action_type = ActionType.SEND_CHECK_IN

            return TriggerAction(
                action_type=action_type,
                student_id=scan_result.student_id,
                priority=scan_result.priority.value,
                message_template=template,
                data=data,
                channel=NotificationChannel.SMS,
            )

        return None

    async def execute_actions(
        self,
        actions: List[TriggerAction],
    ) -> Dict[str, int]:
        """Execute triggered actions by queuing notifications.

        Args:
            actions: Actions to execute

        Returns:
            Dict with counts: queued, skipped
        """
        queued = 0
        skipped = 0

        for action in actions:
            if action.student_id == "*":
                # Skip broadcast actions for now (would need student list)
                skipped += 1
                continue

            # Queue the notification
            self.notification_queue.enqueue(
                student_id=action.student_id,
                title=self._get_action_title(action.action_type),
                message=action.message_template,
                channel=action.channel,
                priority=action.priority,
                trigger_type=action.action_type.value,
                metadata=action.data,
            )
            queued += 1

        return {'queued': queued, 'skipped': skipped}

    def _get_action_title(self, action_type: ActionType) -> str:
        """Get a title for an action type.

        Args:
            action_type: The action type

        Returns:
            Human-readable title
        """
        titles = {
            ActionType.SEND_REMINDER: "Deadline Reminder",
            ActionType.SEND_URGENT_REMINDER: "URGENT: Deadline Tomorrow",
            ActionType.SEND_CHECK_IN: "Check-in",
            ActionType.SEND_REENGAGEMENT: "We Miss You!",
            ActionType.QUEUE_CONVERSATION: "New Message",
            ActionType.NOTIFY_SCHOLARSHIP: "New Scholarship Match",
            ActionType.PROCESS_COMMISSION: "Commission Update",
        }
        return titles.get(action_type, "Notification")

    async def run_scan_cycle(
        self,
        student_ids: List[str],
    ) -> Dict[str, Any]:
        """Run a full scan cycle and execute actions.

        Args:
            student_ids: Students to scan

        Returns:
            Summary of scan cycle results
        """
        # Run all scans
        actions = await self.run_all_scans(student_ids)

        # Execute actions
        execution_result = await self.execute_actions(actions)

        return {
            'triggers_found': len(actions),
            'notifications_queued': execution_result['queued'],
            'skipped': execution_result['skipped'],
            'queue_size': self.notification_queue.get_queue_size(),
        }

    def register_action_handler(
        self,
        action_type: ActionType,
        handler: Callable[[TriggerAction], Awaitable[bool]],
    ):
        """Register a custom handler for an action type.

        Args:
            action_type: Action type to handle
            handler: Async function to handle the action
        """
        self._action_handlers[action_type] = handler
        logger.info(f"Registered handler for {action_type.value}")

    def record_student_activity(
        self,
        student_id: str,
        timestamp: Optional[datetime] = None,
    ):
        """Record student activity for engagement tracking.

        Args:
            student_id: Student ID
            timestamp: Activity time (default: now)
        """
        self.engagement_tracker.record_interaction(student_id, timestamp)

    def add_known_scholarship(
        self,
        student_id: str,
        scholarship_id: str,
    ):
        """Mark a scholarship as already known to avoid re-triggering.

        Args:
            student_id: Student ID
            scholarship_id: Scholarship ID
        """
        self.scholarship_scanner.add_known_match(student_id, scholarship_id)

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get notification queue statistics.

        Returns:
            Queue stats dict
        """
        return self.notification_queue.get_stats()

    async def process_notifications(self) -> Dict[str, int]:
        """Process all ready notifications.

        Returns:
            Processing results
        """
        return await self.notification_queue.process_all_ready()

    def reset_all_tracking(self):
        """Reset all scanner tracking data."""
        self.deadline_scanner.reset_triggers()
        self.scholarship_scanner.reset_matches()
        self.engagement_tracker.reset_tracking()


# Convenience function to create a configured trigger engine
def create_trigger_engine(
    falkordb_client=None,
    graphiti_client=None,
) -> TriggerEngine:
    """Create and configure a trigger engine.

    Args:
        falkordb_client: FalkorDB client
        graphiti_client: Graphiti client

    Returns:
        Configured TriggerEngine instance
    """
    return TriggerEngine(
        falkordb_client=falkordb_client,
        graphiti_client=graphiti_client,
    )
