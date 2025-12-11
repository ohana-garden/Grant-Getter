"""Scholarship Search Tool - Story 2.2

Searches FalkorDB commons graph for scholarships matching student criteria.
Returns matches from FalkorDB with relevance scoring.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScholarshipMatch:
    """A scholarship match result."""
    id: str
    name: str
    amount_min: float
    amount_max: float
    criteria: str
    deadline: Optional[date]
    match_score: float
    match_reasons: List[str] = field(default_factory=list)
    url: str = ""
    renewable: bool = False
    verified: bool = True


@dataclass
class StudentProfile:
    """Anonymized student profile for matching."""
    gpa_range: Optional[str] = None  # e.g., "3.5-4.0"
    test_range: Optional[str] = None  # e.g., "1400-1500"
    income_bracket: Optional[str] = None
    first_gen: Optional[bool] = None
    major_interest: Optional[str] = None
    state: Optional[str] = None
    activities: List[str] = field(default_factory=list)


class ScholarshipSearchTool:
    """Tool for searching scholarships from FalkorDB commons graph.

    Acceptance Criteria:
    - scholarship_search returns matches from FalkorDB
    """

    def __init__(self, falkordb_client=None):
        """Initialize scholarship search tool.

        Args:
            falkordb_client: FalkorDB client for commons graph queries
        """
        self.falkordb = falkordb_client
        self._cache: Dict[str, List[ScholarshipMatch]] = {}

    async def search(
        self,
        profile: Optional[StudentProfile] = None,
        query: Optional[str] = None,
        min_amount: float = 0,
        max_amount: Optional[float] = None,
        deadline_after: Optional[date] = None,
        limit: int = 20,
    ) -> List[ScholarshipMatch]:
        """Search for scholarships matching criteria.

        Args:
            profile: Student profile for matching (anonymized)
            query: Text query for criteria search
            min_amount: Minimum scholarship amount
            max_amount: Maximum scholarship amount (None = no limit)
            deadline_after: Only return scholarships with deadline after this date
            limit: Maximum number of results

        Returns:
            List of ScholarshipMatch objects sorted by match score
        """
        if not self.falkordb:
            logger.warning("No FalkorDB client - returning empty results")
            return []

        try:
            # Get all scholarships from FalkorDB
            result = self.falkordb.get_all_scholarship_sources()

            matches = []
            for row in result.result_set:
                node = row[0]
                props = node.properties

                # Parse deadline
                deadline = None
                if 'deadline' in props:
                    deadline_val = props['deadline']
                    if isinstance(deadline_val, str):
                        try:
                            deadline = datetime.strptime(deadline_val, "%Y-%m-%d").date()
                        except ValueError:
                            pass
                    elif isinstance(deadline_val, date):
                        deadline = deadline_val

                # Apply filters
                amount_min = float(props.get('amount_min', 0))
                amount_max_val = float(props.get('amount_max', 0))

                if amount_max_val < min_amount:
                    continue
                if max_amount and amount_min > max_amount:
                    continue
                if deadline_after and deadline and deadline < deadline_after:
                    continue

                # Calculate match score
                score, reasons = self._calculate_match_score(
                    props, profile, query
                )

                match = ScholarshipMatch(
                    id=props.get('id', ''),
                    name=props.get('name', ''),
                    amount_min=amount_min,
                    amount_max=amount_max_val,
                    criteria=props.get('criteria', ''),
                    deadline=deadline,
                    match_score=score,
                    match_reasons=reasons,
                    url=props.get('url', ''),
                    renewable=props.get('renewable', False),
                    verified=props.get('verified', True),
                )
                matches.append(match)

            # Sort by match score (descending)
            matches.sort(key=lambda x: x.match_score, reverse=True)

            return matches[:limit]

        except Exception as e:
            logger.error(f"Scholarship search failed: {e}")
            return []

    def _calculate_match_score(
        self,
        scholarship_props: Dict[str, Any],
        profile: Optional[StudentProfile],
        query: Optional[str],
    ) -> tuple[float, List[str]]:
        """Calculate match score between scholarship and profile.

        Args:
            scholarship_props: Scholarship properties from graph
            profile: Student profile (may be None)
            query: Text query (may be None)

        Returns:
            Tuple of (score, list of match reasons)
        """
        score = 0.5  # Base score
        reasons = []

        criteria = scholarship_props.get('criteria', '').lower()
        name = scholarship_props.get('name', '').lower()

        # Query matching
        if query:
            query_lower = query.lower()
            if query_lower in criteria or query_lower in name:
                score += 0.2
                reasons.append(f"Matches search: {query}")

        # Profile matching (when available)
        if profile:
            # First generation matching
            if profile.first_gen and 'first-gen' in criteria or 'first generation' in criteria:
                score += 0.15
                reasons.append("First-generation student eligible")

            # Major/field matching
            if profile.major_interest:
                major_lower = profile.major_interest.lower()
                if major_lower in criteria:
                    score += 0.15
                    reasons.append(f"Matches major: {profile.major_interest}")

            # State matching
            if profile.state:
                state_lower = profile.state.lower()
                if state_lower in criteria:
                    score += 0.1
                    reasons.append(f"State eligible: {profile.state}")

            # Income bracket matching
            if profile.income_bracket and 'need-based' in criteria:
                score += 0.1
                reasons.append("Need-based eligibility")

            # Activities matching
            for activity in profile.activities:
                if activity.lower() in criteria:
                    score += 0.05
                    reasons.append(f"Activity match: {activity}")

        # High value bonus
        amount_max = float(scholarship_props.get('amount_max', 0))
        if amount_max >= 10000:
            score += 0.05
            reasons.append("High-value scholarship")

        # Verified bonus
        if scholarship_props.get('verified', False):
            score += 0.05
            reasons.append("Verified scholarship")

        # Renewable bonus
        if scholarship_props.get('renewable', False):
            score += 0.05
            reasons.append("Renewable scholarship")

        # Cap score at 1.0
        score = min(score, 1.0)

        if not reasons:
            reasons.append("General eligibility")

        return score, reasons

    async def search_by_criteria(
        self,
        criteria_keywords: List[str],
        limit: int = 10,
    ) -> List[ScholarshipMatch]:
        """Search scholarships by criteria keywords.

        Args:
            criteria_keywords: List of keywords to match in criteria
            limit: Maximum results

        Returns:
            Matching scholarships
        """
        if not self.falkordb:
            return []

        try:
            # Build Cypher query with OR conditions
            conditions = " OR ".join([
                f"toLower(s.criteria) CONTAINS '{kw.lower()}'"
                for kw in criteria_keywords
            ])

            result = self.falkordb.query(
                f"""
                MATCH (s:ScholarshipSource)
                WHERE {conditions}
                RETURN s
                LIMIT {limit}
                """
            )

            matches = []
            for row in result.result_set:
                node = row[0]
                props = node.properties

                # Count keyword matches for scoring
                criteria_lower = props.get('criteria', '').lower()
                keyword_matches = sum(
                    1 for kw in criteria_keywords if kw.lower() in criteria_lower
                )
                score = min(0.5 + (keyword_matches * 0.1), 1.0)

                match = ScholarshipMatch(
                    id=props.get('id', ''),
                    name=props.get('name', ''),
                    amount_min=float(props.get('amount_min', 0)),
                    amount_max=float(props.get('amount_max', 0)),
                    criteria=props.get('criteria', ''),
                    deadline=None,
                    match_score=score,
                    match_reasons=[f"Matches keywords: {', '.join(criteria_keywords)}"],
                )
                matches.append(match)

            return matches

        except Exception as e:
            logger.error(f"Criteria search failed: {e}")
            return []

    async def get_scholarship_details(
        self,
        scholarship_id: str,
    ) -> Optional[ScholarshipMatch]:
        """Get detailed information about a specific scholarship.

        Args:
            scholarship_id: Scholarship ID to look up

        Returns:
            ScholarshipMatch with full details, or None if not found
        """
        if not self.falkordb:
            return None

        try:
            result = self.falkordb.query(
                "MATCH (s:ScholarshipSource {id: $id}) RETURN s",
                {'id': scholarship_id}
            )

            if not result.result_set:
                return None

            node = result.result_set[0][0]
            props = node.properties

            return ScholarshipMatch(
                id=props.get('id', ''),
                name=props.get('name', ''),
                amount_min=float(props.get('amount_min', 0)),
                amount_max=float(props.get('amount_max', 0)),
                criteria=props.get('criteria', ''),
                deadline=props.get('deadline'),
                match_score=1.0,
                match_reasons=["Direct lookup"],
                url=props.get('url', ''),
                renewable=props.get('renewable', False),
                verified=props.get('verified', True),
            )

        except Exception as e:
            logger.error(f"Scholarship lookup failed: {e}")
            return None
