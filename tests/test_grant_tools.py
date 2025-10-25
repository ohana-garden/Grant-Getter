"""
Test suite for Grant Agent tools

Run with: pytest tests/test_grant_tools.py -v
"""

import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python.tools.grant_discovery import GrantDiscovery
from python.tools.proposal_writer import ProposalWriter
from python.tools.compliance_checker import ComplianceChecker
from python.tools.deadline_tracker import DeadlineTracker
from datetime import datetime, timedelta


class TestGrantDiscovery:
    """Test grant discovery tool"""
    
    @pytest.mark.asyncio
    async def test_basic_search(self):
        """Test basic grant search functionality"""
        tool = GrantDiscovery()
        
        result = await tool.execute(
            keywords="youth education",
            org_type="nonprofit",
            topic_areas=["education", "youth"],
            max_results=5
        )
        
        assert 'opportunities' in result
        assert 'total_found' in result
        assert len(result['opportunities']) <= 5
        assert result['total_found'] >= 0
    
    @pytest.mark.asyncio
    async def test_filtered_search(self):
        """Test search with filters"""
        tool = GrantDiscovery()
        
        result = await tool.execute(
            keywords="education",
            org_type="nonprofit",
            min_amount=100000,
            deadline_within_days=60,
            max_results=10
        )
        
        # Check that filters were applied
        for opp in result['opportunities']:
            if opp['amount_max']:
                assert opp['amount_max'] >= 100000
            
            # Check deadline is within range
            deadline = datetime.fromisoformat(opp['deadline'].replace('Z', '+00:00'))
            days_until = (deadline - datetime.now()).days
            assert days_until <= 60
    
    @pytest.mark.asyncio
    async def test_relevance_scoring(self):
        """Test that opportunities have relevance scores"""
        tool = GrantDiscovery()
        
        result = await tool.execute(
            keywords="youth education",
            org_type="nonprofit",
            topic_areas=["education"],
            max_results=5
        )
        
        for opp in result['opportunities']:
            assert 'relevance_score' in opp
            assert 0.0 <= opp['relevance_score'] <= 1.0


class TestProposalWriter:
    """Test proposal writer tool"""
    
    @pytest.mark.asyncio
    async def test_generate_section(self):
        """Test generating a proposal section"""
        tool = ProposalWriter()
        
        org_profile = {
            'name': 'Test Nonprofit',
            'mission': 'Serve the community',
            'org_type': 'nonprofit',
            'annual_budget': 250000,
            'programs': ['tutoring', 'mentoring']
        }
        
        result = await tool.execute(
            grant_id="TEST-001",
            section="abstract",
            org_profile=org_profile,
            action="generate"
        )
        
        assert 'section_content' in result
        assert 'word_count' in result
        assert 'compliance_status' in result
        assert result['word_count'] > 0
        assert len(result['section_content']) > 0
    
    @pytest.mark.asyncio
    async def test_all_sections(self):
        """Test generating all proposal sections"""
        tool = ProposalWriter()
        
        org_profile = {
            'name': 'Test Nonprofit',
            'mission': 'Serve the community',
            'org_type': 'nonprofit'
        }
        
        sections = ['abstract', 'need', 'goals', 'methods', 'budget', 'evaluation', 'capacity']
        
        for section in sections:
            result = await tool.execute(
                grant_id="TEST-001",
                section=section,
                org_profile=org_profile,
                action="generate"
            )
            
            assert 'section_content' in result, f"Failed to generate {section}"
            assert result['word_count'] > 0, f"Empty content for {section}"
    
    @pytest.mark.asyncio
    async def test_word_count_compliance(self):
        """Test that word count requirements are checked"""
        tool = ProposalWriter()
        
        org_profile = {'name': 'Test Org', 'mission': 'Test mission'}
        
        result = await tool.execute(
            grant_id="TEST-001",
            section="abstract",
            org_profile=org_profile,
            action="generate",
            requirements={'max_words': 250}
        )
        
        assert 'compliance_status' in result
        # Check if word count is tracked
        assert result['word_count'] is not None


class TestComplianceChecker:
    """Test compliance checker tool"""
    
    @pytest.mark.asyncio
    async def test_basic_compliance_check(self):
        """Test basic compliance validation"""
        tool = ComplianceChecker()
        
        proposal = {
            'abstract': 'This is a test abstract that describes the project briefly.',
            'need': 'The community needs this program because...'
        }
        
        requirements = {
            'abstract': {'max_words': 100},
            'need': {'max_words': 1000},
            'required_sections': ['abstract', 'need']
        }
        
        result = await tool.execute(
            proposal_sections=proposal,
            grant_requirements=requirements
        )
        
        assert 'is_compliant' in result
        assert 'issues' in result
        assert 'warnings' in result
        assert 'section_compliance' in result
    
    @pytest.mark.asyncio
    async def test_missing_section_detection(self):
        """Test detection of missing required sections"""
        tool = ComplianceChecker()
        
        proposal = {'abstract': 'Test content'}
        
        requirements = {
            'required_sections': ['abstract', 'need', 'goals']
        }
        
        result = await tool.execute(
            proposal_sections=proposal,
            grant_requirements=requirements
        )
        
        assert result['is_compliant'] == False
        assert len(result['issues']) >= 2  # Missing 'need' and 'goals'
    
    @pytest.mark.asyncio
    async def test_word_limit_violation(self):
        """Test detection of word limit violations"""
        tool = ComplianceChecker()
        
        # Create content that exceeds limit
        long_content = ' '.join(['word'] * 150)
        
        proposal = {'abstract': long_content}
        
        requirements = {
            'abstract': {'max_words': 100}
        }
        
        result = await tool.execute(
            proposal_sections=proposal,
            grant_requirements=requirements
        )
        
        # Should flag word count issue
        assert result['is_compliant'] == False
        assert any('Exceeds maximum' in issue for issue in result['issues'])


class TestDeadlineTracker:
    """Test deadline tracker tool"""
    
    @pytest.mark.asyncio
    async def test_add_deadline(self):
        """Test adding a deadline"""
        tool = DeadlineTracker()
        
        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        
        result = await tool.execute(
            action="add",
            grant_id="TEST-001",
            deadline=future_date,
            notification_days_before=7
        )
        
        assert result['status'] == 'added'
        assert result['grant_id'] == 'TEST-001'
        assert 'days_until_deadline' in result
    
    @pytest.mark.asyncio
    async def test_list_deadlines(self):
        """Test listing all deadlines"""
        tool = DeadlineTracker()
        
        # Add a deadline first
        future_date = (datetime.now() + timedelta(days=45)).isoformat()
        await tool.execute(
            action="add",
            grant_id="TEST-002",
            deadline=future_date
        )
        
        # List deadlines
        result = await tool.execute(action="list")
        
        assert 'deadlines' in result
        assert 'total_count' in result
        assert result['total_count'] >= 1
    
    @pytest.mark.asyncio
    async def test_upcoming_deadlines(self):
        """Test getting upcoming deadlines"""
        tool = DeadlineTracker()
        
        # Add deadlines at different times
        soon = (datetime.now() + timedelta(days=10)).isoformat()
        later = (datetime.now() + timedelta(days=100)).isoformat()
        
        await tool.execute(action="add", grant_id="SOON-001", deadline=soon)
        await tool.execute(action="add", grant_id="LATER-001", deadline=later)
        
        # Get upcoming within 30 days
        result = await tool.execute(action="upcoming", days=30)
        
        assert 'upcoming_deadlines' in result
        # Should include SOON-001 but not LATER-001
        grant_ids = [d['grant_id'] for d in result['upcoming_deadlines']]
        assert 'SOON-001' in grant_ids
        assert 'LATER-001' not in grant_ids
    
    @pytest.mark.asyncio
    async def test_remove_deadline(self):
        """Test removing a deadline"""
        tool = DeadlineTracker()
        
        # Add then remove
        future_date = (datetime.now() + timedelta(days=30)).isoformat()
        await tool.execute(action="add", grant_id="REMOVE-TEST", deadline=future_date)
        
        result = await tool.execute(action="remove", grant_id="REMOVE-TEST")
        
        assert result['status'] == 'removed'


def test_tool_metadata():
    """Test that all tools have proper metadata"""
    from python.tools.grant_discovery import tool_info as discovery_info
    from python.tools.proposal_writer import tool_info as writer_info
    from python.tools.compliance_checker import tool_info as compliance_info
    from python.tools.deadline_tracker import tool_info as tracker_info
    
    tools = [discovery_info, writer_info, compliance_info, tracker_info]
    
    for tool in tools:
        assert 'name' in tool
        assert 'description' in tool
        assert len(tool['name']) > 0
        assert len(tool['description']) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
