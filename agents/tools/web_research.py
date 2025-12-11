"""Web Research Tool - Story 2.2

Fetches scholarship and financial aid information from the web.
Supports searching for scholarship details, deadlines, and eligibility criteria.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum
import re

logger = logging.getLogger(__name__)


class ResearchType(Enum):
    """Types of web research."""
    SCHOLARSHIP = "scholarship"
    SCHOOL = "school"
    FINANCIAL_AID = "financial_aid"
    FAFSA = "fafsa"
    GENERAL = "general"


@dataclass
class ResearchResult:
    """A web research result."""
    title: str
    url: str
    snippet: str
    source: str
    research_type: ResearchType
    relevance_score: float = 0.0
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScholarshipInfo:
    """Extracted scholarship information."""
    name: str
    url: str
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    deadline: Optional[str] = None
    eligibility: List[str] = field(default_factory=list)
    how_to_apply: str = ""
    verified: bool = False
    last_updated: datetime = field(default_factory=datetime.utcnow)


# Known scholarship databases and resources
SCHOLARSHIP_SOURCES = [
    {
        "name": "Fastweb",
        "url": "https://www.fastweb.com",
        "type": ResearchType.SCHOLARSHIP,
    },
    {
        "name": "Scholarships.com",
        "url": "https://www.scholarships.com",
        "type": ResearchType.SCHOLARSHIP,
    },
    {
        "name": "College Board",
        "url": "https://bigfuture.collegeboard.org/scholarships",
        "type": ResearchType.SCHOLARSHIP,
    },
    {
        "name": "Federal Student Aid",
        "url": "https://studentaid.gov",
        "type": ResearchType.FAFSA,
    },
    {
        "name": "Cappex",
        "url": "https://www.cappex.com",
        "type": ResearchType.SCHOLARSHIP,
    },
]


class WebResearchTool:
    """Tool for researching scholarship and financial aid information.

    Acceptance Criteria:
    - web_research can fetch scholarship info

    Note: In production, this would integrate with actual web scraping
    or search APIs. For now, it provides a framework and mock data.
    """

    def __init__(self, http_client=None, cache_ttl_minutes: int = 60):
        """Initialize web research tool.

        Args:
            http_client: HTTP client for web requests (optional)
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.http_client = http_client
        self.cache_ttl_minutes = cache_ttl_minutes
        self._cache: Dict[str, ResearchResult] = {}

    async def search_scholarships(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[ResearchResult]:
        """Search for scholarships based on query.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of ResearchResult objects
        """
        logger.info(f"Searching scholarships: {query}")

        results = []

        # In production, this would call search APIs
        # For now, return relevant known sources
        query_lower = query.lower()

        for source in SCHOLARSHIP_SOURCES:
            if source["type"] == ResearchType.SCHOLARSHIP:
                relevance = self._calculate_relevance(query_lower, source["name"])

                result = ResearchResult(
                    title=f"{source['name']} - Scholarship Search",
                    url=source["url"],
                    snippet=f"Search for scholarships matching '{query}' on {source['name']}",
                    source=source["name"],
                    research_type=ResearchType.SCHOLARSHIP,
                    relevance_score=relevance,
                )
                results.append(result)

        # Sort by relevance
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results[:max_results]

    async def fetch_scholarship_details(
        self,
        scholarship_name: str,
        scholarship_url: Optional[str] = None,
    ) -> Optional[ScholarshipInfo]:
        """Fetch detailed information about a specific scholarship.

        Args:
            scholarship_name: Name of the scholarship
            scholarship_url: Optional URL to fetch from

        Returns:
            ScholarshipInfo or None
        """
        logger.info(f"Fetching scholarship details: {scholarship_name}")

        # In production, this would scrape the scholarship page
        # For now, return a mock response for known scholarships

        known_scholarships = self._get_known_scholarship_info()

        name_lower = scholarship_name.lower()
        for scholarship in known_scholarships:
            if name_lower in scholarship.name.lower():
                return scholarship

        # Return a placeholder for unknown scholarships
        return ScholarshipInfo(
            name=scholarship_name,
            url=scholarship_url or "",
            eligibility=["See scholarship website for eligibility requirements"],
            how_to_apply="Visit the scholarship website for application details",
            verified=False,
        )

    def _get_known_scholarship_info(self) -> List[ScholarshipInfo]:
        """Get information about well-known scholarships.

        Returns:
            List of known scholarship information
        """
        return [
            ScholarshipInfo(
                name="Gates Scholarship",
                url="https://www.thegatesscholarship.org",
                amount_min=50000,
                amount_max=300000,
                deadline="September 15",
                eligibility=[
                    "High school senior",
                    "Pell Grant eligible",
                    "Minimum 3.3 GPA",
                    "U.S. citizen or permanent resident",
                ],
                how_to_apply="Apply online at thegatesscholarship.org",
                verified=True,
            ),
            ScholarshipInfo(
                name="Coca-Cola Scholars Program",
                url="https://www.coca-colascholarsfoundation.org",
                amount_min=20000,
                amount_max=20000,
                deadline="October 31",
                eligibility=[
                    "High school senior",
                    "Minimum 3.0 GPA",
                    "U.S. citizen or permanent resident",
                    "Planning to attend accredited U.S. college",
                ],
                how_to_apply="Apply online through the Coca-Cola Scholars portal",
                verified=True,
            ),
            ScholarshipInfo(
                name="Dell Scholars Program",
                url="https://www.dellscholars.org",
                amount_min=20000,
                amount_max=20000,
                deadline="December 1",
                eligibility=[
                    "High school senior",
                    "Pell Grant eligible",
                    "Minimum 2.4 GPA",
                    "Participating in college readiness program",
                ],
                how_to_apply="Apply through the Dell Scholars portal",
                verified=True,
            ),
            ScholarshipInfo(
                name="Jack Kent Cooke Foundation College Scholarship",
                url="https://www.jkcf.org",
                amount_min=40000,
                amount_max=40000,
                deadline="November 18",
                eligibility=[
                    "High school senior",
                    "Family income under $95,000",
                    "Minimum 3.5 GPA",
                    "Top 15% of graduating class",
                ],
                how_to_apply="Apply online at jkcf.org",
                verified=True,
            ),
        ]

    async def search_fafsa_info(
        self,
        topic: str,
    ) -> List[ResearchResult]:
        """Search for FAFSA and federal aid information.

        Args:
            topic: FAFSA-related topic to search

        Returns:
            List of ResearchResult objects
        """
        logger.info(f"Searching FAFSA info: {topic}")

        # Return known FAFSA resources
        results = []

        fafsa_topics = {
            "deadline": {
                "title": "FAFSA Deadlines",
                "snippet": "Federal deadline is June 30, but state and school deadlines vary. Apply early!",
            },
            "eligibility": {
                "title": "FAFSA Eligibility Requirements",
                "snippet": "Must be a U.S. citizen or eligible noncitizen, have a valid SSN, and more.",
            },
            "application": {
                "title": "How to Complete the FAFSA",
                "snippet": "Complete at studentaid.gov using your FSA ID. Have tax returns ready.",
            },
            "efc": {
                "title": "Expected Family Contribution (EFC)",
                "snippet": "EFC determines your federal aid eligibility based on family finances.",
            },
        }

        topic_lower = topic.lower()
        for key, info in fafsa_topics.items():
            if key in topic_lower or topic_lower in key:
                result = ResearchResult(
                    title=info["title"],
                    url="https://studentaid.gov",
                    snippet=info["snippet"],
                    source="Federal Student Aid",
                    research_type=ResearchType.FAFSA,
                    relevance_score=0.9,
                )
                results.append(result)

        # Always include the main FAFSA resource
        results.append(ResearchResult(
            title="Official FAFSA Website",
            url="https://studentaid.gov/h/apply-for-aid/fafsa",
            snippet="Apply for federal student aid at the official FAFSA website.",
            source="Federal Student Aid",
            research_type=ResearchType.FAFSA,
            relevance_score=0.8,
        ))

        return results

    async def search_school_info(
        self,
        school_name: str,
        info_type: str = "financial_aid",
    ) -> List[ResearchResult]:
        """Search for school-specific information.

        Args:
            school_name: Name of the school
            info_type: Type of info (financial_aid, deadlines, etc.)

        Returns:
            List of ResearchResult objects
        """
        logger.info(f"Searching school info: {school_name} - {info_type}")

        results = []

        # Common info types
        if info_type == "financial_aid":
            results.append(ResearchResult(
                title=f"{school_name} Financial Aid Office",
                url=f"https://www.google.com/search?q={school_name}+financial+aid",
                snippet=f"Contact {school_name}'s financial aid office for specific aid packages and requirements.",
                source="School Website",
                research_type=ResearchType.SCHOOL,
                relevance_score=0.9,
            ))

        elif info_type == "net_price":
            results.append(ResearchResult(
                title=f"{school_name} Net Price Calculator",
                url=f"https://www.google.com/search?q={school_name}+net+price+calculator",
                snippet=f"Use {school_name}'s net price calculator to estimate your actual cost.",
                source="School Website",
                research_type=ResearchType.SCHOOL,
                relevance_score=0.9,
            ))

        elif info_type == "deadlines":
            results.append(ResearchResult(
                title=f"{school_name} Application Deadlines",
                url=f"https://www.google.com/search?q={school_name}+application+deadlines",
                snippet=f"Find {school_name}'s application and financial aid deadlines.",
                source="School Website",
                research_type=ResearchType.SCHOOL,
                relevance_score=0.9,
            ))

        return results

    def _calculate_relevance(self, query: str, text: str) -> float:
        """Calculate relevance score between query and text.

        Args:
            query: Search query
            text: Text to compare

        Returns:
            Relevance score (0-1)
        """
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())

        if not query_words or not text_words:
            return 0.5

        overlap = len(query_words & text_words)
        relevance = overlap / len(query_words) if query_words else 0

        return min(relevance + 0.5, 1.0)  # Base score of 0.5

    async def verify_scholarship(
        self,
        scholarship_name: str,
        scholarship_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify if a scholarship is legitimate.

        Args:
            scholarship_name: Name of scholarship
            scholarship_url: URL to verify

        Returns:
            Verification result dict
        """
        logger.info(f"Verifying scholarship: {scholarship_name}")

        # Red flags to check for
        red_flags = [
            "fee",
            "payment required",
            "guarantee",
            "credit card",
            "purchase",
            "wire transfer",
        ]

        verification = {
            "scholarship_name": scholarship_name,
            "verified": False,
            "warnings": [],
            "recommendation": "",
        }

        # Check for red flags in name
        name_lower = scholarship_name.lower()
        for flag in red_flags:
            if flag in name_lower:
                verification["warnings"].append(
                    f"Warning: '{flag}' mentioned - legitimate scholarships never require payment"
                )

        # Check against known legitimate scholarships
        known = self._get_known_scholarship_info()
        for ks in known:
            if name_lower in ks.name.lower():
                verification["verified"] = True
                verification["recommendation"] = "This is a known legitimate scholarship."
                break

        if not verification["verified"] and not verification["warnings"]:
            verification["recommendation"] = (
                "Could not verify this scholarship. Research carefully before applying. "
                "Never pay fees to apply for scholarships."
            )

        return verification

    def get_scholarship_sources(self) -> List[Dict[str, str]]:
        """Get list of known scholarship search sources.

        Returns:
            List of scholarship source dictionaries
        """
        return [
            {"name": s["name"], "url": s["url"]}
            for s in SCHOLARSHIP_SOURCES
            if s["type"] == ResearchType.SCHOLARSHIP
        ]
