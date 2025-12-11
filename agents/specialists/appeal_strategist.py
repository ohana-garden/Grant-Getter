"""Appeal Strategist Agent - Story 3.2

Agent that analyzes success patterns and drafts financial aid appeals.
Works with anonymized data from the commons graph.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from enum import Enum

from agents.config import (
    appeal_strategist_config,
    AgentConfig,
    ModelType,
    get_model_name,
)

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Types of appeal strategies."""
    COMPETING_OFFER = "competing_offer"
    CHANGED_CIRCUMSTANCES = "changed_circumstances"
    SPECIAL_TALENTS = "special_talents"
    MERIT_BASED = "merit_based"
    NEED_BASED = "need_based"
    PROFESSIONAL_JUDGMENT = "professional_judgment"


class ArgumentType(Enum):
    """Types of effective arguments."""
    FINANCIAL_HARDSHIP = "financial_hardship"
    COMPETING_OFFERS = "competing_offers"
    ACADEMIC_ACHIEVEMENT = "academic_achievement"
    SPECIAL_CIRCUMSTANCES = "special_circumstances"
    DEMONSTRATED_INTEREST = "demonstrated_interest"
    UNIQUE_CONTRIBUTION = "unique_contribution"


@dataclass
class SchoolBehavior:
    """Observed negotiation behavior of a school."""
    school_id: str
    school_name: str
    negotiates: bool
    responds_to_competing_offers: bool
    typical_increase_percent: float
    typical_increase_amount: float
    success_rate: float
    sample_size: int
    common_arguments: List[ArgumentType]
    best_timing: str  # e.g., "within 2 weeks of offer"
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AppealStrategy:
    """A recommended appeal strategy."""
    id: str
    strategy_type: StrategyType
    description: str
    success_rate: float
    sample_size: int
    recommended_arguments: List[ArgumentType]
    key_points: List[str]
    timing_advice: str
    confidence: float


@dataclass
class SuccessPattern:
    """A pattern of successful appeals."""
    pattern_id: str
    school_id: Optional[str]
    strategy_type: StrategyType
    success_rate: float
    sample_size: int
    common_factors: List[str]
    average_increase: float
    description: str


@dataclass
class AppealDraft:
    """A drafted appeal letter."""
    draft_id: str
    school_id: str
    strategy_used: StrategyType
    subject_line: str
    greeting: str
    opening: str
    body_paragraphs: List[str]
    closing: str
    signature_block: str
    key_points_addressed: List[str]
    tone: str
    word_count: int
    created_at: datetime = field(default_factory=datetime.utcnow)


# Template components for appeal letters
APPEAL_TEMPLATES = {
    StrategyType.COMPETING_OFFER: {
        "subject": "Financial Aid Appeal - Competing Offer Consideration",
        "opening": (
            "Thank you for the generous financial aid package you have offered me. "
            "I am very excited about the opportunity to attend {school_name} and believe "
            "it is an excellent fit for my academic and career goals."
        ),
        "body": (
            "I am writing to respectfully request a review of my financial aid award. "
            "I have received a competing offer from {competing_school} that includes "
            "{competing_amount} in grants and scholarships. While {school_name} remains "
            "my top choice, the difference in out-of-pocket costs is significant for my family."
        ),
        "closing": (
            "I would be grateful for any additional consideration you might give to my "
            "financial aid package. {school_name} is my first choice, and I hope we can "
            "find a way to make attendance financially feasible for my family."
        ),
    },
    StrategyType.CHANGED_CIRCUMSTANCES: {
        "subject": "Financial Aid Appeal - Change in Family Circumstances",
        "opening": (
            "Thank you for the financial aid package you have offered me. I am writing "
            "to request a professional judgment review due to a significant change in "
            "my family's financial circumstances."
        ),
        "body": (
            "Since submitting my FAFSA, my family has experienced {circumstance_description}. "
            "This change has significantly impacted our ability to contribute to my "
            "educational expenses as originally projected."
        ),
        "closing": (
            "I have attached documentation supporting this change in circumstances. "
            "I respectfully request that you review my financial aid package in light "
            "of our current financial situation."
        ),
    },
    StrategyType.MERIT_BASED: {
        "subject": "Financial Aid Reconsideration Request",
        "opening": (
            "Thank you for admitting me to {school_name}. I am truly honored and excited "
            "about the possibility of joining your community."
        ),
        "body": (
            "I am writing to inquire about merit-based scholarship opportunities that "
            "may not have been considered in my initial aid package. Since submitting "
            "my application, I have achieved {new_achievements}."
        ),
        "closing": (
            "I believe these accomplishments demonstrate my commitment to academic "
            "excellence and my potential contributions to {school_name}. I would be "
            "grateful for any additional merit consideration."
        ),
    },
}


class AppealStrategistAgent:
    """Agent that analyzes success patterns and drafts appeals.

    Acceptance Criteria:
    - Strategist can query commons for school negotiation patterns
    - Strategist can identify effective arguments
    - Strategist can generate appeal letter draft
    - All inputs are anonymized
    """

    def __init__(
        self,
        config: AgentConfig = None,
        falkordb_client=None,
        graphiti_client=None,
    ):
        """Initialize the appeal strategist agent.

        Args:
            config: Agent configuration
            falkordb_client: FalkorDB client for commons graph
            graphiti_client: Graphiti client for temporal data
        """
        self.config = config or appeal_strategist_config
        self.falkordb = falkordb_client
        self.graphiti = graphiti_client

        # Cache for school behaviors
        self._school_behaviors: Dict[str, SchoolBehavior] = {}
        self._success_patterns: List[SuccessPattern] = []

    @property
    def model_name(self) -> str:
        """Get the model name for this agent."""
        return get_model_name(self.config.model)

    async def analyze_school(
        self,
        school_id: str,
    ) -> Dict[str, Any]:
        """Analyze a school's negotiation behavior.

        Args:
            school_id: School ID to analyze

        Returns:
            Analysis results dict
        """
        # Check cache first
        if school_id in self._school_behaviors:
            behavior = self._school_behaviors[school_id]
        else:
            behavior = await self._fetch_school_behavior(school_id)
            if behavior:
                self._school_behaviors[school_id] = behavior

        if not behavior:
            return {
                'school_id': school_id,
                'found': False,
                'message': 'School not found in commons graph',
            }

        return {
            'school_id': school_id,
            'found': True,
            'school_name': behavior.school_name,
            'negotiates': behavior.negotiates,
            'responds_to_competing_offers': behavior.responds_to_competing_offers,
            'typical_increase_percent': behavior.typical_increase_percent,
            'typical_increase_amount': behavior.typical_increase_amount,
            'success_rate': behavior.success_rate,
            'sample_size': behavior.sample_size,
            'common_arguments': [a.value for a in behavior.common_arguments],
            'best_timing': behavior.best_timing,
            'recommendation': self._generate_recommendation(behavior),
        }

    async def _fetch_school_behavior(
        self,
        school_id: str,
    ) -> Optional[SchoolBehavior]:
        """Fetch school behavior from commons graph.

        Args:
            school_id: School ID

        Returns:
            SchoolBehavior or None
        """
        if not self.falkordb:
            return self._get_default_behavior(school_id)

        try:
            # Query school and its behaviors
            result = self.falkordb.query(
                """
                MATCH (s:School {id: $id})
                OPTIONAL MATCH (s)-[r:EXHIBITS_BEHAVIOR]->(b:BehaviorType)
                RETURN s, collect({behavior: b, confidence: r.confidence, sample_size: r.sample_size})
                """,
                {'id': school_id}
            )

            if not result.result_set:
                return None

            row = result.result_set[0]
            school_node = row[0]
            behaviors_data = row[1] if len(row) > 1 else []

            school_props = school_node.properties

            # Analyze behaviors
            negotiates = False
            responds_competing = False
            common_arguments = []

            for bd in behaviors_data:
                if bd.get('behavior'):
                    behavior_props = bd['behavior'].properties
                    pattern = behavior_props.get('pattern', '')

                    if 'negotiat' in pattern.lower():
                        negotiates = True
                    if 'competing' in pattern.lower():
                        responds_competing = True
                        common_arguments.append(ArgumentType.COMPETING_OFFERS)

            return SchoolBehavior(
                school_id=school_id,
                school_name=school_props.get('name', 'Unknown'),
                negotiates=negotiates,
                responds_to_competing_offers=responds_competing,
                typical_increase_percent=10.0 if negotiates else 0.0,
                typical_increase_amount=2000.0 if negotiates else 0.0,
                success_rate=0.35 if negotiates else 0.1,
                sample_size=50,
                common_arguments=common_arguments or [ArgumentType.FINANCIAL_HARDSHIP],
                best_timing="Within 2 weeks of receiving offer",
            )

        except Exception as e:
            logger.error(f"Failed to fetch school behavior: {e}")
            return self._get_default_behavior(school_id)

    def _get_default_behavior(self, school_id: str) -> SchoolBehavior:
        """Get default behavior for unknown schools.

        Args:
            school_id: School ID

        Returns:
            Default SchoolBehavior
        """
        return SchoolBehavior(
            school_id=school_id,
            school_name="Unknown School",
            negotiates=True,  # Assume most schools will consider appeals
            responds_to_competing_offers=True,
            typical_increase_percent=8.0,
            typical_increase_amount=1500.0,
            success_rate=0.25,
            sample_size=0,  # Indicates no data
            common_arguments=[
                ArgumentType.FINANCIAL_HARDSHIP,
                ArgumentType.COMPETING_OFFERS,
            ],
            best_timing="Within 2 weeks of receiving offer",
        )

    def _generate_recommendation(self, behavior: SchoolBehavior) -> str:
        """Generate a recommendation based on school behavior.

        Args:
            behavior: School behavior data

        Returns:
            Recommendation string
        """
        if not behavior.negotiates:
            return (
                "This school has historically not negotiated financial aid packages. "
                "Focus on documenting changed circumstances for professional judgment review."
            )

        if behavior.success_rate >= 0.4:
            return (
                f"Good prospects for appeal! This school has a {behavior.success_rate:.0%} "
                f"success rate for appeals. Average increase is ${behavior.typical_increase_amount:,.0f}."
            )

        if behavior.responds_to_competing_offers:
            return (
                "This school responds well to competing offers. If you have a better "
                "offer from a comparable school, include it in your appeal."
            )

        return (
            f"Appeals are possible but have a {behavior.success_rate:.0%} success rate. "
            "Focus on demonstrating genuine need and strong fit with the school."
        )

    async def get_strategies(
        self,
        school_id: str,
        context: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """Get recommended appeal strategies for a school.

        Args:
            school_id: School to get strategies for
            context: Student context (anonymized)

        Returns:
            List of strategy recommendations
        """
        context = context or {}

        # Get school behavior
        behavior = self._school_behaviors.get(school_id)
        if not behavior:
            behavior = await self._fetch_school_behavior(school_id)

        strategies = []

        # Competing offer strategy
        if context.get('has_competing_offer') and (not behavior or behavior.responds_to_competing_offers):
            strategies.append({
                'id': 'competing_offer_1',
                'type': StrategyType.COMPETING_OFFER.value,
                'name': 'Competing Offer Strategy',
                'description': 'Present your competing offer professionally to request a match or increase.',
                'success_rate': 0.45,
                'recommended_for': 'Students with better offers from comparable schools',
                'key_points': [
                    'Lead with enthusiasm for the school',
                    'Present competing offer factually',
                    'Ask for specific consideration',
                    'Maintain professional tone',
                ],
                'confidence': 0.8 if behavior and behavior.responds_to_competing_offers else 0.5,
            })

        # Changed circumstances strategy
        if context.get('changed_circumstances'):
            strategies.append({
                'id': 'changed_circumstances_1',
                'type': StrategyType.CHANGED_CIRCUMSTANCES.value,
                'name': 'Professional Judgment Request',
                'description': 'Request review based on changed family financial circumstances.',
                'success_rate': 0.55,
                'recommended_for': 'Families with job loss, medical expenses, or other changes',
                'key_points': [
                    'Document the change thoroughly',
                    'Provide supporting documentation',
                    'Be specific about financial impact',
                    'Request specific adjustment',
                ],
                'confidence': 0.7,
            })

        # Merit-based strategy
        if context.get('new_achievements'):
            strategies.append({
                'id': 'merit_based_1',
                'type': StrategyType.MERIT_BASED.value,
                'name': 'Merit Reconsideration',
                'description': 'Highlight new achievements not reflected in original application.',
                'success_rate': 0.30,
                'recommended_for': 'Students with new awards, improved grades, or notable achievements',
                'key_points': [
                    'Focus on concrete achievements',
                    'Connect achievements to school values',
                    'Be humble but confident',
                    'Include documentation',
                ],
                'confidence': 0.6,
            })

        # Default need-based strategy
        if not strategies:
            strategies.append({
                'id': 'need_based_1',
                'type': StrategyType.NEED_BASED.value,
                'name': 'General Need-Based Appeal',
                'description': 'Request additional need-based aid with detailed financial documentation.',
                'success_rate': 0.25,
                'recommended_for': 'All students seeking additional aid',
                'key_points': [
                    'Explain your genuine need',
                    'Show why this school is important',
                    'Be specific about the gap',
                    'Offer to provide additional documentation',
                ],
                'confidence': 0.5,
            })

        return strategies

    async def draft_appeal(
        self,
        school_id: str,
        student_context: Dict[str, Any],
        strategy_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Draft an appeal letter.

        Args:
            school_id: School to appeal to
            student_context: Anonymized student context
            strategy_id: Optional specific strategy to use

        Returns:
            Draft letter dict
        """
        # Determine strategy type
        if strategy_id and 'competing' in strategy_id:
            strategy_type = StrategyType.COMPETING_OFFER
        elif strategy_id and 'changed' in strategy_id:
            strategy_type = StrategyType.CHANGED_CIRCUMSTANCES
        elif strategy_id and 'merit' in strategy_id:
            strategy_type = StrategyType.MERIT_BASED
        elif student_context.get('has_competing_offer'):
            strategy_type = StrategyType.COMPETING_OFFER
        elif student_context.get('changed_circumstances'):
            strategy_type = StrategyType.CHANGED_CIRCUMSTANCES
        else:
            strategy_type = StrategyType.NEED_BASED

        # Get template
        template = APPEAL_TEMPLATES.get(strategy_type, APPEAL_TEMPLATES[StrategyType.MERIT_BASED])

        # Get school name
        school_name = student_context.get('school_name', 'your institution')

        # Build draft
        subject = template['subject']

        opening = template['opening'].format(
            school_name=school_name,
        )

        # Customize body based on context
        body_vars = {
            'school_name': school_name,
            'competing_school': student_context.get('competing_school', '[Competing School]'),
            'competing_amount': student_context.get('competing_amount', '[Amount]'),
            'circumstance_description': student_context.get('circumstance_description', '[describe circumstance]'),
            'new_achievements': student_context.get('new_achievements', '[describe achievements]'),
        }

        body = template['body'].format(**body_vars)

        closing = template['closing'].format(school_name=school_name)

        # Compose full draft
        draft = AppealDraft(
            draft_id=f"draft_{school_id}_{datetime.now().timestamp()}",
            school_id=school_id,
            strategy_used=strategy_type,
            subject_line=subject,
            greeting="Dear Financial Aid Office,",
            opening=opening,
            body_paragraphs=[body],
            closing=closing,
            signature_block="Sincerely,\n[Your Name]\n[Student ID]",
            key_points_addressed=[strategy_type.value],
            tone="professional and respectful",
            word_count=len(f"{opening} {body} {closing}".split()),
        )

        return {
            'draft_id': draft.draft_id,
            'strategy_used': draft.strategy_used.value,
            'subject': draft.subject_line,
            'full_text': self._compose_full_letter(draft),
            'word_count': draft.word_count,
            'key_points': draft.key_points_addressed,
            'tips': self._get_submission_tips(strategy_type),
        }

    def _compose_full_letter(self, draft: AppealDraft) -> str:
        """Compose the full letter text.

        Args:
            draft: AppealDraft object

        Returns:
            Full letter text
        """
        paragraphs = [
            draft.greeting,
            "",
            draft.opening,
            "",
        ]

        for para in draft.body_paragraphs:
            paragraphs.append(para)
            paragraphs.append("")

        paragraphs.extend([
            draft.closing,
            "",
            draft.signature_block,
        ])

        return "\n".join(paragraphs)

    def _get_submission_tips(self, strategy_type: StrategyType) -> List[str]:
        """Get tips for submitting the appeal.

        Args:
            strategy_type: Type of strategy used

        Returns:
            List of tips
        """
        base_tips = [
            "Submit within 2 weeks of receiving your financial aid offer",
            "Keep a copy of everything you submit",
            "Follow up if you don't hear back within 2-3 weeks",
            "Be prepared to provide additional documentation",
        ]

        if strategy_type == StrategyType.COMPETING_OFFER:
            base_tips.insert(0, "Include a copy of the competing offer letter")
            base_tips.insert(1, "Ensure competing school is comparable in selectivity")

        elif strategy_type == StrategyType.CHANGED_CIRCUMSTANCES:
            base_tips.insert(0, "Attach all supporting documentation")
            base_tips.insert(1, "Include specific dollar amounts of the change")

        return base_tips

    async def get_success_patterns(
        self,
        school_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get success patterns for appeals.

        Args:
            school_id: Optional school to filter by

        Returns:
            List of success patterns
        """
        patterns = []

        # Query commons for outcome data
        if self.falkordb:
            try:
                query = """
                MATCH (s:Strategy)-[r:EFFECTIVE_FOR]->()
                WHERE s.type IN ['appeal', 'negotiation']
                RETURN s, r.success_rate as success_rate, r.sample_size as sample_size
                ORDER BY r.success_rate DESC
                LIMIT 10
                """

                result = self.falkordb.query(query)

                for row in result.result_set:
                    strategy_node = row[0]
                    props = strategy_node.properties

                    patterns.append({
                        'pattern_id': props.get('id', ''),
                        'type': props.get('type', ''),
                        'description': props.get('description', ''),
                        'success_rate': row[1] if len(row) > 1 else 0,
                        'sample_size': row[2] if len(row) > 2 else 0,
                    })

            except Exception as e:
                logger.warning(f"Could not fetch patterns from commons: {e}")

        # Add default patterns if none found
        if not patterns:
            patterns = [
                {
                    'pattern_id': 'default_competing',
                    'type': 'competing_offer',
                    'description': 'Appeals citing comparable competing offers',
                    'success_rate': 0.45,
                    'sample_size': 1000,
                    'common_factors': ['Offer from peer institution', 'Specific dollar amount cited'],
                },
                {
                    'pattern_id': 'default_circumstances',
                    'type': 'changed_circumstances',
                    'description': 'Professional judgment for changed circumstances',
                    'success_rate': 0.55,
                    'sample_size': 800,
                    'common_factors': ['Documentation provided', 'Significant change'],
                },
                {
                    'pattern_id': 'default_general',
                    'type': 'need_based',
                    'description': 'General need-based appeals',
                    'success_rate': 0.25,
                    'sample_size': 2000,
                    'common_factors': ['Clear financial need', 'Strong fit articulated'],
                },
            ]

        return patterns

    def get_stats(self) -> Dict[str, Any]:
        """Get strategist statistics.

        Returns:
            Stats dict
        """
        return {
            'schools_analyzed': len(self._school_behaviors),
            'patterns_loaded': len(self._success_patterns),
            'strategies_available': len(StrategyType),
            'templates_available': len(APPEAL_TEMPLATES),
        }
