"""Schedule Reminder Tool - Story 2.2

Creates and manages scheduled reminders for students.
Supports deadline reminders, check-ins, and custom notifications.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)


class ReminderType(Enum):
    """Types of reminders."""
    DEADLINE = "deadline"
    SCHOLARSHIP = "scholarship"
    APPLICATION = "application"
    CHECK_IN = "check_in"
    FOLLOW_UP = "follow_up"
    CUSTOM = "custom"


class ReminderPriority(Enum):
    """Priority levels for reminders."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ReminderStatus(Enum):
    """Status of a reminder."""
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    CANCELLED = "cancelled"
    SNOOZED = "snoozed"


@dataclass
class Reminder:
    """A scheduled reminder."""
    id: str
    student_id: str
    reminder_type: ReminderType
    title: str
    message: str
    scheduled_time: datetime
    priority: ReminderPriority = ReminderPriority.MEDIUM
    status: ReminderStatus = ReminderStatus.PENDING
    channel: str = "all"  # sms, email, push, all
    related_entity_id: Optional[str] = None
    snooze_count: int = 0
    max_snoozes: int = 3
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScheduleReminderTool:
    """Tool for scheduling and managing reminders.

    Acceptance Criteria:
    - schedule_reminder creates scheduled messages
    """

    def __init__(self, graphiti_client=None):
        """Initialize schedule reminder tool.

        Args:
            graphiti_client: Graphiti client for persistence
        """
        self.graphiti = graphiti_client
        # In-memory storage (in production, use persistent storage)
        self._reminders: Dict[str, Reminder] = {}
        self._student_reminders: Dict[str, List[str]] = {}

    async def create_reminder(
        self,
        student_id: str,
        title: str,
        message: str,
        scheduled_time: datetime,
        reminder_type: ReminderType = ReminderType.CUSTOM,
        priority: ReminderPriority = ReminderPriority.MEDIUM,
        channel: str = "all",
        related_entity_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Reminder:
        """Create a new scheduled reminder.

        Args:
            student_id: Student to remind
            title: Reminder title
            message: Reminder message
            scheduled_time: When to send the reminder
            reminder_type: Type of reminder
            priority: Priority level
            channel: Delivery channel
            related_entity_id: Related entity (scholarship, application, etc.)
            metadata: Additional metadata

        Returns:
            Created Reminder object
        """
        reminder = Reminder(
            id=str(uuid.uuid4()),
            student_id=student_id,
            reminder_type=reminder_type,
            title=title,
            message=message,
            scheduled_time=scheduled_time,
            priority=priority,
            channel=channel,
            related_entity_id=related_entity_id,
            metadata=metadata or {},
        )

        # Store reminder
        self._reminders[reminder.id] = reminder

        # Index by student
        if student_id not in self._student_reminders:
            self._student_reminders[student_id] = []
        self._student_reminders[student_id].append(reminder.id)

        # Persist to Graphiti if available
        if self.graphiti:
            try:
                await self.graphiti.add_fact(
                    subject=student_id,
                    predicate="has_reminder",
                    obj=f"{title} at {scheduled_time.isoformat()}",
                    source="schedule_reminder_tool",
                )
            except Exception as e:
                logger.warning(f"Failed to persist reminder to Graphiti: {e}")

        logger.info(f"Created reminder {reminder.id} for student {student_id}")
        return reminder

    async def create_deadline_reminder(
        self,
        student_id: str,
        deadline_name: str,
        deadline_date: date,
        days_before: int = 7,
        related_entity_id: Optional[str] = None,
    ) -> Reminder:
        """Create a reminder for an upcoming deadline.

        Args:
            student_id: Student to remind
            deadline_name: Name of the deadline
            deadline_date: Date of the deadline
            days_before: Days before deadline to send reminder
            related_entity_id: Related entity ID

        Returns:
            Created Reminder object
        """
        reminder_time = datetime.combine(
            deadline_date - timedelta(days=days_before),
            datetime.min.time().replace(hour=9)  # 9 AM
        )

        # Determine priority based on days before
        if days_before <= 1:
            priority = ReminderPriority.URGENT
        elif days_before <= 3:
            priority = ReminderPriority.HIGH
        elif days_before <= 7:
            priority = ReminderPriority.MEDIUM
        else:
            priority = ReminderPriority.LOW

        message = f"Reminder: {deadline_name} is due in {days_before} day(s) on {deadline_date.strftime('%B %d, %Y')}."

        return await self.create_reminder(
            student_id=student_id,
            title=f"Deadline: {deadline_name}",
            message=message,
            scheduled_time=reminder_time,
            reminder_type=ReminderType.DEADLINE,
            priority=priority,
            related_entity_id=related_entity_id,
        )

    async def create_scholarship_reminder(
        self,
        student_id: str,
        scholarship_name: str,
        deadline_date: date,
        scholarship_id: str,
    ) -> List[Reminder]:
        """Create a series of reminders for a scholarship deadline.

        Creates reminders at 7 days, 3 days, and 1 day before deadline.

        Args:
            student_id: Student to remind
            scholarship_name: Name of scholarship
            deadline_date: Application deadline
            scholarship_id: Scholarship ID

        Returns:
            List of created Reminder objects
        """
        reminders = []
        today = date.today()

        for days_before in [7, 3, 1]:
            reminder_date = deadline_date - timedelta(days=days_before)
            if reminder_date > today:
                reminder = await self.create_deadline_reminder(
                    student_id=student_id,
                    deadline_name=f"{scholarship_name} Application",
                    deadline_date=deadline_date,
                    days_before=days_before,
                    related_entity_id=scholarship_id,
                )
                reminders.append(reminder)

        return reminders

    async def create_check_in_reminder(
        self,
        student_id: str,
        days_from_now: int = 5,
        reason: str = "general check-in",
    ) -> Reminder:
        """Create a check-in reminder to re-engage with a student.

        Args:
            student_id: Student to check in with
            days_from_now: Days from now to schedule check-in
            reason: Reason for check-in

        Returns:
            Created Reminder object
        """
        reminder_time = datetime.utcnow() + timedelta(days=days_from_now)

        return await self.create_reminder(
            student_id=student_id,
            title="Time to Check In",
            message=f"It's been a while! Let's check in about your {reason}.",
            scheduled_time=reminder_time,
            reminder_type=ReminderType.CHECK_IN,
            priority=ReminderPriority.LOW,
        )

    async def get_student_reminders(
        self,
        student_id: str,
        status: Optional[ReminderStatus] = None,
        include_past: bool = False,
    ) -> List[Reminder]:
        """Get all reminders for a student.

        Args:
            student_id: Student ID
            status: Filter by status (None = all)
            include_past: Include past reminders

        Returns:
            List of reminders
        """
        reminder_ids = self._student_reminders.get(student_id, [])
        reminders = [
            self._reminders[rid]
            for rid in reminder_ids
            if rid in self._reminders
        ]

        # Filter by status
        if status:
            reminders = [r for r in reminders if r.status == status]

        # Filter past reminders
        if not include_past:
            now = datetime.utcnow()
            reminders = [r for r in reminders if r.scheduled_time > now]

        # Sort by scheduled time
        reminders.sort(key=lambda x: x.scheduled_time)

        return reminders

    async def get_due_reminders(
        self,
        window_minutes: int = 5,
    ) -> List[Reminder]:
        """Get all reminders due to be sent.

        Args:
            window_minutes: Time window to check

        Returns:
            List of due reminders
        """
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        window_end = now + timedelta(minutes=window_minutes)

        due_reminders = [
            r for r in self._reminders.values()
            if r.status == ReminderStatus.PENDING
            and window_start <= r.scheduled_time <= window_end
        ]

        return sorted(due_reminders, key=lambda x: x.scheduled_time)

    async def mark_sent(self, reminder_id: str) -> bool:
        """Mark a reminder as sent.

        Args:
            reminder_id: Reminder ID

        Returns:
            True if successful
        """
        if reminder_id not in self._reminders:
            return False

        reminder = self._reminders[reminder_id]
        reminder.status = ReminderStatus.SENT
        reminder.sent_at = datetime.utcnow()

        return True

    async def acknowledge(self, reminder_id: str) -> bool:
        """Mark a reminder as acknowledged by the user.

        Args:
            reminder_id: Reminder ID

        Returns:
            True if successful
        """
        if reminder_id not in self._reminders:
            return False

        self._reminders[reminder_id].status = ReminderStatus.ACKNOWLEDGED
        return True

    async def snooze(
        self,
        reminder_id: str,
        snooze_minutes: int = 60,
    ) -> Optional[Reminder]:
        """Snooze a reminder.

        Args:
            reminder_id: Reminder ID
            snooze_minutes: Minutes to snooze

        Returns:
            Updated Reminder or None if cannot snooze
        """
        if reminder_id not in self._reminders:
            return None

        reminder = self._reminders[reminder_id]

        if reminder.snooze_count >= reminder.max_snoozes:
            logger.warning(f"Reminder {reminder_id} has reached max snoozes")
            return None

        reminder.scheduled_time = datetime.utcnow() + timedelta(minutes=snooze_minutes)
        reminder.status = ReminderStatus.SNOOZED
        reminder.snooze_count += 1

        return reminder

    async def cancel(self, reminder_id: str) -> bool:
        """Cancel a reminder.

        Args:
            reminder_id: Reminder ID

        Returns:
            True if successful
        """
        if reminder_id not in self._reminders:
            return False

        self._reminders[reminder_id].status = ReminderStatus.CANCELLED
        return True

    async def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Get a specific reminder.

        Args:
            reminder_id: Reminder ID

        Returns:
            Reminder or None
        """
        return self._reminders.get(reminder_id)

    async def reschedule(
        self,
        reminder_id: str,
        new_time: datetime,
    ) -> Optional[Reminder]:
        """Reschedule a reminder to a new time.

        Args:
            reminder_id: Reminder ID
            new_time: New scheduled time

        Returns:
            Updated Reminder or None
        """
        if reminder_id not in self._reminders:
            return None

        reminder = self._reminders[reminder_id]
        reminder.scheduled_time = new_time
        reminder.status = ReminderStatus.PENDING

        return reminder

    async def get_upcoming_count(self, student_id: str) -> int:
        """Get count of upcoming reminders for a student.

        Args:
            student_id: Student ID

        Returns:
            Number of upcoming reminders
        """
        reminders = await self.get_student_reminders(student_id)
        return len(reminders)
