"""Deadline Check Tool - Story 2.2

Checks and returns upcoming deadlines for scholarships, applications, and FAFSA.
Integrates with FalkorDB for scholarship deadlines and Graphiti for student-specific dates.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class DeadlineType(Enum):
    """Types of deadlines tracked."""
    SCHOLARSHIP = "scholarship"
    APPLICATION = "application"
    FAFSA = "fafsa"
    FINANCIAL_AID = "financial_aid"
    ESSAY = "essay"
    RECOMMENDATION = "recommendation"
    OTHER = "other"


class DeadlineUrgency(Enum):
    """Urgency levels for deadlines."""
    PAST_DUE = "past_due"
    URGENT = "urgent"  # Within 24 hours
    SOON = "soon"  # Within 7 days
    UPCOMING = "upcoming"  # Within 30 days
    FUTURE = "future"  # More than 30 days


@dataclass
class Deadline:
    """A deadline entry."""
    id: str
    name: str
    deadline_type: DeadlineType
    due_date: date
    description: str = ""
    urgency: DeadlineUrgency = DeadlineUrgency.FUTURE
    days_remaining: int = 0
    completed: bool = False
    related_entity_id: Optional[str] = None  # e.g., scholarship_id, school_id
    notes: str = ""


# Known important dates (FAFSA, common deadlines)
KNOWN_DEADLINES = [
    {
        "id": "fafsa_open",
        "name": "FAFSA Opens",
        "type": DeadlineType.FAFSA,
        "month": 10,
        "day": 1,
        "description": "FAFSA application opens for the next academic year",
    },
    {
        "id": "fafsa_priority",
        "name": "FAFSA Priority Deadline (Most States)",
        "type": DeadlineType.FAFSA,
        "month": 3,
        "day": 1,
        "description": "Priority deadline for maximum state and institutional aid",
    },
    {
        "id": "fafsa_federal",
        "name": "FAFSA Federal Deadline",
        "type": DeadlineType.FAFSA,
        "month": 6,
        "day": 30,
        "description": "Final deadline for federal student aid",
    },
]


class DeadlineCheckTool:
    """Tool for checking and managing deadlines.

    Acceptance Criteria:
    - deadline_check returns upcoming deadlines
    """

    def __init__(
        self,
        falkordb_client=None,
        graphiti_client=None,
    ):
        """Initialize deadline check tool.

        Args:
            falkordb_client: FalkorDB client for scholarship deadlines
            graphiti_client: Graphiti client for student-specific deadlines
        """
        self.falkordb = falkordb_client
        self.graphiti = graphiti_client
        self._custom_deadlines: Dict[str, List[Deadline]] = {}

    async def get_upcoming_deadlines(
        self,
        student_id: Optional[str] = None,
        days_ahead: int = 30,
        deadline_types: Optional[List[DeadlineType]] = None,
    ) -> List[Deadline]:
        """Get all upcoming deadlines.

        Args:
            student_id: Optional student ID for personalized deadlines
            days_ahead: Number of days to look ahead
            deadline_types: Filter by deadline types (None = all)

        Returns:
            List of Deadline objects sorted by due date
        """
        today = date.today()
        cutoff_date = today + timedelta(days=days_ahead)

        deadlines = []

        # Get scholarship deadlines from FalkorDB
        scholarship_deadlines = await self._get_scholarship_deadlines(
            cutoff_date
        )
        deadlines.extend(scholarship_deadlines)

        # Get known important dates
        known_deadlines = self._get_known_deadlines(today, cutoff_date)
        deadlines.extend(known_deadlines)

        # Get student-specific deadlines if student_id provided
        if student_id:
            student_deadlines = await self._get_student_deadlines(
                student_id, cutoff_date
            )
            deadlines.extend(student_deadlines)

            # Get custom deadlines for this student
            if student_id in self._custom_deadlines:
                for dl in self._custom_deadlines[student_id]:
                    if dl.due_date <= cutoff_date:
                        deadlines.append(dl)

        # Filter by type if specified
        if deadline_types:
            deadlines = [
                d for d in deadlines if d.deadline_type in deadline_types
            ]

        # Calculate urgency and days remaining
        for deadline in deadlines:
            deadline.days_remaining = (deadline.due_date - today).days
            deadline.urgency = self._calculate_urgency(deadline.days_remaining)

        # Sort by due date
        deadlines.sort(key=lambda x: x.due_date)

        return deadlines

    async def _get_scholarship_deadlines(
        self,
        cutoff_date: date,
    ) -> List[Deadline]:
        """Get scholarship deadlines from FalkorDB.

        Args:
            cutoff_date: Don't return deadlines after this date

        Returns:
            List of scholarship deadlines
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
                        deadline_date = datetime.strptime(
                            deadline_val, "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        continue
                elif isinstance(deadline_val, date):
                    deadline_date = deadline_val
                else:
                    continue

                if deadline_date > cutoff_date:
                    continue

                deadline = Deadline(
                    id=f"scholarship_{props.get('id', '')}",
                    name=f"{props.get('name', 'Unknown')} Deadline",
                    deadline_type=DeadlineType.SCHOLARSHIP,
                    due_date=deadline_date,
                    description=f"Apply for {props.get('name', '')}. "
                               f"Award: ${props.get('amount_min', 0):,.0f}-"
                               f"${props.get('amount_max', 0):,.0f}",
                    related_entity_id=props.get('id', ''),
                )
                deadlines.append(deadline)

            return deadlines

        except Exception as e:
            logger.error(f"Failed to get scholarship deadlines: {e}")
            return []

    def _get_known_deadlines(
        self,
        today: date,
        cutoff_date: date,
    ) -> List[Deadline]:
        """Get known important dates (FAFSA, etc.).

        Args:
            today: Current date
            cutoff_date: Don't return dates after this

        Returns:
            List of known deadlines
        """
        deadlines = []
        current_year = today.year
        next_year = current_year + 1

        for known in KNOWN_DEADLINES:
            # Try current year and next year
            for year in [current_year, next_year]:
                deadline_date = date(year, known["month"], known["day"])

                # Skip past dates and dates beyond cutoff
                if deadline_date < today or deadline_date > cutoff_date:
                    continue

                deadline = Deadline(
                    id=f"{known['id']}_{year}",
                    name=known["name"],
                    deadline_type=known["type"],
                    due_date=deadline_date,
                    description=known["description"],
                )
                deadlines.append(deadline)

        return deadlines

    async def _get_student_deadlines(
        self,
        student_id: str,
        cutoff_date: date,
    ) -> List[Deadline]:
        """Get student-specific deadlines from Graphiti.

        Args:
            student_id: Student ID
            cutoff_date: Don't return deadlines after this date

        Returns:
            List of student-specific deadlines
        """
        if not self.graphiti:
            return []

        try:
            # Search Graphiti for deadline-related facts
            results = await self.graphiti.search(
                query="deadline due date application",
                num_results=50,
                group_ids=[student_id],
            )

            deadlines = []
            for result in results:
                # Extract deadline info from facts (simplified)
                fact = result.get('fact', '')
                if 'deadline' in fact.lower() or 'due' in fact.lower():
                    # Try to extract date from fact
                    deadline_date = self._extract_date_from_text(fact)
                    if deadline_date and deadline_date <= cutoff_date:
                        deadline = Deadline(
                            id=f"student_{student_id}_{result.get('name', '')}",
                            name=result.get('name', 'Deadline'),
                            deadline_type=DeadlineType.OTHER,
                            due_date=deadline_date,
                            description=fact,
                        )
                        deadlines.append(deadline)

            return deadlines

        except Exception as e:
            logger.error(f"Failed to get student deadlines: {e}")
            return []

    def _extract_date_from_text(self, text: str) -> Optional[date]:
        """Try to extract a date from text.

        Args:
            text: Text that may contain a date

        Returns:
            Extracted date or None
        """
        import re

        # Try common date formats
        patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # 2025-01-15
            r'(\d{2}/\d{2}/\d{4})',  # 01/15/2025
            r'(\d{1,2}/\d{1,2}/\d{4})',  # 1/15/2025
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    if '-' in date_str:
                        return datetime.strptime(date_str, "%Y-%m-%d").date()
                    else:
                        return datetime.strptime(date_str, "%m/%d/%Y").date()
                except ValueError:
                    continue

        return None

    def _calculate_urgency(self, days_remaining: int) -> DeadlineUrgency:
        """Calculate urgency based on days remaining.

        Args:
            days_remaining: Days until deadline

        Returns:
            DeadlineUrgency level
        """
        if days_remaining < 0:
            return DeadlineUrgency.PAST_DUE
        elif days_remaining <= 1:
            return DeadlineUrgency.URGENT
        elif days_remaining <= 7:
            return DeadlineUrgency.SOON
        elif days_remaining <= 30:
            return DeadlineUrgency.UPCOMING
        else:
            return DeadlineUrgency.FUTURE

    async def get_urgent_deadlines(
        self,
        student_id: Optional[str] = None,
    ) -> List[Deadline]:
        """Get only urgent deadlines (within 7 days).

        Args:
            student_id: Optional student ID

        Returns:
            List of urgent deadlines
        """
        all_deadlines = await self.get_upcoming_deadlines(
            student_id=student_id,
            days_ahead=7,
        )

        return [
            d for d in all_deadlines
            if d.urgency in (DeadlineUrgency.URGENT, DeadlineUrgency.SOON)
        ]

    async def add_custom_deadline(
        self,
        student_id: str,
        name: str,
        due_date: date,
        deadline_type: DeadlineType = DeadlineType.OTHER,
        description: str = "",
        related_entity_id: Optional[str] = None,
    ) -> Deadline:
        """Add a custom deadline for a student.

        Args:
            student_id: Student ID
            name: Deadline name
            due_date: Due date
            deadline_type: Type of deadline
            description: Optional description
            related_entity_id: Optional related entity

        Returns:
            Created Deadline object
        """
        deadline = Deadline(
            id=f"custom_{student_id}_{datetime.now().timestamp()}",
            name=name,
            deadline_type=deadline_type,
            due_date=due_date,
            description=description,
            related_entity_id=related_entity_id,
        )

        # Store in memory (in production, persist to Graphiti)
        if student_id not in self._custom_deadlines:
            self._custom_deadlines[student_id] = []
        self._custom_deadlines[student_id].append(deadline)

        # Also store in Graphiti if available
        if self.graphiti:
            try:
                await self.graphiti.add_fact(
                    subject=student_id,
                    predicate="has_deadline",
                    obj=f"{name} on {due_date.isoformat()}",
                    source="deadline_check_tool",
                )
            except Exception as e:
                logger.warning(f"Failed to persist deadline to Graphiti: {e}")

        return deadline

    async def mark_deadline_complete(
        self,
        student_id: str,
        deadline_id: str,
    ) -> bool:
        """Mark a deadline as complete.

        Args:
            student_id: Student ID
            deadline_id: Deadline ID to mark complete

        Returns:
            True if successful
        """
        if student_id in self._custom_deadlines:
            for deadline in self._custom_deadlines[student_id]:
                if deadline.id == deadline_id:
                    deadline.completed = True
                    return True

        return False
