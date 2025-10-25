"""
Grant Discovery Tool for Agent Zero

Searches Grants.gov API and other grant sources for matching opportunities.
Returns ranked list with relevance scores.
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
from dataclasses import dataclass, asdict


@dataclass
class GrantOpportunity:
    """Structured grant opportunity data"""
    id: str
    title: str
    funder: str
    source: str
    deadline: str
    amount_min: Optional[int]
    amount_max: Optional[int]
    eligibility: List[str]
    topic_areas: List[str]
    description: str
    url: str
    relevance_score: float
    
    def to_dict(self):
        return asdict(self)


class GrantDiscovery:
    """
    Grant Discovery Tool for Agent Zero
    
    Searches multiple grant sources and returns ranked opportunities.
    Compatible with Agent Zero's tool system.
    """
    
    def __init__(self, agent=None, **kwargs):
        """Initialize tool with agent context"""
        self.agent = agent
        self.name = "grant_discovery"
        self.args = kwargs
        
        # API endpoints
        self.grants_gov_api = "https://www.grants.gov/grantsws/rest/opportunities/search"
        self.api_key = os.getenv('GRANTS_GOV_API_KEY', '')
        
    async def execute(
        self,
        keywords: str = "",
        org_type: str = "nonprofit",
        topic_areas: Optional[List[str]] = None,
        max_results: int = 10,
        min_amount: Optional[int] = None,
        deadline_within_days: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Search for grant opportunities
        
        Args:
            keywords: Search keywords (e.g., "education youth development")
            org_type: Organization type (nonprofit, tribal, university, local_government)
            topic_areas: List of topic areas (education, health, environment, etc.)
            max_results: Maximum number of results (default 10)
            min_amount: Minimum grant amount filter
            deadline_within_days: Only show grants due within X days
            
        Returns:
            Dict with:
                - opportunities: List[GrantOpportunity]
                - total_found: int
                - search_params: Dict
                - message: str
        """
        
        try:
            # Build search parameters
            search_params = {
                'keywords': keywords,
                'org_type': org_type,
                'topic_areas': topic_areas or [],
                'max_results': max_results,
                'min_amount': min_amount,
                'deadline_within_days': deadline_within_days
            }
            
            # Search Grants.gov
            grants_gov_results = await self._search_grants_gov(
                keywords=keywords,
                org_type=org_type,
                max_results=max_results
            )
            
            # Filter and rank results
            filtered = self._filter_opportunities(
                grants_gov_results,
                min_amount=min_amount,
                deadline_within_days=deadline_within_days,
                topic_areas=topic_areas
            )
            
            # Calculate relevance scores
            ranked = self._rank_opportunities(filtered, keywords, org_type, topic_areas)
            
            # Sort by relevance
            ranked.sort(key=lambda x: x.relevance_score, reverse=True)
            
            # Limit results
            top_results = ranked[:max_results]
            
            # Format response
            return {
                'opportunities': [opp.to_dict() for opp in top_results],
                'total_found': len(ranked),
                'search_params': search_params,
                'message': f"Found {len(top_results)} relevant grant opportunities"
            }
            
        except Exception as e:
            return {
                'opportunities': [],
                'total_found': 0,
                'error': str(e),
                'message': f"Error searching grants: {str(e)}"
            }
    
    async def _search_grants_gov(
        self,
        keywords: str,
        org_type: str,
        max_results: int
    ) -> List[GrantOpportunity]:
        """
        Search Grants.gov API
        
        Note: This uses mock data. In production, replace with actual API calls.
        """
        
        # MOCK DATA - Replace with actual API call in production
        # In production, use:
        # headers = {'Authorization': f'Bearer {self.api_key}'}
        # response = requests.post(self.grants_gov_api, json=query, headers=headers)
        
        mock_grants = self._generate_mock_grants(keywords, org_type)
        
        return mock_grants[:max_results * 2]  # Get extra for filtering
    
    def _generate_mock_grants(self, keywords: str, org_type: str) -> List[GrantOpportunity]:
        """Generate realistic mock grant data for testing"""
        
        # Determine relevant grants based on keywords
        keyword_lower = keywords.lower()
        
        mock_data = [
            {
                'id': 'ED-GRANTS-2025-001',
                'title': 'Youth Education and Development Program',
                'funder': 'Department of Education',
                'source': 'grants.gov',
                'deadline': (datetime.now() + timedelta(days=45)).isoformat(),
                'amount_min': 50000,
                'amount_max': 500000,
                'eligibility': ['nonprofit', 'tribal', 'local_government'],
                'topic_areas': ['education', 'youth'],
                'description': 'Supports innovative education programs for underserved youth populations.',
                'url': 'https://grants.gov/view-opportunity.html?oppId=12345'
            },
            {
                'id': 'HHS-HEALTH-2025-002',
                'title': 'Community Health Services Expansion',
                'funder': 'Department of Health and Human Services',
                'source': 'grants.gov',
                'deadline': (datetime.now() + timedelta(days=60)).isoformat(),
                'amount_min': 100000,
                'amount_max': 1000000,
                'eligibility': ['nonprofit', 'university', 'local_government'],
                'topic_areas': ['health', 'community'],
                'description': 'Funds expansion of healthcare services in underserved communities.',
                'url': 'https://grants.gov/view-opportunity.html?oppId=12346'
            },
            {
                'id': 'EPA-ENV-2025-003',
                'title': 'Environmental Conservation and Education',
                'funder': 'Environmental Protection Agency',
                'source': 'grants.gov',
                'deadline': (datetime.now() + timedelta(days=30)).isoformat(),
                'amount_min': 25000,
                'amount_max': 250000,
                'eligibility': ['nonprofit', 'tribal'],
                'topic_areas': ['environment', 'education'],
                'description': 'Supports environmental education and conservation initiatives.',
                'url': 'https://grants.gov/view-opportunity.html?oppId=12347'
            },
            {
                'id': 'NEA-ARTS-2025-004',
                'title': 'Arts Education for Youth',
                'funder': 'National Endowment for the Arts',
                'source': 'grants.gov',
                'deadline': (datetime.now() + timedelta(days=90)).isoformat(),
                'amount_min': 10000,
                'amount_max': 100000,
                'eligibility': ['nonprofit'],
                'topic_areas': ['arts', 'education', 'youth'],
                'description': 'Provides funding for arts education programs serving young people.',
                'url': 'https://grants.gov/view-opportunity.html?oppId=12348'
            },
            {
                'id': 'USDA-AG-2025-005',
                'title': 'Rural Community Development Initiative',
                'funder': 'Department of Agriculture',
                'source': 'grants.gov',
                'deadline': (datetime.now() + timedelta(days=75)).isoformat(),
                'amount_min': 75000,
                'amount_max': 500000,
                'eligibility': ['nonprofit', 'local_government', 'tribal'],
                'topic_areas': ['agriculture', 'rural', 'community'],
                'description': 'Supports development projects in rural communities.',
                'url': 'https://grants.gov/view-opportunity.html?oppId=12349'
            }
        ]
        
        # Convert to GrantOpportunity objects
        opportunities = [
            GrantOpportunity(
                id=g['id'],
                title=g['title'],
                funder=g['funder'],
                source=g['source'],
                deadline=g['deadline'],
                amount_min=g['amount_min'],
                amount_max=g['amount_max'],
                eligibility=g['eligibility'],
                topic_areas=g['topic_areas'],
                description=g['description'],
                url=g['url'],
                relevance_score=0.0  # Will be calculated later
            )
            for g in mock_data
        ]
        
        return opportunities
    
    def _filter_opportunities(
        self,
        opportunities: List[GrantOpportunity],
        min_amount: Optional[int],
        deadline_within_days: Optional[int],
        topic_areas: Optional[List[str]]
    ) -> List[GrantOpportunity]:
        """Filter opportunities based on criteria"""
        
        filtered = opportunities
        
        # Filter by minimum amount
        if min_amount:
            filtered = [
                opp for opp in filtered
                if opp.amount_max and opp.amount_max >= min_amount
            ]
        
        # Filter by deadline
        if deadline_within_days:
            cutoff_date = datetime.now() + timedelta(days=deadline_within_days)
            filtered = [
                opp for opp in filtered
                if datetime.fromisoformat(opp.deadline.replace('Z', '+00:00')) <= cutoff_date
            ]
        
        # Filter by topic areas
        if topic_areas:
            filtered = [
                opp for opp in filtered
                if any(topic in opp.topic_areas for topic in topic_areas)
            ]
        
        return filtered
    
    def _rank_opportunities(
        self,
        opportunities: List[GrantOpportunity],
        keywords: str,
        org_type: str,
        topic_areas: Optional[List[str]]
    ) -> List[GrantOpportunity]:
        """Calculate relevance scores for opportunities"""
        
        keyword_terms = keywords.lower().split() if keywords else []
        target_topics = set(topic_areas) if topic_areas else set()
        
        for opp in opportunities:
            score = 0.0
            
            # Keyword matching in title and description
            text = f"{opp.title} {opp.description}".lower()
            for term in keyword_terms:
                if term in text:
                    score += 0.2
            
            # Topic area matching
            if target_topics:
                matching_topics = target_topics.intersection(set(opp.topic_areas))
                score += len(matching_topics) * 0.3
            
            # Eligibility matching
            if org_type in opp.eligibility:
                score += 0.3
            
            # Deadline urgency (sooner = slightly higher score)
            try:
                deadline = datetime.fromisoformat(opp.deadline.replace('Z', '+00:00'))
                days_until = (deadline - datetime.now()).days
                if 30 <= days_until <= 90:
                    score += 0.1  # Sweet spot
            except:
                pass
            
            # Normalize score to 0-1
            opp.relevance_score = min(score, 1.0)
        
        return opportunities


# Tool metadata for Agent Zero registration
tool_info = {
    'name': 'grant_discovery',
    'description': 'Search for grant opportunities from Grants.gov and other sources',
    'parameters': {
        'keywords': 'Search keywords',
        'org_type': 'Organization type (nonprofit, tribal, university, local_government)',
        'topic_areas': 'List of topic areas',
        'max_results': 'Maximum results to return (default 10)',
        'min_amount': 'Minimum grant amount',
        'deadline_within_days': 'Only show grants due within X days'
    },
    'example': 'grant_discovery(keywords="youth education", org_type="nonprofit", topic_areas=["education", "youth"])'
}
