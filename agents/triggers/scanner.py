"""Proactive Scanners - Story 2.3

Implements background scanning for:
- Deadline detection (7 day, 24 hour triggers)
- Scholarship match detection
- Engagement tracking (5 day, 14 day inactivity)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class TriggerPriority(Enum):
    """Priority levels for triggers."""
    CRITICAL = 1  # 24 hours or less
    HIGH = 2      # 7 days or less
    MEDIUM = 3    # Standard triggers
    LOW = 4       # Non-urgent


@dataclass
class ScanResult:
    """Result from a scanner."""
    trigger_type: str
    student_id: str
    priority: TriggerPriority
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action_recommended: str = ""


class DeadlineScanner:
    """Scans for upcoming deadlines and triggers reminders.

    Acceptance Criteria:
    - System detects deadline within 7 days, queues reminder
    """

    def __init__(
        self,
        falkordb_client=None,
        graphiti_client=None,
    ):
        """Initialize deadline scanner.

        Args:
            falkordb_client: FalkorDB client for deadline data
            graphiti_client: Graphiti client for student-specific data
        """
        self.falkordb = falkordb_client
        self.graphiti = graphiti_client

        # Track which deadlines we've already triggered for
        self._triggered_deadlines: Dict[str, Set[str]] = {}  # student_id -> set of deadline_ids

    async def scan(
        self,
        student_ids: Optional[List[str]] = None,
    ) -> List[ScanResult]:
        """Scan for upcoming deadlines.

        Args:
            student_ids: Specific students to scan (None = all)

        Returns:
            List of ScanResult for triggered deadlines
        """
        results = []
        today = date.today()

        # Get all scholarship deadlines
        scholarship_deadlines = await self._get_scholarship_deadlines()

        # If no specific students, return general deadline triggers
        if not student_ids:
            for deadline in scholarship_deadlines:
                days_until = (deadline['due_date'] - today).days

                if days_until <= 0:
                    continue  # Past deadline

                if days_until <= 1:
                    priority = TriggerPriority.CRITICAL
                    action = "send_urgent_reminder"
                elif days_until <= 7:
                    priority = TriggerPriority.HIGH
                    action = "send_reminder"
                else:
                    continue  # Not within trigger window

                result = ScanResult(
                    trigger_type="deadline_approaching",
                    student_id="*",  # All students
                    priority=priority,
                    data={
                        'deadline_id': deadline['id'],
                        'deadline_name': deadline['name'],
                        'due_date': deadline['due_date'].isoformat(),
                        'days_until': days_until,
                    },
                    action_recommended=action,
                )
                results.append(result)

        else:
            # Scan for specific students
            for student_id in student_ids:
                student_results = await self._scan_student_deadlines(
                    student_id, today, scholarship_deadlines
                )
                results.extend(student_results)

        return results

    async def _get_scholarship_deadlines(self) -> List[Dict[str, Any]]:
        """Get all scholarship deadlines from FalkorDB.

        Returns:
            List of deadline dictionaries
        """
        if not self.falkordb:
            return []

        try:
            result = self.falkordb.get_all_scholarship_sources()

            deadlines = []
            for row in result.result_set:
                node = row[0]
                props = node.properties

                deadline_val = props.get('deadline')
                if not deadline_val:
                    continue

                # Parse deadline
                if isinstance(deadline_val, str):
                    try:
                        due_date = datetime.strptime(deadline_val, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                elif isinstance(deadline_val, date):
                    due_date = deadline_val
                else:
                    continue

                deadlines.append({
                    'id': props.get('id', ''),
                    'name': props.get('name', ''),
                    'due_date': due_date,
                    'amount_max': props.get('amount_max', 0),
                })

            return deadlines

        except Exception as e:
            logger.error(f"Failed to get scholarship deadlines: {e}")
            return []

    async def _scan_student_deadlines(
        self,
        student_id: str,
        today: date,
        scholarship_deadlines: List[Dict[str, Any]],
    ) -> List[ScanResult]:
        """Scan deadlines for a specific student.

        Args:
            student_id: Student to scan for
            today: Current date
            scholarship_deadlines: Available scholarship deadlines

        Returns:
            List of triggered scan results
        """
        results = []

        # Initialize triggered set for student if needed
        if student_id not in self._triggered_deadlines:
            self._triggered_deadlines[student_id] = set()

        for deadline in scholarship_deadlines:
            deadline_id = deadline['id']
            days_until = (deadline['due_date'] - today).days

            if days_until <= 0:
                continue

            # Check if we already triggered for this deadline
            trigger_key = f"{deadline_id}_{days_until <= 1}"
            if trigger_key in self._triggered_deadlines[student_id]:
                continue

            if days_until <= 1:
                priority = TriggerPriority.CRITICAL
                action = "send_urgent_reminder"
                self._triggered_deadlines[student_id].add(trigger_key)
            elif days_until <= 7:
                priority = TriggerPriority.HIGH
                action = "send_reminder"
                self._triggered_deadlines[student_id].add(trigger_key)
            else:
                continue

            result = ScanResult(
                trigger_type="deadline_approaching",
                student_id=student_id,
                priority=priority,
                data={
                    'deadline_id': deadline_id,
                    'deadline_name': deadline['name'],
                    'due_date': deadline['due_date'].isoformat(),
                    'days_until': days_until,
                },
                action_recommended=action,
            )
            results.append(result)

        return results

    def reset_triggers(self, student_id: Optional[str] = None):
        """Reset trigger tracking.

        Args:
            student_id: Specific student to reset (None = all)
        """
        if student_id:
            self._triggered_deadlines.pop(student_id, None)
        else:
            self._triggered_deadlines.clear()


class ScholarshipMatchScanner:
    """Scans for new scholarship matches.

    Acceptance Criteria:
    - System detects new scholarship match, queues conversation
    """

    def __init__(
        self,
        falkordb_client=None,
        graphiti_client=None,
    ):
        """Initialize scholarship match scanner.

        Args:
            falkordb_client: FalkorDB client for scholarship data
            graphiti_client: Graphiti client for student data
        """
        self.falkordb = falkordb_client
        self.graphiti = graphiti_client

        # Track previously matched scholarships per student
        self._previous_matches: Dict[str, Set[str]] = {}

    async def scan(
        self,
        student_ids: List[str],
        min_match_score: float = 0.7,
    ) -> List[ScanResult]:
        """Scan for new scholarship matches.

        Args:
            student_ids: Students to scan
            min_match_score: Minimum score to consider a match

        Returns:
            List of ScanResult for new matches
        """
        results = []

        for student_id in student_ids:
            new_matches = await self._find_new_matches(
                student_id, min_match_score
            )
            results.extend(new_matches)

        return results

    async def _find_new_matches(
        self,
        student_id: str,
        min_score: float,
    ) -> List[ScanResult]:
        """Find new scholarship matches for a student.

        Args:
            student_id: Student to find matches for
            min_score: Minimum match score

        Returns:
            List of new match results
        """
        results = []

        if not self.falkordb:
            return results

        # Initialize previous matches for student
        if student_id not in self._previous_matches:
            self._previous_matches[student_id] = set()

        try:
            # Get all scholarships
            result = self.falkordb.get_all_scholarship_sources()

            for row in result.result_set:
                node = row[0]
                props = node.properties

                scholarship_id = props.get('id', '')

                # Skip if already matched
                if scholarship_id in self._previous_matches[student_id]:
                    continue

                # Calculate match score (simplified - in production use profile)
                match_score = await self._calculate_match_score(
                    student_id, props
                )

                if match_score >= min_score:
                    # Mark as matched
                    self._previous_matches[student_id].add(scholarship_id)

                    # Determine priority based on amount and deadline
                    amount = props.get('amount_max', 0)
                    if amount >= 10000:
                        priority = TriggerPriority.HIGH
                    else:
                        priority = TriggerPriority.MEDIUM

                    result_entry = ScanResult(
                        trigger_type="new_scholarship_match",
                        student_id=student_id,
                        priority=priority,
                        data={
                            'scholarship_id': scholarship_id,
                            'scholarship_name': props.get('name', ''),
                            'match_score': match_score,
                            'amount_max': amount,
                            'deadline': str(props.get('deadline', '')),
                        },
                        action_recommended="queue_scholarship_conversation",
                    )
                    results.append(result_entry)

        except Exception as e:
            logger.error(f"Failed to find scholarship matches: {e}")

        return results

    async def _calculate_match_score(
        self,
        student_id: str,
        scholarship_props: Dict[str, Any],
    ) -> float:
        """Calculate match score between student and scholarship.

        Args:
            student_id: Student ID
            scholarship_props: Scholarship properties

        Returns:
            Match score (0-1)
        """
        # In production, this would:
        # 1. Get student profile from Graphiti
        # 2. Compare criteria
        # For now, return a random-ish score based on scholarship properties

        score = 0.5  # Base score

        # Higher amounts get slight boost
        if scholarship_props.get('amount_max', 0) >= 10000:
            score += 0.1

        # Verified scholarships get boost
        if scholarship_props.get('verified', False):
            score += 0.1

        # Renewable scholarships get boost
        if scholarship_props.get('renewable', False):
            score += 0.1

        return min(score, 1.0)

    def add_known_match(self, student_id: str, scholarship_id: str):
        """Mark a scholarship as already matched.

        Args:
            student_id: Student ID
            scholarship_id: Scholarship ID
        """
        if student_id not in self._previous_matches:
            self._previous_matches[student_id] = set()
        self._previous_matches[student_id].add(scholarship_id)

    def reset_matches(self, student_id: Optional[str] = None):
        """Reset match tracking.

        Args:
            student_id: Specific student to reset (None = all)
        """
        if student_id:
            self._previous_matches.pop(student_id, None)
        else:
            self._previous_matches.clear()


class EngagementTracker:
    """Tracks student engagement and triggers check-ins.

    Acceptance Criteria:
    - System detects 5 days inactive, queues check-in
    """

    # Inactivity thresholds
    WARN_THRESHOLD_DAYS = 5
    CRITICAL_THRESHOLD_DAYS = 14

    def __init__(
        self,
        graphiti_client=None,
    ):
        """Initialize engagement tracker.

        Args:
            graphiti_client: Graphiti client for activity data
        """
        self.graphiti = graphiti_client

        # Track last interaction time per student
        self._last_interaction: Dict[str, datetime] = {}

        # Track which students we've already triggered for
        self._triggered_students: Dict[str, str] = {}  # student_id -> trigger level

    async def scan(
        self,
        student_ids: List[str],
    ) -> List[ScanResult]:
        """Scan for inactive students.

        Args:
            student_ids: Students to check

        Returns:
            List of ScanResult for inactive students
        """
        results = []
        now = datetime.utcnow()

        for student_id in student_ids:
            result = await self._check_engagement(student_id, now)
            if result:
                results.append(result)

        return results

    async def _check_engagement(
        self,
        student_id: str,
        now: datetime,
    ) -> Optional[ScanResult]:
        """Check engagement for a specific student.

        Args:
            student_id: Student to check
            now: Current time

        Returns:
            ScanResult if trigger conditions met, None otherwise
        """
        # Get last interaction time
        last_interaction = await self._get_last_interaction(student_id)

        if not last_interaction:
            # No interaction history - could be new student
            return None

        days_inactive = (now - last_interaction).days

        # Check against thresholds
        if days_inactive >= self.CRITICAL_THRESHOLD_DAYS:
            trigger_level = "critical"
            priority = TriggerPriority.HIGH
            action = "send_reengagement_message"
        elif days_inactive >= self.WARN_THRESHOLD_DAYS:
            trigger_level = "warning"
            priority = TriggerPriority.MEDIUM
            action = "send_check_in"
        else:
            return None  # Active student

        # Check if we already triggered at this level
        previous_trigger = self._triggered_students.get(student_id)
        if previous_trigger == trigger_level:
            return None  # Already triggered

        # Record trigger
        self._triggered_students[student_id] = trigger_level

        return ScanResult(
            trigger_type="student_inactive",
            student_id=student_id,
            priority=priority,
            data={
                'days_inactive': days_inactive,
                'last_interaction': last_interaction.isoformat(),
                'trigger_level': trigger_level,
            },
            action_recommended=action,
        )

    async def _get_last_interaction(
        self,
        student_id: str,
    ) -> Optional[datetime]:
        """Get last interaction time for a student.

        Args:
            student_id: Student ID

        Returns:
            Last interaction datetime or None
        """
        # Check cache first
        if student_id in self._last_interaction:
            return self._last_interaction[student_id]

        # Try to get from Graphiti
        if self.graphiti:
            try:
                history = await self.graphiti.get_student_history(
                    student_id, limit=1
                )
                if history:
                    # Get the most recent entry
                    last_entry = history[0]
                    valid_at = last_entry.get('valid_at')
                    if valid_at:
                        if isinstance(valid_at, str):
                            last_time = datetime.fromisoformat(valid_at)
                        else:
                            last_time = valid_at
                        self._last_interaction[student_id] = last_time
                        return last_time
            except Exception as e:
                logger.warning(f"Could not get history for {student_id}: {e}")

        return None

    def record_interaction(self, student_id: str, timestamp: Optional[datetime] = None):
        """Record a student interaction.

        Args:
            student_id: Student ID
            timestamp: Interaction time (default: now)
        """
        self._last_interaction[student_id] = timestamp or datetime.utcnow()

        # Clear any previous triggers for this student
        self._triggered_students.pop(student_id, None)

    def get_inactive_days(self, student_id: str) -> int:
        """Get number of days a student has been inactive.

        Args:
            student_id: Student ID

        Returns:
            Days inactive (0 if active or unknown)
        """
        last = self._last_interaction.get(student_id)
        if not last:
            return 0
        return (datetime.utcnow() - last).days

    def reset_tracking(self, student_id: Optional[str] = None):
        """Reset engagement tracking.

        Args:
            student_id: Specific student to reset (None = all)
        """
        if student_id:
            self._last_interaction.pop(student_id, None)
            self._triggered_students.pop(student_id, None)
        else:
            self._last_interaction.clear()
            self._triggered_students.clear()
