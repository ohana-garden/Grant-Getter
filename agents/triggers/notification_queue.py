"""Notification Queue - Story 2.3

Manages queued notifications for proactive outreach.
Supports priority-based processing and delivery tracking.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Callable, Awaitable
from enum import Enum
import uuid
from heapq import heappush, heappop

logger = logging.getLogger(__name__)


class NotificationStatus(Enum):
    """Status of a notification."""
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationChannel(Enum):
    """Delivery channels for notifications."""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    VOICE = "voice"


@dataclass
class Notification:
    """A queued notification."""
    id: str
    student_id: str
    title: str
    message: str
    channel: NotificationChannel
    priority: int  # Lower = higher priority
    trigger_type: str
    status: NotificationStatus = NotificationStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other):
        """Compare by priority for heap operations."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class NotificationQueue:
    """Priority queue for proactive notifications.

    Manages queued notifications with priority-based processing
    and delivery tracking.
    """

    def __init__(self):
        """Initialize notification queue."""
        # Priority queue using heapq
        self._queue: List[Notification] = []

        # Index by ID for quick lookup
        self._notifications: Dict[str, Notification] = {}

        # Index by student
        self._student_notifications: Dict[str, List[str]] = {}

        # Delivery handlers by channel
        self._handlers: Dict[NotificationChannel, Callable] = {}

    def enqueue(
        self,
        student_id: str,
        title: str,
        message: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        priority: int = 3,
        trigger_type: str = "manual",
        scheduled_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Add a notification to the queue.

        Args:
            student_id: Student to notify
            title: Notification title
            message: Notification message
            channel: Delivery channel
            priority: Priority (1=highest, 5=lowest)
            trigger_type: What triggered this notification
            scheduled_at: When to send (None = immediate)
            metadata: Additional data

        Returns:
            Created Notification object
        """
        notification = Notification(
            id=str(uuid.uuid4()),
            student_id=student_id,
            title=title,
            message=message,
            channel=channel,
            priority=priority,
            trigger_type=trigger_type,
            scheduled_at=scheduled_at or datetime.utcnow(),
            metadata=metadata or {},
        )

        # Add to priority queue
        heappush(self._queue, notification)

        # Index by ID
        self._notifications[notification.id] = notification

        # Index by student
        if student_id not in self._student_notifications:
            self._student_notifications[student_id] = []
        self._student_notifications[student_id].append(notification.id)

        logger.info(
            f"Queued notification {notification.id} for student {student_id} "
            f"(priority={priority}, trigger={trigger_type})"
        )

        return notification

    def dequeue(self) -> Optional[Notification]:
        """Get the highest priority notification ready to send.

        Returns:
            Next notification or None if queue empty
        """
        now = datetime.utcnow()

        # Find next ready notification
        while self._queue:
            notification = heappop(self._queue)

            # Check if cancelled
            if notification.status == NotificationStatus.CANCELLED:
                continue

            # Check if scheduled time has passed
            if notification.scheduled_at and notification.scheduled_at > now:
                # Put it back, not ready yet
                heappush(self._queue, notification)
                return None

            # Mark as processing
            notification.status = NotificationStatus.PROCESSING

            return notification

        return None

    def peek(self) -> Optional[Notification]:
        """Peek at the next notification without removing it.

        Returns:
            Next notification or None
        """
        if not self._queue:
            return None

        # Find first non-cancelled notification
        for notification in self._queue:
            if notification.status != NotificationStatus.CANCELLED:
                return notification

        return None

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Get a specific notification by ID.

        Args:
            notification_id: Notification ID

        Returns:
            Notification or None
        """
        return self._notifications.get(notification_id)

    def get_student_notifications(
        self,
        student_id: str,
        status: Optional[NotificationStatus] = None,
    ) -> List[Notification]:
        """Get all notifications for a student.

        Args:
            student_id: Student ID
            status: Filter by status (None = all)

        Returns:
            List of notifications
        """
        notification_ids = self._student_notifications.get(student_id, [])
        notifications = [
            self._notifications[nid]
            for nid in notification_ids
            if nid in self._notifications
        ]

        if status:
            notifications = [n for n in notifications if n.status == status]

        return sorted(notifications, key=lambda x: x.created_at, reverse=True)

    def mark_sent(self, notification_id: str) -> bool:
        """Mark a notification as sent.

        Args:
            notification_id: Notification ID

        Returns:
            True if successful
        """
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        notification.status = NotificationStatus.SENT
        notification.sent_at = datetime.utcnow()

        logger.info(f"Notification {notification_id} marked as sent")
        return True

    def mark_failed(
        self,
        notification_id: str,
        requeue: bool = True,
    ) -> bool:
        """Mark a notification as failed.

        Args:
            notification_id: Notification ID
            requeue: Whether to requeue for retry

        Returns:
            True if successful
        """
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        notification.retry_count += 1

        if requeue and notification.retry_count < notification.max_retries:
            # Requeue with delay
            notification.status = NotificationStatus.QUEUED
            notification.scheduled_at = datetime.utcnow() + timedelta(
                minutes=5 * notification.retry_count
            )
            heappush(self._queue, notification)
            logger.info(
                f"Notification {notification_id} requeued (retry {notification.retry_count})"
            )
        else:
            notification.status = NotificationStatus.FAILED
            logger.warning(f"Notification {notification_id} failed permanently")

        return True

    def cancel(self, notification_id: str) -> bool:
        """Cancel a notification.

        Args:
            notification_id: Notification ID

        Returns:
            True if successful
        """
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        notification.status = NotificationStatus.CANCELLED
        logger.info(f"Notification {notification_id} cancelled")
        return True

    def register_handler(
        self,
        channel: NotificationChannel,
        handler: Callable[[Notification], Awaitable[bool]],
    ):
        """Register a delivery handler for a channel.

        Args:
            channel: Notification channel
            handler: Async function to deliver notification
        """
        self._handlers[channel] = handler
        logger.info(f"Registered handler for {channel.value}")

    async def process_next(self) -> Optional[bool]:
        """Process the next notification in queue.

        Returns:
            True if sent successfully, False if failed, None if queue empty
        """
        notification = self.dequeue()
        if not notification:
            return None

        # Get handler for channel
        handler = self._handlers.get(notification.channel)

        if not handler:
            logger.warning(
                f"No handler for channel {notification.channel.value}, "
                f"using default in-app delivery"
            )
            # Mark as sent for in-app (client will fetch)
            self.mark_sent(notification.id)
            return True

        try:
            success = await handler(notification)
            if success:
                self.mark_sent(notification.id)
                return True
            else:
                self.mark_failed(notification.id)
                return False
        except Exception as e:
            logger.error(f"Failed to deliver notification: {e}")
            self.mark_failed(notification.id)
            return False

    async def process_all_ready(self) -> Dict[str, int]:
        """Process all ready notifications.

        Returns:
            Dict with counts: sent, failed, remaining
        """
        sent = 0
        failed = 0

        while True:
            result = await self.process_next()
            if result is None:
                break
            elif result:
                sent += 1
            else:
                failed += 1

        return {
            'sent': sent,
            'failed': failed,
            'remaining': len([
                n for n in self._queue
                if n.status == NotificationStatus.QUEUED
            ]),
        }

    def get_queue_size(self) -> int:
        """Get number of queued notifications.

        Returns:
            Queue size
        """
        return len([
            n for n in self._queue
            if n.status == NotificationStatus.QUEUED
        ])

    def get_pending_by_priority(self) -> Dict[int, int]:
        """Get count of pending notifications by priority.

        Returns:
            Dict mapping priority to count
        """
        counts: Dict[int, int] = {}
        for notification in self._queue:
            if notification.status == NotificationStatus.QUEUED:
                counts[notification.priority] = counts.get(notification.priority, 0) + 1
        return counts

    def clear_student_queue(self, student_id: str) -> int:
        """Clear all pending notifications for a student.

        Args:
            student_id: Student ID

        Returns:
            Number of notifications cancelled
        """
        cancelled = 0
        notification_ids = self._student_notifications.get(student_id, [])

        for nid in notification_ids:
            notification = self._notifications.get(nid)
            if notification and notification.status == NotificationStatus.QUEUED:
                notification.status = NotificationStatus.CANCELLED
                cancelled += 1

        return cancelled

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics.

        Returns:
            Dict with queue stats
        """
        total = len(self._notifications)
        by_status = {}
        by_channel = {}

        for notification in self._notifications.values():
            status_key = notification.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1

            channel_key = notification.channel.value
            by_channel[channel_key] = by_channel.get(channel_key, 0) + 1

        return {
            'total': total,
            'queue_size': self.get_queue_size(),
            'by_status': by_status,
            'by_channel': by_channel,
            'by_priority': self.get_pending_by_priority(),
        }
