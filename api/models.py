"""Data models for the Student Ambassador API.

Pydantic models for request/response validation, adapted from the reference implementation.
"""

from datetime import date as date_type, datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    """A file uploaded by the student, stored encrypted on device."""
    doc_type: str = Field(..., description="Type of document (e.g., transcript, award_letter).")
    content_hash: str = Field(..., description="Hash of the file content for deduplication.")
    encrypted_content: str = Field(..., description="Encrypted content (base64 encoded).")


class TestScore(BaseModel):
    """Standardized test score record."""
    test_type: str = Field(..., description="Type of test (e.g., SAT, ACT, AP).")
    score: float = Field(..., ge=0, description="Numeric score obtained.")
    test_date: date_type = Field(..., description="Date of the test.")


class Activity(BaseModel):
    """Extracurricular activity or job."""
    name: str = Field(..., description="Name of the activity.")
    role: str = Field(..., description="Role held in the activity.")
    hours: int = Field(..., ge=0, description="Number of hours spent.")
    years: List[int] = Field(..., description="Years of participation (e.g. [2023, 2024]).")


class Essay(BaseModel):
    """Essay draft or final submission."""
    school_id: str
    prompt: str
    version: int = Field(..., ge=1)
    content_hash: str


class Recommendation(BaseModel):
    """Recommendation request and status."""
    recommender: str
    rec_status: str = Field(..., pattern="^(requested|received|submitted)$")
    requested_date: date_type


class StudentCreate(BaseModel):
    """Request body for creating a student."""
    id: str
    documents: List[Document] = Field(default_factory=list)
    test_scores: List[TestScore] = Field(default_factory=list)
    activities: List[Activity] = Field(default_factory=list)
    essays: List[Essay] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    financials: Dict[str, Any] = Field(default_factory=dict)


class Student(BaseModel):
    """A single student with personal data."""
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    documents: List[Document] = Field(default_factory=list)
    test_scores: List[TestScore] = Field(default_factory=list)
    activities: List[Activity] = Field(default_factory=list)
    essays: List[Essay] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    financials: Dict[str, Any] = Field(default_factory=dict)


class Application(BaseModel):
    """An application record linking a student to a school."""
    id: str
    student_id: str
    school_id: str
    app_status: str = Field(..., pattern="^(draft|submitted|accepted|rejected)$")
    timeline: Dict[str, Any] = Field(default_factory=dict)


class Negotiation(BaseModel):
    """Aid negotiation or appeal event."""
    id: str
    student_id: str
    negotiation_type: str = Field(..., pattern="^(scholarship|grant|appeal|other)$")
    ask: Dict[str, Any]
    result: Optional[str] = None
    strategy_used: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ScholarshipSource(BaseModel):
    """Provider of scholarships or grants."""
    id: str
    name: str
    amount_min: float = Field(..., ge=0)
    amount_max: float = Field(..., ge=0)
    criteria: str
    deadline: date_type
    verified: bool = True
    url: str = ""
    renewable: bool = False


class ScholarshipMatch(BaseModel):
    """Return structure for scholarship matches."""
    source: ScholarshipSource
    match_score: float = Field(..., ge=0, le=1)
    reasons: List[str]


class School(BaseModel):
    """Educational institution from commons graph."""
    id: str
    name: str
    school_type: str  # public, private, community
    location: str
    selectivity: str  # highly_selective, selective, moderate, open


class EpisodeCreate(BaseModel):
    """Request body for creating a conversation episode."""
    name: str = Field(..., description="Episode identifier")
    body: str = Field(..., description="Conversation content")
    source_description: str = Field(default="conversation")
    student_id: Optional[str] = Field(default=None, description="Associated student ID")


class EpisodeResponse(BaseModel):
    """Response for created episode."""
    id: str
    name: str
    created: bool


class FactCreate(BaseModel):
    """Request body for creating a temporal fact."""
    subject: str
    predicate: str
    object: str
    source: str = "api"


class FactResponse(BaseModel):
    """Response for created fact."""
    id: str
    subject: str
    predicate: str
    created: bool


class SearchQuery(BaseModel):
    """Request body for knowledge graph search."""
    query: str
    num_results: int = Field(default=10, ge=1, le=100)
    student_id: Optional[str] = None


class SearchResult(BaseModel):
    """Single search result."""
    fact: str
    name: str = ""
    valid_at: Optional[datetime] = None
    invalid_at: Optional[datetime] = None
    score: float = 0.0


class HealthStatus(BaseModel):
    """Health check response."""
    status: str
    falkordb: bool
    graphiti: bool
    version: str = "0.1.0"
