"""Scholarship Scout Agent - Story 3.1

Background agent that crawls and matches scholarships.
Runs on schedule to discover new opportunities and match to anonymized profiles.
"""

import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Set
from enum import Enum

from agents.config import (
    scholarship_scout_config,
    AgentConfig,
    ModelType,
    get_model_name,
)

logger = logging.getLogger(__name__)


class CrawlStatus(Enum):
    """Status of a crawl operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LegitimacyStatus(Enum):
    """Legitimacy verification status."""
    VERIFIED = "verified"
    SUSPICIOUS = "suspicious"
    UNKNOWN = "unknown"
    SCAM = "scam"


@dataclass
class CrawlResult:
    """Result from crawling a scholarship source."""
    source_url: str
    scholarships_found: int
    new_scholarships: int
    updated_scholarships: int
    status: CrawlStatus
    crawled_at: datetime = field(default_factory=datetime.utcnow)
    errors: List[str] = field(default_factory=list)


@dataclass
class ScholarshipDiscovery:
    """A newly discovered or updated scholarship."""
    id: str
    name: str
    source_url: str
    amount_min: float
    amount_max: float
    deadline: Optional[date]
    criteria: str
    eligibility: List[str]
    how_to_apply: str
    legitimacy: LegitimacyStatus
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    last_verified: Optional[datetime] = None


@dataclass
class ProfileMatch:
    """A match between a scholarship and an anonymized profile."""
    scholarship_id: str
    profile_id: str
    match_score: float
    match_reasons: List[str]
    matched_at: datetime = field(default_factory=datetime.utcnow)


# Known scholarship databases to crawl
SCHOLARSHIP_SOURCES = [
    {
        "name": "Fastweb",
        "url": "https://www.fastweb.com",
        "type": "aggregator",
    },
    {
        "name": "Scholarships.com",
        "url": "https://www.scholarships.com",
        "type": "aggregator",
    },
    {
        "name": "College Board BigFuture",
        "url": "https://bigfuture.collegeboard.org/scholarships",
        "type": "official",
    },
    {
        "name": "Cappex",
        "url": "https://www.cappex.com",
        "type": "aggregator",
    },
    {
        "name": "Unigo",
        "url": "https://www.unigo.com",
        "type": "aggregator",
    },
]

# Red flags for scam detection
SCAM_RED_FLAGS = [
    "fee required",
    "payment required",
    "credit card",
    "wire transfer",
    "guaranteed winner",
    "you've been selected",
    "act now",
    "limited time",
    "processing fee",
    "application fee",
]


class ScholarshipScoutAgent:
    """Background agent for discovering and matching scholarships.

    Acceptance Criteria:
    - Scout runs on schedule
    - Scout finds new scholarships
    - Scout matches scholarships to anonymized profiles
    - Ambassador can query Scout via A2A
    """

    def __init__(
        self,
        config: AgentConfig = None,
        falkordb_client=None,
        graphiti_client=None,
    ):
        """Initialize the scholarship scout agent.

        Args:
            config: Agent configuration
            falkordb_client: FalkorDB client for commons graph
            graphiti_client: Graphiti client for temporal data
        """
        self.config = config or scholarship_scout_config
        self.falkordb = falkordb_client
        self.graphiti = graphiti_client

        # Discovery state
        self._known_scholarships: Set[str] = set()
        self._crawl_history: List[CrawlResult] = []
        self._discoveries: Dict[str, ScholarshipDiscovery] = {}
        self._matches: Dict[str, List[ProfileMatch]] = {}  # profile_id -> matches

        # Scheduling state
        self._is_running = False
        self._last_crawl: Optional[datetime] = None
        self._crawl_interval_hours = 6

    @property
    def model_name(self) -> str:
        """Get the model name for this agent."""
        return get_model_name(self.config.model)

    async def start(self):
        """Start the scout agent (begins scheduled crawling)."""
        self._is_running = True
        logger.info("Scholarship Scout Agent started")

    async def stop(self):
        """Stop the scout agent."""
        self._is_running = False
        logger.info("Scholarship Scout Agent stopped")

    async def run_crawl_cycle(self) -> List[CrawlResult]:
        """Run a complete crawl cycle across all sources.

        Returns:
            List of CrawlResult objects
        """
        if not self._is_running:
            logger.warning("Scout not running, skipping crawl")
            return []

        results = []
        for source in SCHOLARSHIP_SOURCES:
            result = await self._crawl_source(source)
            results.append(result)

        self._last_crawl = datetime.utcnow()
        self._crawl_history.extend(results)

        # Keep only recent history
        if len(self._crawl_history) > 100:
            self._crawl_history = self._crawl_history[-100:]

        return results

    async def _crawl_source(
        self,
        source: Dict[str, str],
    ) -> CrawlResult:
        """Crawl a single scholarship source.

        Args:
            source: Source configuration

        Returns:
            CrawlResult
        """
        logger.info(f"Crawling {source['name']}...")

        try:
            # In production, this would actually fetch and parse the source
            # For now, simulate discovery from FalkorDB commons
            discoveries = await self._discover_from_commons(source)

            new_count = 0
            updated_count = 0

            for discovery in discoveries:
                if discovery.id not in self._known_scholarships:
                    self._known_scholarships.add(discovery.id)
                    new_count += 1
                else:
                    updated_count += 1

                self._discoveries[discovery.id] = discovery

            return CrawlResult(
                source_url=source['url'],
                scholarships_found=len(discoveries),
                new_scholarships=new_count,
                updated_scholarships=updated_count,
                status=CrawlStatus.COMPLETED,
            )

        except Exception as e:
            logger.error(f"Crawl failed for {source['name']}: {e}")
            return CrawlResult(
                source_url=source['url'],
                scholarships_found=0,
                new_scholarships=0,
                updated_scholarships=0,
                status=CrawlStatus.FAILED,
                errors=[str(e)],
            )

    async def _discover_from_commons(
        self,
        source: Dict[str, str],
    ) -> List[ScholarshipDiscovery]:
        """Discover scholarships from commons graph.

        Args:
            source: Source configuration

        Returns:
            List of discovered scholarships
        """
        if not self.falkordb:
            return []

        try:
            result = self.falkordb.get_all_scholarship_sources()

            discoveries = []
            for row in result.result_set:
                node = row[0]
                props = node.properties

                # Parse deadline
                deadline = None
                deadline_val = props.get('deadline')
                if deadline_val:
                    if isinstance(deadline_val, str):
                        try:
                            deadline = datetime.strptime(deadline_val, "%Y-%m-%d").date()
                        except ValueError:
                            pass
                    elif isinstance(deadline_val, date):
                        deadline = deadline_val

                # Check legitimacy
                legitimacy = await self._verify_legitimacy(props)

                discovery = ScholarshipDiscovery(
                    id=props.get('id', ''),
                    name=props.get('name', ''),
                    source_url=props.get('url', source['url']),
                    amount_min=float(props.get('amount_min', 0)),
                    amount_max=float(props.get('amount_max', 0)),
                    deadline=deadline,
                    criteria=props.get('criteria', ''),
                    eligibility=[props.get('criteria', '')],
                    how_to_apply="See scholarship website",
                    legitimacy=legitimacy,
                    last_verified=datetime.utcnow() if legitimacy == LegitimacyStatus.VERIFIED else None,
                )
                discoveries.append(discovery)

            return discoveries

        except Exception as e:
            logger.error(f"Discovery from commons failed: {e}")
            return []

    async def _verify_legitimacy(
        self,
        scholarship_props: Dict[str, Any],
    ) -> LegitimacyStatus:
        """Verify the legitimacy of a scholarship.

        Args:
            scholarship_props: Scholarship properties

        Returns:
            LegitimacyStatus
        """
        name = scholarship_props.get('name', '').lower()
        criteria = scholarship_props.get('criteria', '').lower()
        url = scholarship_props.get('url', '').lower()

        combined_text = f"{name} {criteria} {url}"

        # Check for red flags
        red_flag_count = sum(
            1 for flag in SCAM_RED_FLAGS if flag in combined_text
        )

        if red_flag_count >= 2:
            return LegitimacyStatus.SCAM
        elif red_flag_count == 1:
            return LegitimacyStatus.SUSPICIOUS

        # Check if verified in props
        if scholarship_props.get('verified', False):
            return LegitimacyStatus.VERIFIED

        return LegitimacyStatus.UNKNOWN

    async def match_to_profiles(
        self,
        profile_ids: List[str],
        min_score: float = 0.6,
    ) -> Dict[str, List[ProfileMatch]]:
        """Match discovered scholarships to anonymized profiles.

        Args:
            profile_ids: List of anonymized profile IDs
            min_score: Minimum match score

        Returns:
            Dict mapping profile_id to list of matches
        """
        all_matches: Dict[str, List[ProfileMatch]] = {}

        for profile_id in profile_ids:
            matches = await self._match_profile(profile_id, min_score)
            all_matches[profile_id] = matches
            self._matches[profile_id] = matches

        return all_matches

    async def _match_profile(
        self,
        profile_id: str,
        min_score: float,
    ) -> List[ProfileMatch]:
        """Match scholarships to a single profile.

        Args:
            profile_id: Anonymized profile ID
            min_score: Minimum match score

        Returns:
            List of ProfileMatch objects
        """
        matches = []

        # Get profile data from Graphiti if available
        profile_data = await self._get_profile_data(profile_id)

        for scholarship_id, discovery in self._discoveries.items():
            # Skip scams
            if discovery.legitimacy == LegitimacyStatus.SCAM:
                continue

            # Calculate match score
            score, reasons = self._calculate_match_score(
                profile_data, discovery
            )

            if score >= min_score:
                match = ProfileMatch(
                    scholarship_id=scholarship_id,
                    profile_id=profile_id,
                    match_score=score,
                    match_reasons=reasons,
                )
                matches.append(match)

        # Sort by score
        matches.sort(key=lambda x: x.match_score, reverse=True)

        return matches

    async def _get_profile_data(
        self,
        profile_id: str,
    ) -> Dict[str, Any]:
        """Get anonymized profile data.

        Args:
            profile_id: Profile ID

        Returns:
            Profile data dict
        """
        if not self.graphiti:
            return {}

        try:
            results = await self.graphiti.search(
                query=f"profile {profile_id}",
                num_results=10,
                group_ids=[profile_id],
            )

            profile_data = {}
            for result in results:
                # Extract profile attributes from facts
                fact = result.get('fact', '')
                # Simple parsing - in production use NLP
                if 'gpa' in fact.lower():
                    profile_data['gpa_mentioned'] = True
                if 'first-gen' in fact.lower() or 'first generation' in fact.lower():
                    profile_data['first_gen'] = True
                if any(field in fact.lower() for field in ['stem', 'engineering', 'science', 'math']):
                    profile_data['stem_interest'] = True

            return profile_data

        except Exception as e:
            logger.warning(f"Could not get profile data: {e}")
            return {}

    def _calculate_match_score(
        self,
        profile_data: Dict[str, Any],
        discovery: ScholarshipDiscovery,
    ) -> tuple[float, List[str]]:
        """Calculate match score between profile and scholarship.

        Args:
            profile_data: Profile data
            discovery: Scholarship discovery

        Returns:
            Tuple of (score, reasons)
        """
        score = 0.5  # Base score
        reasons = []

        criteria_lower = discovery.criteria.lower()

        # First-gen matching
        if profile_data.get('first_gen') and 'first' in criteria_lower:
            score += 0.15
            reasons.append("First-generation student eligible")

        # STEM matching
        if profile_data.get('stem_interest') and any(
            field in criteria_lower for field in ['stem', 'engineering', 'science', 'math']
        ):
            score += 0.15
            reasons.append("STEM field match")

        # High value bonus
        if discovery.amount_max >= 10000:
            score += 0.1
            reasons.append("High-value scholarship")

        # Verified bonus
        if discovery.legitimacy == LegitimacyStatus.VERIFIED:
            score += 0.1
            reasons.append("Verified scholarship")

        # Deadline proximity bonus (if within 60 days, boost priority)
        if discovery.deadline:
            days_until = (discovery.deadline - date.today()).days
            if 0 < days_until <= 60:
                score += 0.05
                reasons.append(f"Deadline in {days_until} days")

        if not reasons:
            reasons.append("General eligibility")

        return min(score, 1.0), reasons

    # =========================================================================
    # A2A Query Interface (for Ambassador)
    # =========================================================================

    async def query_scholarships(
        self,
        query: str,
        profile_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[ScholarshipDiscovery]:
        """Query discovered scholarships (A2A interface).

        Args:
            query: Search query
            profile_id: Optional profile ID for personalized results
            limit: Maximum results

        Returns:
            List of matching ScholarshipDiscovery objects
        """
        query_lower = query.lower()
        results = []

        for discovery in self._discoveries.values():
            # Skip scams
            if discovery.legitimacy == LegitimacyStatus.SCAM:
                continue

            # Simple text matching
            searchable = f"{discovery.name} {discovery.criteria}".lower()
            if query_lower in searchable:
                results.append(discovery)

        # If profile_id provided, sort by match score
        if profile_id and profile_id in self._matches:
            match_scores = {m.scholarship_id: m.match_score for m in self._matches[profile_id]}
            results.sort(
                key=lambda x: match_scores.get(x.id, 0),
                reverse=True
            )

        return results[:limit]

    async def get_matches_for_profile(
        self,
        profile_id: str,
    ) -> List[ProfileMatch]:
        """Get scholarship matches for a profile (A2A interface).

        Args:
            profile_id: Anonymized profile ID

        Returns:
            List of ProfileMatch objects
        """
        return self._matches.get(profile_id, [])

    async def verify_scholarship(
        self,
        scholarship_id: str,
    ) -> Dict[str, Any]:
        """Verify a specific scholarship (A2A interface).

        Args:
            scholarship_id: Scholarship ID

        Returns:
            Verification result dict
        """
        discovery = self._discoveries.get(scholarship_id)
        if not discovery:
            return {
                'scholarship_id': scholarship_id,
                'found': False,
                'message': 'Scholarship not found in scout database',
            }

        return {
            'scholarship_id': scholarship_id,
            'found': True,
            'name': discovery.name,
            'legitimacy': discovery.legitimacy.value,
            'verified': discovery.legitimacy == LegitimacyStatus.VERIFIED,
            'last_verified': discovery.last_verified.isoformat() if discovery.last_verified else None,
            'warnings': ['Legitimacy unknown - research before applying']
                if discovery.legitimacy == LegitimacyStatus.UNKNOWN else [],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get scout statistics.

        Returns:
            Stats dict
        """
        legitimacy_counts = {}
        for discovery in self._discoveries.values():
            key = discovery.legitimacy.value
            legitimacy_counts[key] = legitimacy_counts.get(key, 0) + 1

        return {
            'is_running': self._is_running,
            'total_scholarships': len(self._discoveries),
            'known_scholarships': len(self._known_scholarships),
            'profiles_matched': len(self._matches),
            'crawl_count': len(self._crawl_history),
            'last_crawl': self._last_crawl.isoformat() if self._last_crawl else None,
            'by_legitimacy': legitimacy_counts,
        }
