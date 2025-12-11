"""Document Analyst Agent - Story 3.4

On-device agent that processes sensitive documents locally.
Parses award letters, transcripts, and validates completeness.
CRITICAL: No document content ever leaves the device.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

from agents.config import (
    document_analyst_config,
    AgentConfig,
    ModelType,
    get_model_name,
)

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Types of documents we can analyze."""
    AWARD_LETTER = "award_letter"
    TRANSCRIPT = "transcript"
    SAR = "sar"  # Student Aid Report
    TAX_FORM = "tax_form"
    FAFSA_CONFIRMATION = "fafsa_confirmation"
    SCHOLARSHIP_OFFER = "scholarship_offer"
    APPEAL_LETTER = "appeal_letter"
    OTHER = "other"


class AnalysisStatus(Enum):
    """Status of document analysis."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class CompletionStatus(Enum):
    """Document completeness status."""
    COMPLETE = "complete"
    MISSING_FIELDS = "missing_fields"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"


@dataclass
class ExtractedField:
    """An extracted field from a document."""
    name: str
    value: Any
    confidence: float  # 0.0 to 1.0
    location: Optional[str] = None  # e.g., "Page 1, Line 5"
    raw_text: Optional[str] = None


@dataclass
class AwardLetterData:
    """Extracted data from a financial aid award letter."""
    school_name: Optional[str] = None
    academic_year: Optional[str] = None
    student_name: Optional[str] = None  # Should be redacted before transmission

    # Cost of Attendance
    total_cost: Optional[float] = None
    tuition: Optional[float] = None
    fees: Optional[float] = None
    room_board: Optional[float] = None
    books_supplies: Optional[float] = None
    personal_expenses: Optional[float] = None
    transportation: Optional[float] = None

    # Aid Components
    total_aid: Optional[float] = None
    grants: Dict[str, float] = field(default_factory=dict)
    scholarships: Dict[str, float] = field(default_factory=dict)
    loans: Dict[str, float] = field(default_factory=dict)
    work_study: Optional[float] = None

    # Calculated
    net_cost: Optional[float] = None
    total_gift_aid: Optional[float] = None
    total_self_help: Optional[float] = None

    # Metadata
    deadline: Optional[date] = None
    is_renewable: Optional[bool] = None
    conditions: List[str] = field(default_factory=list)

    def calculate_totals(self):
        """Calculate derived totals."""
        # Total gift aid (grants + scholarships)
        self.total_gift_aid = sum(self.grants.values()) + sum(self.scholarships.values())

        # Total self-help (loans + work study)
        loan_total = sum(self.loans.values())
        self.total_self_help = loan_total + (self.work_study or 0)

        # Net cost
        if self.total_cost and self.total_aid:
            self.net_cost = self.total_cost - self.total_aid


@dataclass
class TranscriptData:
    """Extracted data from an academic transcript."""
    school_name: Optional[str] = None
    student_name: Optional[str] = None  # Should be redacted

    # Academic Info
    cumulative_gpa: Optional[float] = None
    gpa_scale: float = 4.0
    credits_earned: Optional[float] = None
    credits_attempted: Optional[float] = None

    # By semester/term
    terms: List[Dict[str, Any]] = field(default_factory=list)

    # Courses
    courses: List[Dict[str, Any]] = field(default_factory=list)

    # Academic standing
    standing: Optional[str] = None  # e.g., "Good Standing", "Dean's List"
    honors: List[str] = field(default_factory=list)

    # For scholarship eligibility
    stem_courses: int = 0
    advanced_courses: int = 0


@dataclass
class DocumentAnalysisResult:
    """Result of analyzing a document."""
    document_type: DocumentType
    status: AnalysisStatus
    completeness: CompletionStatus
    extracted_fields: List[ExtractedField] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    data: Optional[Any] = None  # AwardLetterData, TranscriptData, etc.
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
    confidence_score: float = 0.0


# Required fields for validation
AWARD_LETTER_REQUIRED_FIELDS = [
    'school_name',
    'academic_year',
    'total_cost',
    'total_aid',
]

TRANSCRIPT_REQUIRED_FIELDS = [
    'cumulative_gpa',
    'credits_earned',
]


class DocumentAnalystAgent:
    """On-device agent for analyzing sensitive documents.

    CRITICAL: This agent runs ENTIRELY on-device. No document content
    is ever transmitted to external servers.

    Acceptance Criteria:
    - Can parse award letters extracting key fields
    - Can parse transcripts extracting GPA, courses
    - Validates document completeness
    - All processing is local (no data leaves device)
    """

    def __init__(
        self,
        config: AgentConfig = None,
    ):
        """Initialize the document analyst agent.

        Args:
            config: Agent configuration
        """
        self.config = config or document_analyst_config

        # Analysis history (in-memory only)
        self._analysis_history: List[DocumentAnalysisResult] = []

        # Pattern matchers for field extraction
        self._init_patterns()

    @property
    def model_name(self) -> str:
        """Get the model name for this agent."""
        return get_model_name(self.config.model)

    def _init_patterns(self):
        """Initialize regex patterns for field extraction."""
        # Money patterns
        self._money_pattern = re.compile(r'\$[\d,]+(?:\.\d{2})?')

        # GPA patterns
        self._gpa_pattern = re.compile(r'(\d+\.\d{1,2})\s*(?:/\s*(\d+\.\d{1,2}))?')

        # Date patterns
        self._date_pattern = re.compile(
            r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})|'
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'
        )

        # Academic year pattern
        self._academic_year_pattern = re.compile(r'20\d{2}[-–]20\d{2}')

        # Credit patterns
        self._credit_pattern = re.compile(r'(\d+(?:\.\d)?)\s*(?:credits?|hours?|units?)', re.I)

    async def analyze_document(
        self,
        content: str,
        document_type: Optional[DocumentType] = None,
        filename: Optional[str] = None,
    ) -> DocumentAnalysisResult:
        """Analyze a document and extract structured data.

        NOTE: This method receives document content as text. In production,
        the PDF parsing happens on-device before calling this method.

        Args:
            content: Document text content
            document_type: Type of document (auto-detected if None)
            filename: Optional filename for context

        Returns:
            DocumentAnalysisResult
        """
        # Auto-detect document type if not specified
        if document_type is None:
            document_type = self._detect_document_type(content, filename)

        # Route to appropriate analyzer
        if document_type == DocumentType.AWARD_LETTER:
            result = await self._analyze_award_letter(content)
        elif document_type == DocumentType.TRANSCRIPT:
            result = await self._analyze_transcript(content)
        elif document_type == DocumentType.SAR:
            result = await self._analyze_sar(content)
        else:
            result = await self._analyze_generic(content, document_type)

        # Store in history
        self._analysis_history.append(result)

        # Keep history bounded
        if len(self._analysis_history) > 50:
            self._analysis_history = self._analysis_history[-50:]

        return result

    def _detect_document_type(
        self,
        content: str,
        filename: Optional[str],
    ) -> DocumentType:
        """Detect the type of document based on content.

        Args:
            content: Document text
            filename: Optional filename

        Returns:
            Detected DocumentType
        """
        content_lower = content.lower()

        # Check filename first
        if filename:
            filename_lower = filename.lower()
            if 'award' in filename_lower or 'aid' in filename_lower:
                return DocumentType.AWARD_LETTER
            if 'transcript' in filename_lower:
                return DocumentType.TRANSCRIPT
            if 'sar' in filename_lower:
                return DocumentType.SAR

        # Content-based detection
        award_keywords = ['cost of attendance', 'financial aid award', 'grants', 'loans', 'net cost']
        if any(kw in content_lower for kw in award_keywords):
            return DocumentType.AWARD_LETTER

        transcript_keywords = ['transcript', 'cumulative gpa', 'credits earned', 'course', 'grade']
        if any(kw in content_lower for kw in transcript_keywords):
            return DocumentType.TRANSCRIPT

        sar_keywords = ['student aid report', 'expected family contribution', 'efc']
        if any(kw in content_lower for kw in sar_keywords):
            return DocumentType.SAR

        return DocumentType.OTHER

    async def _analyze_award_letter(
        self,
        content: str,
    ) -> DocumentAnalysisResult:
        """Analyze an award letter.

        Args:
            content: Award letter text

        Returns:
            DocumentAnalysisResult with AwardLetterData
        """
        extracted_fields = []
        missing_fields = []
        warnings = []

        data = AwardLetterData()

        # Extract school name (usually at top)
        school_match = self._extract_school_name(content)
        if school_match:
            data.school_name = school_match
            extracted_fields.append(ExtractedField(
                name='school_name',
                value=school_match,
                confidence=0.8,
            ))
        else:
            missing_fields.append('school_name')

        # Extract academic year
        year_match = self._academic_year_pattern.search(content)
        if year_match:
            data.academic_year = year_match.group()
            extracted_fields.append(ExtractedField(
                name='academic_year',
                value=data.academic_year,
                confidence=0.9,
            ))
        else:
            missing_fields.append('academic_year')

        # Extract monetary values
        money_extractions = self._extract_money_values(content)

        # Cost of Attendance
        coa_value = self._find_value_near_label(content, ['cost of attendance', 'total cost', 'coa'], money_extractions)
        if coa_value:
            data.total_cost = coa_value
            extracted_fields.append(ExtractedField(name='total_cost', value=coa_value, confidence=0.85))
        else:
            missing_fields.append('total_cost')

        # Tuition
        tuition = self._find_value_near_label(content, ['tuition'], money_extractions)
        if tuition:
            data.tuition = tuition
            extracted_fields.append(ExtractedField(name='tuition', value=tuition, confidence=0.8))

        # Room & Board
        room_board = self._find_value_near_label(content, ['room', 'board', 'housing'], money_extractions)
        if room_board:
            data.room_board = room_board
            extracted_fields.append(ExtractedField(name='room_board', value=room_board, confidence=0.75))

        # Total Aid
        total_aid = self._find_value_near_label(content, ['total aid', 'total financial aid', 'total package'], money_extractions)
        if total_aid:
            data.total_aid = total_aid
            extracted_fields.append(ExtractedField(name='total_aid', value=total_aid, confidence=0.85))
        else:
            missing_fields.append('total_aid')

        # Extract grants (Pell, State, Institutional)
        data.grants = self._extract_grants(content, money_extractions)
        for name, value in data.grants.items():
            extracted_fields.append(ExtractedField(name=f'grant_{name}', value=value, confidence=0.75))

        # Extract scholarships
        data.scholarships = self._extract_scholarships(content, money_extractions)
        for name, value in data.scholarships.items():
            extracted_fields.append(ExtractedField(name=f'scholarship_{name}', value=value, confidence=0.75))

        # Extract loans
        data.loans = self._extract_loans(content, money_extractions)
        for name, value in data.loans.items():
            extracted_fields.append(ExtractedField(name=f'loan_{name}', value=value, confidence=0.8))
            if value > 10000:
                warnings.append(f"High loan amount detected: ${value:,.2f}")

        # Work study
        work_study = self._find_value_near_label(content, ['work study', 'work-study'], money_extractions)
        if work_study:
            data.work_study = work_study
            extracted_fields.append(ExtractedField(name='work_study', value=work_study, confidence=0.8))

        # Calculate totals
        data.calculate_totals()

        # Check for conditions
        data.conditions = self._extract_conditions(content)
        if data.conditions:
            warnings.append(f"Found {len(data.conditions)} condition(s) on award")

        # Validate completeness
        completeness = self._validate_award_letter(data, missing_fields)

        # Calculate overall confidence
        confidence = sum(f.confidence for f in extracted_fields) / len(extracted_fields) if extracted_fields else 0

        return DocumentAnalysisResult(
            document_type=DocumentType.AWARD_LETTER,
            status=AnalysisStatus.COMPLETED,
            completeness=completeness,
            extracted_fields=extracted_fields,
            missing_fields=missing_fields,
            warnings=warnings,
            data=data,
            confidence_score=confidence,
        )

    async def _analyze_transcript(
        self,
        content: str,
    ) -> DocumentAnalysisResult:
        """Analyze a transcript.

        Args:
            content: Transcript text

        Returns:
            DocumentAnalysisResult with TranscriptData
        """
        extracted_fields = []
        missing_fields = []
        warnings = []

        data = TranscriptData()

        # Extract school name
        school_match = self._extract_school_name(content)
        if school_match:
            data.school_name = school_match
            extracted_fields.append(ExtractedField(name='school_name', value=school_match, confidence=0.8))

        # Extract GPA
        gpa_value = self._extract_gpa(content)
        if gpa_value:
            data.cumulative_gpa, data.gpa_scale = gpa_value
            extracted_fields.append(ExtractedField(
                name='cumulative_gpa',
                value=data.cumulative_gpa,
                confidence=0.9,
            ))

            # Warn if GPA seems low
            if data.cumulative_gpa < 2.0:
                warnings.append("GPA below 2.0 may affect aid eligibility")
        else:
            missing_fields.append('cumulative_gpa')

        # Extract credits
        credits = self._extract_credits(content)
        if credits:
            data.credits_earned, data.credits_attempted = credits
            extracted_fields.append(ExtractedField(name='credits_earned', value=data.credits_earned, confidence=0.85))
        else:
            missing_fields.append('credits_earned')

        # Extract courses (simplified)
        courses = self._extract_courses(content)
        data.courses = courses
        if courses:
            extracted_fields.append(ExtractedField(name='courses', value=f"{len(courses)} courses", confidence=0.7))

            # Count STEM courses
            stem_keywords = ['math', 'science', 'physics', 'chemistry', 'biology', 'computer', 'engineering', 'calculus', 'statistics']
            data.stem_courses = sum(1 for c in courses if any(kw in c.get('name', '').lower() for kw in stem_keywords))

        # Extract academic standing
        standing = self._extract_standing(content)
        if standing:
            data.standing = standing
            extracted_fields.append(ExtractedField(name='standing', value=standing, confidence=0.85))

        # Extract honors
        honors = self._extract_honors(content)
        if honors:
            data.honors = honors
            extracted_fields.append(ExtractedField(name='honors', value=honors, confidence=0.8))

        # Validate completeness
        completeness = CompletionStatus.COMPLETE if not missing_fields else CompletionStatus.MISSING_FIELDS

        confidence = sum(f.confidence for f in extracted_fields) / len(extracted_fields) if extracted_fields else 0

        return DocumentAnalysisResult(
            document_type=DocumentType.TRANSCRIPT,
            status=AnalysisStatus.COMPLETED,
            completeness=completeness,
            extracted_fields=extracted_fields,
            missing_fields=missing_fields,
            warnings=warnings,
            data=data,
            confidence_score=confidence,
        )

    async def _analyze_sar(
        self,
        content: str,
    ) -> DocumentAnalysisResult:
        """Analyze a Student Aid Report.

        Args:
            content: SAR text

        Returns:
            DocumentAnalysisResult
        """
        extracted_fields = []
        missing_fields = []

        # Extract EFC
        efc_pattern = re.compile(r'(?:EFC|Expected Family Contribution)[:\s]*\$?([\d,]+)', re.I)
        efc_match = efc_pattern.search(content)

        if efc_match:
            efc = float(efc_match.group(1).replace(',', ''))
            extracted_fields.append(ExtractedField(name='efc', value=efc, confidence=0.9))
        else:
            missing_fields.append('efc')

        # Extract verification status
        if 'selected for verification' in content.lower():
            extracted_fields.append(ExtractedField(name='verification_required', value=True, confidence=0.95))

        completeness = CompletionStatus.COMPLETE if not missing_fields else CompletionStatus.MISSING_FIELDS
        confidence = sum(f.confidence for f in extracted_fields) / len(extracted_fields) if extracted_fields else 0

        return DocumentAnalysisResult(
            document_type=DocumentType.SAR,
            status=AnalysisStatus.COMPLETED,
            completeness=completeness,
            extracted_fields=extracted_fields,
            missing_fields=missing_fields,
            confidence_score=confidence,
        )

    async def _analyze_generic(
        self,
        content: str,
        doc_type: DocumentType,
    ) -> DocumentAnalysisResult:
        """Analyze a generic document.

        Args:
            content: Document text
            doc_type: Document type

        Returns:
            DocumentAnalysisResult
        """
        extracted_fields = []

        # Extract any money values
        money_values = self._extract_money_values(content)
        if money_values:
            extracted_fields.append(ExtractedField(
                name='monetary_values',
                value=f"{len(money_values)} values found",
                confidence=0.7,
            ))

        # Extract dates
        dates = self._date_pattern.findall(content)
        if dates:
            extracted_fields.append(ExtractedField(
                name='dates',
                value=f"{len(dates)} dates found",
                confidence=0.6,
            ))

        return DocumentAnalysisResult(
            document_type=doc_type,
            status=AnalysisStatus.COMPLETED,
            completeness=CompletionStatus.INCOMPLETE,
            extracted_fields=extracted_fields,
            confidence_score=0.5,
        )

    # =========================================================================
    # Field Extraction Helpers
    # =========================================================================

    def _extract_school_name(self, content: str) -> Optional[str]:
        """Extract school name from content."""
        # Common patterns
        patterns = [
            r'((?:University|College|Institute|School)\s+of\s+[\w\s]+)',
            r'([\w\s]+(?:University|College|Institute))',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.I)
            if match:
                return match.group(1).strip()

        return None

    def _extract_money_values(self, content: str) -> List[Tuple[float, int]]:
        """Extract all money values with their positions."""
        values = []
        for match in self._money_pattern.finditer(content):
            value_str = match.group().replace('$', '').replace(',', '')
            try:
                value = float(value_str)
                values.append((value, match.start()))
            except ValueError:
                pass
        return values

    def _find_value_near_label(
        self,
        content: str,
        labels: List[str],
        money_values: List[Tuple[float, int]],
        max_distance: int = 100,
    ) -> Optional[float]:
        """Find a money value near a label."""
        content_lower = content.lower()

        for label in labels:
            label_pos = content_lower.find(label.lower())
            if label_pos >= 0:
                # Find closest money value after the label
                for value, pos in money_values:
                    if label_pos <= pos <= label_pos + max_distance:
                        return value

        return None

    def _extract_grants(
        self,
        content: str,
        money_values: List[Tuple[float, int]],
    ) -> Dict[str, float]:
        """Extract grant amounts."""
        grants = {}

        grant_labels = {
            'pell': ['pell grant', 'federal pell'],
            'seog': ['seog', 'supplemental educational'],
            'state': ['state grant', 'cal grant', 'tap'],
            'institutional': ['institutional grant', 'university grant', 'need-based grant'],
        }

        for grant_name, labels in grant_labels.items():
            value = self._find_value_near_label(content, labels, money_values)
            if value:
                grants[grant_name] = value

        return grants

    def _extract_scholarships(
        self,
        content: str,
        money_values: List[Tuple[float, int]],
    ) -> Dict[str, float]:
        """Extract scholarship amounts."""
        scholarships = {}

        scholarship_labels = {
            'merit': ['merit scholarship', 'academic scholarship'],
            'athletic': ['athletic scholarship'],
            'outside': ['outside scholarship', 'external scholarship'],
        }

        for name, labels in scholarship_labels.items():
            value = self._find_value_near_label(content, labels, money_values)
            if value:
                scholarships[name] = value

        return scholarships

    def _extract_loans(
        self,
        content: str,
        money_values: List[Tuple[float, int]],
    ) -> Dict[str, float]:
        """Extract loan amounts."""
        loans = {}

        loan_labels = {
            'subsidized': ['subsidized loan', 'direct subsidized'],
            'unsubsidized': ['unsubsidized loan', 'direct unsubsidized'],
            'plus': ['plus loan', 'parent plus', 'parent loan'],
            'perkins': ['perkins loan'],
        }

        for loan_name, labels in loan_labels.items():
            value = self._find_value_near_label(content, labels, money_values)
            if value:
                loans[loan_name] = value

        return loans

    def _extract_conditions(self, content: str) -> List[str]:
        """Extract conditions on aid."""
        conditions = []

        condition_patterns = [
            r'(?:must|required to|condition)[:\s]+([\w\s,]+)',
            r'(?:maintain|keep)[:\s]+(?:a\s+)?(\d+\.\d+)\s+GPA',
            r'full[- ]time\s+enrollment\s+required',
        ]

        for pattern in condition_patterns:
            matches = re.findall(pattern, content, re.I)
            if matches:
                if isinstance(matches[0], str):
                    conditions.extend(matches)
                else:
                    conditions.extend([m[0] if isinstance(m, tuple) else m for m in matches])

        return conditions[:5]  # Limit to 5 conditions

    def _extract_gpa(self, content: str) -> Optional[Tuple[float, float]]:
        """Extract GPA and scale."""
        gpa_patterns = [
            r'(?:cumulative|overall)\s+GPA[:\s]+(\d+\.\d{1,2})',
            r'GPA[:\s]+(\d+\.\d{1,2})\s*/\s*(\d+\.\d{1,2})',
            r'(\d+\.\d{1,2})\s+(?:out of|/)\s+(\d+\.\d{1,2})',
        ]

        for pattern in gpa_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                gpa = float(match.group(1))
                scale = float(match.group(2)) if match.lastindex >= 2 else 4.0
                return (gpa, scale)

        return None

    def _extract_credits(self, content: str) -> Optional[Tuple[float, float]]:
        """Extract credits earned and attempted."""
        earned_match = re.search(r'(?:credits?\s+earned|earned\s+credits?)[:\s]+(\d+(?:\.\d)?)', content, re.I)
        attempted_match = re.search(r'(?:credits?\s+attempted|attempted\s+credits?)[:\s]+(\d+(?:\.\d)?)', content, re.I)

        if earned_match:
            earned = float(earned_match.group(1))
            attempted = float(attempted_match.group(1)) if attempted_match else earned
            return (earned, attempted)

        return None

    def _extract_courses(self, content: str) -> List[Dict[str, Any]]:
        """Extract course information."""
        courses = []

        # Simple course pattern: SUBJ ### or similar
        course_pattern = re.compile(r'([A-Z]{2,4})\s*(\d{3,4})\s+(.+?)(?:\s+(\d+(?:\.\d)?)\s*(?:cr|credits?)?)?(?:\s+([A-F][+-]?))?', re.I)

        for match in course_pattern.finditer(content):
            course = {
                'subject': match.group(1),
                'number': match.group(2),
                'name': match.group(3).strip() if match.group(3) else '',
                'credits': float(match.group(4)) if match.group(4) else None,
                'grade': match.group(5) if match.group(5) else None,
            }
            courses.append(course)

        return courses[:50]  # Limit to 50 courses

    def _extract_standing(self, content: str) -> Optional[str]:
        """Extract academic standing."""
        standing_patterns = [
            r"(?:academic\s+standing|standing)[:\s]+([\w\s]+)",
            r"(good\s+standing|probation|dean'?s?\s+list)",
        ]

        for pattern in standing_patterns:
            match = re.search(pattern, content, re.I)
            if match:
                return match.group(1).strip()

        return None

    def _extract_honors(self, content: str) -> List[str]:
        """Extract honors and awards."""
        honors = []

        honor_keywords = ['dean\'s list', 'honor roll', 'cum laude', 'magna cum laude', 'summa cum laude', 'honors']

        for keyword in honor_keywords:
            if keyword.lower() in content.lower():
                honors.append(keyword.title())

        return honors

    def _validate_award_letter(
        self,
        data: AwardLetterData,
        missing_fields: List[str],
    ) -> CompletionStatus:
        """Validate award letter completeness."""
        critical_missing = [f for f in missing_fields if f in AWARD_LETTER_REQUIRED_FIELDS]

        if not critical_missing:
            return CompletionStatus.COMPLETE
        elif len(critical_missing) <= 2:
            return CompletionStatus.MISSING_FIELDS
        else:
            return CompletionStatus.INCOMPLETE

    # =========================================================================
    # Comparison and Validation Methods
    # =========================================================================

    async def compare_award_letters(
        self,
        letters: List[DocumentAnalysisResult],
    ) -> Dict[str, Any]:
        """Compare multiple award letters.

        Args:
            letters: List of analyzed award letters

        Returns:
            Comparison results
        """
        if len(letters) < 2:
            return {"error": "Need at least 2 letters to compare"}

        comparison = {
            "schools": [],
            "lowest_net_cost": None,
            "highest_gift_aid": None,
            "lowest_loans": None,
            "recommendation": "",
        }

        for letter in letters:
            if letter.data and isinstance(letter.data, AwardLetterData):
                data = letter.data
                school_info = {
                    "school": data.school_name,
                    "net_cost": data.net_cost,
                    "total_gift_aid": data.total_gift_aid,
                    "total_loans": sum(data.loans.values()),
                }
                comparison["schools"].append(school_info)

        # Find best options
        if comparison["schools"]:
            sorted_by_cost = sorted(comparison["schools"], key=lambda x: x.get("net_cost") or float('inf'))
            comparison["lowest_net_cost"] = sorted_by_cost[0]["school"] if sorted_by_cost else None

            sorted_by_gift = sorted(comparison["schools"], key=lambda x: x.get("total_gift_aid") or 0, reverse=True)
            comparison["highest_gift_aid"] = sorted_by_gift[0]["school"] if sorted_by_gift else None

            sorted_by_loans = sorted(comparison["schools"], key=lambda x: x.get("total_loans") or float('inf'))
            comparison["lowest_loans"] = sorted_by_loans[0]["school"] if sorted_by_loans else None

        return comparison

    async def validate_completeness(
        self,
        document_type: DocumentType,
        extracted_fields: List[ExtractedField],
    ) -> Dict[str, Any]:
        """Validate that required fields are present.

        Args:
            document_type: Type of document
            extracted_fields: Extracted fields

        Returns:
            Validation result
        """
        required = AWARD_LETTER_REQUIRED_FIELDS if document_type == DocumentType.AWARD_LETTER else TRANSCRIPT_REQUIRED_FIELDS
        extracted_names = {f.name for f in extracted_fields}

        missing = [f for f in required if f not in extracted_names]

        return {
            "complete": len(missing) == 0,
            "missing_fields": missing,
            "extracted_count": len(extracted_fields),
            "required_count": len(required),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get analyst statistics.

        Returns:
            Stats dict
        """
        by_type = {}
        for result in self._analysis_history:
            key = result.document_type.value
            by_type[key] = by_type.get(key, 0) + 1

        avg_confidence = 0
        if self._analysis_history:
            avg_confidence = sum(r.confidence_score for r in self._analysis_history) / len(self._analysis_history)

        return {
            "total_analyzed": len(self._analysis_history),
            "by_type": by_type,
            "average_confidence": round(avg_confidence, 2),
            "on_device_processing": True,  # Always true - critical feature
        }
