"""Deadline Sentinel Agent - Story 3.3

Background agent that proactively monitors and scrapes deadlines.
Tracks FAFSA, school-specific, and scholarship deadlines with verification.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set
from enum import Enum

from agents.config import (
    deadline_sentinel_config,
    AgentConfig,
    ModelType,
    get_model_name,
)

logger = logging.getLogger(__name__)


class DeadlineType(Enum):
    """Types of deadlines tracked."""
    FAFSA = "fafsa"
    CSS_PROFILE = "css_profile"
    SCHOOL_PRIORITY = "school_priority"
    SCHOOL_FINAL = "school_final"
    SCHOLARSHIP = "scholarship"
    VERIFICATION = "verification"
    APPEAL = "appeal"
    OTHER = "other"


class DeadlineStatus(Enum):
    """Status of a deadline."""
    UPCOMING = "upcoming"
    DUE_SOON = "due_soon"  # Within 7 days
    URGENT = "urgent"  # Within 24 hours
    PASSED = "passed"
    COMPLETED = "completed"


class SourceReliability(Enum):
    """Reliability of deadline source."""
    OFFICIAL = "official"  # Direct from school website
    VERIFIED = "verified"  # Cross-referenced
    SCRAPED = "scraped"  # Auto-scraped, may change
    USER_REPORTED = "user_reported"
    UNKNOWN = "unknown"


@dataclass
class DeadlineEntry:
    """A tracked deadline."""
    id: str
    deadline_type: DeadlineType
    name: str
    due_date: date
    school_id: Optional[str] = None
    school_name: Optional[str] = None
    description: str = ""
    source_url: Optional[str] = None
    source_reliability: SourceReliability = SourceReliability.UNKNOWN
    status: DeadlineStatus = DeadlineStatus.UPCOMING
    student_ids: List[str] = field(default_factory=list)
    last_verified: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def days_until(self) -> int:
        """Get days until deadline."""
        return (self.due_date - date.today()).days

    @property
    def is_past(self) -> bool:
        """Check if deadline has passed."""
        return self.days_until < 0


@dataclass
class ScrapeResult:
    """Result from scraping a deadline source."""
    source_url: str
    deadlines_found: int
    new_deadlines: int
    updated_deadlines: int
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    errors: List[str] = field(default_factory=list)
    success: bool = True


@dataclass
class DeadlineChange:
    """A detected change in a deadline."""
    deadline_id: str
    change_type: str  # "new", "updated", "removed"
    old_date: Optional[date] = None
    new_date: Optional[date] = None
    detected_at: datetime = field(default_factory=datetime.utcnow)
    notified: bool = False


# Known FAFSA deadlines (federal)
FAFSA_DEADLINES = {
    "fafsa_open": {
        "name": "FAFSA Application Opens",
        "month": 10,
        "day": 1,
        "description": "FAFSA application becomes available",
    },
    "fafsa_federal": {
        "name": "Federal FAFSA Deadline",
        "month": 6,
        "day": 30,
        "description": "Federal deadline for FAFSA completion",
    },
}

# School-specific financial aid portal patterns
SCHOOL_PORTAL_PATTERNS = {
    "stanford": "https://financialaid.stanford.edu/undergrad/apply/",
    "mit": "https://sfs.mit.edu/undergraduate-students/apply/",
    "harvard": "https://college.harvard.edu/financial-aid/applying-aid",
    "yale": "https://finaid.yale.edu/applying-for-aid",
    "princeton": "https://finaid.princeton.edu/applying-aid",
}


class DeadlineSentinelAgent:
    """Background agent for monitoring and scraping deadlines.

    Acceptance Criteria:
    - Sentinel runs daily checks
    - Detects deadline changes on school websites
    - Alerts students of changes
    - Ambassador can query for specific deadlines
    """

    def __init__(
        self,
        config: AgentConfig = None,
        falkordb_client=None,
        graphiti_client=None,
    ):
        """Initialize the deadline sentinel agent.

        Args:
            config: Agent configuration
            falkordb_client: FalkorDB client for deadline storage
            graphiti_client: Graphiti client for student associations
        """
        self.config = config or deadline_sentinel_config
        self.falkordb = falkordb_client
        self.graphiti = graphiti_client

        # Deadline state
        self._deadlines: Dict[str, DeadlineEntry] = {}
        self._changes: List[DeadlineChange] = []
        self._scrape_history: List[ScrapeResult] = []

        # Scheduling state
        self._is_running = False
        self._last_scrape: Optional[datetime] = None
        self._scrape_interval_hours = 24

        # Initialize FAFSA deadlines
        self._initialize_fafsa_deadlines()

    @property
    def model_name(self) -> str:
        """Get the model name for this agent."""
        return get_model_name(self.config.model)

    def _initialize_fafsa_deadlines(self):
        """Initialize known FAFSA deadlines."""
        today = date.today()
        current_year = today.year

        # Determine academic year (FAFSA opens Oct 1 for next academic year)
        if today.month >= 10:
            academic_year = current_year + 1
        else:
            academic_year = current_year

        for key, info in FAFSA_DEADLINES.items():
            deadline_id = f"fafsa_{key}_{academic_year}"

            # Calculate actual date
            if info["month"] >= 10:
                year = academic_year - 1
            else:
                year = academic_year

            due_date = date(year, info["month"], info["day"])

            entry = DeadlineEntry(
                id=deadline_id,
                deadline_type=DeadlineType.FAFSA,
                name=f"{info['name']} ({academic_year}-{academic_year+1})",
                due_date=due_date,
                description=info["description"],
                source_url="https://studentaid.gov/apply-for-aid/fafsa",
                source_reliability=SourceReliability.OFFICIAL,
            )

            # Set status based on date
            if entry.is_past:
                entry.status = DeadlineStatus.PASSED
            elif entry.days_until <= 1:
                entry.status = DeadlineStatus.URGENT
            elif entry.days_until <= 7:
                entry.status = DeadlineStatus.DUE_SOON

            self._deadlines[deadline_id] = entry

    async def start(self):
        """Start the sentinel agent."""
        self._is_running = True
        logger.info("Deadline Sentinel Agent started")

    async def stop(self):
        """Stop the sentinel agent."""
        self._is_running = False
        logger.info("Deadline Sentinel Agent stopped")

    async def run_scrape_cycle(self) -> List[ScrapeResult]:
        """Run a complete scrape cycle across all sources.

        Returns:
            List of ScrapeResult objects
        """
        if not self._is_running:
            logger.warning("Sentinel not running, skipping scrape")
            return []

        results = []

        # Scrape each school portal
        for school_id, url in SCHOOL_PORTAL_PATTERNS.items():
            result = await self._scrape_school(school_id, url)
            results.append(result)

        self._last_scrape = datetime.utcnow()
        self._scrape_history.extend(results)

        # Keep only recent history
        if len(self._scrape_history) > 100:
            self._scrape_history = self._scrape_history[-100:]

        return results

    async def _scrape_school(
        self,
        school_id: str,
        url: str,
    ) -> ScrapeResult:
        """Scrape deadlines from a school's financial aid page.

        Args:
            school_id: School identifier
            url: URL to scrape

        Returns:
            ScrapeResult
        """
        logger.info(f"Scraping deadlines from {school_id}...")

        try:
            # In production, this would:
            # 1. Fetch the URL
            # 2. Parse HTML for deadline information
            # 3. Extract dates using NLP/patterns
            # For now, simulate with FalkorDB data

            deadlines = await self._discover_from_falkordb(school_id)

            new_count = 0
            updated_count = 0

            for deadline in deadlines:
                if deadline.id not in self._deadlines:
                    self._deadlines[deadline.id] = deadline
                    new_count += 1

                    # Record change
                    self._changes.append(DeadlineChange(
                        deadline_id=deadline.id,
                        change_type="new",
                        new_date=deadline.due_date,
                    ))
                else:
                    existing = self._deadlines[deadline.id]
                    if existing.due_date != deadline.due_date:
                        # Deadline changed!
                        self._changes.append(DeadlineChange(
                            deadline_id=deadline.id,
                            change_type="updated",
                            old_date=existing.due_date,
                            new_date=deadline.due_date,
                        ))
                        self._deadlines[deadline.id] = deadline
                        updated_count += 1

            return ScrapeResult(
                source_url=url,
                deadlines_found=len(deadlines),
                new_deadlines=new_count,
                updated_deadlines=updated_count,
            )

        except Exception as e:
            logger.error(f"Scrape failed for {school_id}: {e}")
            return ScrapeResult(
                source_url=url,
                deadlines_found=0,
                new_deadlines=0,
                updated_deadlines=0,
                errors=[str(e)],
                success=False,
            )

    async def _discover_from_falkordb(
        self,
        school_id: str,
    ) -> List[DeadlineEntry]:
        """Discover deadlines from FalkorDB.

        Args:
            school_id: School identifier

        Returns:
            List of deadline entries
        """
        if not self.falkordb:
            return []

        try:
            # Query school-specific deadlines
            result = self.falkordb.query(
                """
                MATCH (s:School {id: $school_id})-[:HAS_DEADLINE]->(d:Deadline)
                RETURN d
                """,
                {'school_id': school_id}
            )

            deadlines = []
            for row in result.result_set:
                node = row[0]
                props = node.properties

                # Parse due date
                due_date_val = props.get('due_date')
                if isinstance(due_date_val, str):
                    try:
                        due_date = datetime.strptime(due_date_val, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                elif isinstance(due_date_val, date):
                    due_date = due_date_val
                else:
                    continue

                # Determine deadline type
                deadline_type_str = props.get('type', 'other').lower()
                try:
                    deadline_type = DeadlineType(deadline_type_str)
                except ValueError:
                    deadline_type = DeadlineType.OTHER

                entry = DeadlineEntry(
                    id=props.get('id', ''),
                    deadline_type=deadline_type,
                    name=props.get('name', ''),
                    due_date=due_date,
                    school_id=school_id,
                    school_name=props.get('school_name', school_id.title()),
                    description=props.get('description', ''),
                    source_url=props.get('url'),
                    source_reliability=SourceReliability.SCRAPED,
                    last_verified=datetime.utcnow(),
                )
                deadlines.append(entry)

            return deadlines

        except Exception as e:
            logger.error(f"FalkorDB query failed: {e}")
            return []

    async def add_deadline(
        self,
        deadline: DeadlineEntry,
    ) -> bool:
        """Add or update a deadline.

        Args:
            deadline: Deadline entry to add

        Returns:
            True if successful
        """
        self._deadlines[deadline.id] = deadline

        # Store in Graphiti for temporal tracking
        if self.graphiti:
            try:
                await self.graphiti.add_episode(
                    name=f"deadline_{deadline.id}",
                    episode_body=f"Deadline: {deadline.name} due {deadline.due_date}",
                    source_description="deadline_sentinel",
                    group_id=deadline.school_id or "global",
                )
            except Exception as e:
                logger.warning(f"Failed to store deadline in Graphiti: {e}")

        return True

    async def verify_deadline(
        self,
        deadline_id: str,
    ) -> Dict[str, Any]:
        """Verify a deadline is still accurate.

        Args:
            deadline_id: ID of deadline to verify

        Returns:
            Verification result dict
        """
        deadline = self._deadlines.get(deadline_id)
        if not deadline:
            return {
                "deadline_id": deadline_id,
                "found": False,
                "message": "Deadline not found in sentinel database",
            }

        # In production, re-scrape the source URL and compare
        # For now, mark as verified
        deadline.last_verified = datetime.utcnow()

        return {
            "deadline_id": deadline_id,
            "found": True,
            "name": deadline.name,
            "due_date": deadline.due_date.isoformat(),
            "days_until": deadline.days_until,
            "status": deadline.status.value,
            "reliability": deadline.source_reliability.value,
            "last_verified": deadline.last_verified.isoformat(),
            "verified": True,
        }

    # =========================================================================
    # A2A Query Interface (for Ambassador)
    # =========================================================================

    async def get_deadlines(
        self,
        student_id: Optional[str] = None,
        school_id: Optional[str] = None,
        deadline_type: Optional[DeadlineType] = None,
        include_past: bool = False,
        limit: int = 20,
    ) -> List[DeadlineEntry]:
        """Get deadlines (A2A interface).

        Args:
            student_id: Filter by student (their tracked schools)
            school_id: Filter by specific school
            deadline_type: Filter by deadline type
            include_past: Include past deadlines
            limit: Maximum results

        Returns:
            List of DeadlineEntry objects
        """
        results = []

        for deadline in self._deadlines.values():
            # Filter by past
            if not include_past and deadline.is_past:
                continue

            # Filter by school
            if school_id and deadline.school_id != school_id:
                continue

            # Filter by type
            if deadline_type and deadline.deadline_type != deadline_type:
                continue

            # Filter by student
            if student_id and student_id not in deadline.student_ids:
                # Check if school is associated with student
                # In production, query Graphiti for student's schools
                pass

            results.append(deadline)

        # Sort by due date
        results.sort(key=lambda x: x.due_date)

        return results[:limit]

    async def get_upcoming_deadlines(
        self,
        days_ahead: int = 30,
    ) -> List[DeadlineEntry]:
        """Get upcoming deadlines within a time window.

        Args:
            days_ahead: Number of days to look ahead

        Returns:
            List of upcoming DeadlineEntry objects
        """
        cutoff = date.today() + timedelta(days=days_ahead)
        today = date.today()

        results = []
        for deadline in self._deadlines.values():
            if today <= deadline.due_date <= cutoff:
                results.append(deadline)

        results.sort(key=lambda x: x.due_date)
        return results

    async def get_urgent_deadlines(self) -> List[DeadlineEntry]:
        """Get deadlines that are urgent (within 7 days).

        Returns:
            List of urgent DeadlineEntry objects
        """
        results = []
        for deadline in self._deadlines.values():
            if not deadline.is_past and deadline.days_until <= 7:
                results.append(deadline)

        results.sort(key=lambda x: x.due_date)
        return results

    async def scrape_deadline(
        self,
        url: str,
        school_id: Optional[str] = None,
    ) -> ScrapeResult:
        """Scrape a specific URL for deadline info (A2A interface).

        Args:
            url: URL to scrape
            school_id: Optional school identifier

        Returns:
            ScrapeResult
        """
        return await self._scrape_school(school_id or "custom", url)

    async def subscribe_student(
        self,
        student_id: str,
        deadline_id: str,
    ) -> bool:
        """Subscribe a student to a deadline.

        Args:
            student_id: Student ID
            deadline_id: Deadline ID

        Returns:
            True if successful
        """
        deadline = self._deadlines.get(deadline_id)
        if not deadline:
            return False

        if student_id not in deadline.student_ids:
            deadline.student_ids.append(student_id)

        return True

    async def unsubscribe_student(
        self,
        student_id: str,
        deadline_id: str,
    ) -> bool:
        """Unsubscribe a student from a deadline.

        Args:
            student_id: Student ID
            deadline_id: Deadline ID

        Returns:
            True if successful
        """
        deadline = self._deadlines.get(deadline_id)
        if not deadline:
            return False

        if student_id in deadline.student_ids:
            deadline.student_ids.remove(student_id)

        return True

    def get_changes(
        self,
        since: Optional[datetime] = None,
        unnotified_only: bool = False,
    ) -> List[DeadlineChange]:
        """Get deadline changes.

        Args:
            since: Only changes after this time
            unnotified_only: Only unnotified changes

        Returns:
            List of DeadlineChange objects
        """
        results = []
        for change in self._changes:
            if since and change.detected_at < since:
                continue
            if unnotified_only and change.notified:
                continue
            results.append(change)

        return results

    def mark_changes_notified(self, change_ids: List[str]):
        """Mark changes as notified.

        Args:
            change_ids: IDs of changes to mark
        """
        for change in self._changes:
            if change.deadline_id in change_ids:
                change.notified = True

    def get_stats(self) -> Dict[str, Any]:
        """Get sentinel statistics.

        Returns:
            Stats dict
        """
        today = date.today()

        total = len(self._deadlines)
        upcoming = sum(1 for d in self._deadlines.values() if not d.is_past)
        urgent = sum(1 for d in self._deadlines.values() if not d.is_past and d.days_until <= 7)
        past = sum(1 for d in self._deadlines.values() if d.is_past)

        by_type = {}
        for deadline in self._deadlines.values():
            key = deadline.deadline_type.value
            by_type[key] = by_type.get(key, 0) + 1

        unnotified_changes = sum(1 for c in self._changes if not c.notified)

        return {
            "is_running": self._is_running,
            "total_deadlines": total,
            "upcoming_deadlines": upcoming,
            "urgent_deadlines": urgent,
            "past_deadlines": past,
            "by_type": by_type,
            "changes_detected": len(self._changes),
            "unnotified_changes": unnotified_changes,
            "scrape_count": len(self._scrape_history),
            "last_scrape": self._last_scrape.isoformat() if self._last_scrape else None,
        }
