"""
Compliance Checker Tool for Agent Zero

Validates proposals against funder requirements and formatting rules.
"""

from typing import Dict, List, Any, Optional
import re


class ComplianceChecker:
    """
    Compliance Checker Tool for Agent Zero
    
    Validates grant proposals against funder-specific requirements.
    """
    
    def __init__(self, agent=None, **kwargs):
        self.agent = agent
        self.name = "compliance_checker"
        self.args = kwargs
        
    async def execute(
        self,
        proposal_sections: Dict[str, str],
        grant_requirements: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Check proposal compliance
        
        Args:
            proposal_sections: Dict of section_name: content
            grant_requirements: Dict with funder rules
            
        Returns:
            Dict with:
                - is_compliant: bool
                - issues: List[str] (blocking problems)
                - warnings: List[str] (recommendations)
                - suggestions: List[str]
                - section_compliance: Dict (per-section details)
        """
        
        try:
            issues = []
            warnings = []
            suggestions = []
            section_compliance = {}
            
            # Check each section
            for section, content in proposal_sections.items():
                section_result = self._check_section(
                    section=section,
                    content=content,
                    requirements=grant_requirements.get(section, {})
                )
                section_compliance[section] = section_result
                
                issues.extend(section_result.get('issues', []))
                warnings.extend(section_result.get('warnings', []))
            
            # Check required sections
            required_sections = grant_requirements.get('required_sections', [])
            for req_section in required_sections:
                if req_section not in proposal_sections:
                    issues.append(f"Missing required section: {req_section}")
            
            # Overall compliance
            is_compliant = len(issues) == 0
            
            # Generate suggestions
            if warnings:
                suggestions.append("Address warnings to strengthen proposal")
            if is_compliant:
                suggestions.append("Proposal meets all mandatory requirements")
            
            return {
                'is_compliant': is_compliant,
                'issues': issues,
                'warnings': warnings,
                'suggestions': suggestions,
                'section_compliance': section_compliance,
                'message': f"Compliance check complete. {'PASS' if is_compliant else 'FAIL'}"
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'message': f"Error checking compliance: {str(e)}"
            }
    
    def _check_section(
        self,
        section: str,
        content: str,
        requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check compliance for a single section"""
        
        issues = []
        warnings = []
        
        # Word count check
        word_count = len(content.split())
        max_words = requirements.get('max_words')
        min_words = requirements.get('min_words')
        
        if max_words and word_count > max_words:
            issues.append(f"{section}: Exceeds maximum ({word_count}/{max_words} words)")
        elif min_words and word_count < min_words:
            warnings.append(f"{section}: Below recommended minimum ({word_count}/{min_words} words)")
        
        # Character count check
        char_count = len(content)
        max_chars = requirements.get('max_characters')
        
        if max_chars and char_count > max_chars:
            issues.append(f"{section}: Exceeds character limit ({char_count}/{max_chars})")
        
        # Required elements check
        required_elements = requirements.get('required_elements', [])
        for element in required_elements:
            if element.lower() not in content.lower():
                warnings.append(f"{section}: May be missing required element '{element}'")
        
        # Formatting checks
        if requirements.get('no_urls') and re.search(r'http[s]?://', content):
            warnings.append(f"{section}: Contains URLs (may not be allowed)")
        
        if requirements.get('no_special_chars') and re.search(r'[^\w\s.,;:!?\-\']', content):
            warnings.append(f"{section}: Contains special characters")
        
        return {
            'section': section,
            'word_count': word_count,
            'character_count': char_count,
            'issues': issues,
            'warnings': warnings,
            'compliant': len(issues) == 0
        }


# Tool metadata
tool_info = {
    'name': 'compliance_checker',
    'description': 'Validate proposal against funder requirements',
    'example': 'compliance_checker(proposal_sections={...}, grant_requirements={...})'
}
