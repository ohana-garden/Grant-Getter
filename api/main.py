"""Student Ambassador API - FastAPI Application.

This API exposes core resources for the Student Ambassador Platform using
FalkorDB for graph storage and Graphiti for temporal knowledge management.
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends

from api.models import (
    Student,
    StudentCreate,
    Application,
    Negotiation,
    School,
    ScholarshipSource,
    ScholarshipMatch,
    EpisodeCreate,
    EpisodeResponse,
    FactCreate,
    FactResponse,
    SearchQuery,
    SearchResult,
    HealthStatus,
)
from db.falkordb_client import FalkorDBClient, get_client
from db.graphiti_client import GraphitiClient, get_graphiti_client


# Global clients (initialized on startup)
_falkordb_client: Optional[FalkorDBClient] = None
_graphiti_client: Optional[GraphitiClient] = None


def get_falkordb() -> FalkorDBClient:
    """Dependency to get FalkorDB client."""
    if _falkordb_client is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _falkordb_client


def get_graphiti() -> GraphitiClient:
    """Dependency to get Graphiti client."""
    if _graphiti_client is None:
        raise HTTPException(status_code=503, detail="Graphiti not initialized")
    return _graphiti_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - initialize and cleanup resources."""
    global _falkordb_client, _graphiti_client

    # Initialize FalkorDB
    _falkordb_client = get_client()
    _falkordb_client.connect()

    # Initialize Graphiti
    _graphiti_client = get_graphiti_client()
    await _graphiti_client.initialize()

    yield

    # Cleanup
    if _graphiti_client:
        await _graphiti_client.close()
    if _falkordb_client:
        _falkordb_client.close()


app = FastAPI(
    title="Student Ambassador API",
    version="0.1.0",
    description=(
        "API for the Student Ambassador Platform. Provides student management, "
        "scholarship matching, and temporal knowledge graph capabilities. "
        "Uses FalkorDB for graph storage and Graphiti for episodic memory."
    ),
    lifespan=lifespan,
)


# =============================================================================
# Health Check
# =============================================================================

@app.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check(
    falkordb: FalkorDBClient = Depends(get_falkordb),
    graphiti: GraphitiClient = Depends(get_graphiti),
) -> HealthStatus:
    """Check API health status including database connections."""
    falkordb_healthy = falkordb.health_check()
    graphiti_status = await graphiti.health_check()

    status = "healthy" if falkordb_healthy and graphiti_status.get('connected', False) else "degraded"

    return HealthStatus(
        status=status,
        falkordb=falkordb_healthy,
        graphiti=graphiti_status.get('connected', False),
        version="0.1.0",
    )


# =============================================================================
# Student Endpoints
# =============================================================================

@app.post("/students", response_model=Student, status_code=201, tags=["Students"])
async def create_student(
    student_data: StudentCreate,
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> Student:
    """Create a new student profile.

    Note: In production, PII is stored on-device only. This endpoint creates
    an anonymized profile reference in the commons graph.
    """
    # Check if student already exists
    existing = falkordb.query(
        "MATCH (s:Student {id: $id}) RETURN s",
        {'id': student_data.id}
    )
    if existing.result_set:
        raise HTTPException(status_code=400, detail="Student already exists")

    # Create student node in graph
    now = datetime.utcnow()
    falkordb.query(
        """
        CREATE (s:Student {
            id: $id,
            created_at: $created_at
        })
        RETURN s
        """,
        {'id': student_data.id, 'created_at': now.isoformat()}
    )

    return Student(
        id=student_data.id,
        created_at=now,
        documents=student_data.documents,
        test_scores=student_data.test_scores,
        activities=student_data.activities,
        essays=student_data.essays,
        recommendations=student_data.recommendations,
        financials=student_data.financials,
    )


@app.get("/students", response_model=List[Student], tags=["Students"])
async def list_students(
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> List[Student]:
    """Retrieve a list of all students (admin only)."""
    result = falkordb.query("MATCH (s:Student) RETURN s")

    students = []
    for row in result.result_set:
        node = row[0]
        props = node.properties
        students.append(Student(
            id=props.get('id', ''),
            created_at=datetime.fromisoformat(props['created_at']) if 'created_at' in props else datetime.utcnow(),
        ))

    return students


@app.get("/students/{student_id}", response_model=Student, tags=["Students"])
async def get_student(
    student_id: str,
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> Student:
    """Retrieve a single student by ID."""
    result = falkordb.query(
        "MATCH (s:Student {id: $id}) RETURN s",
        {'id': student_id}
    )

    if not result.result_set:
        raise HTTPException(status_code=404, detail="Student not found")

    node = result.result_set[0][0]
    props = node.properties

    return Student(
        id=props.get('id', ''),
        created_at=datetime.fromisoformat(props['created_at']) if 'created_at' in props else datetime.utcnow(),
    )


@app.delete("/students/{student_id}", status_code=204, tags=["Students"])
async def delete_student(
    student_id: str,
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> None:
    """Delete a student and all associated data."""
    result = falkordb.query(
        "MATCH (s:Student {id: $id}) RETURN s",
        {'id': student_id}
    )

    if not result.result_set:
        raise HTTPException(status_code=404, detail="Student not found")

    falkordb.query(
        "MATCH (s:Student {id: $id}) DETACH DELETE s",
        {'id': student_id}
    )


# =============================================================================
# Scholarship Endpoints
# =============================================================================

@app.get(
    "/students/{student_id}/scholarship-matches",
    response_model=List[ScholarshipMatch],
    tags=["Scholarships"],
)
async def get_scholarship_matches(
    student_id: str,
    min_score: float = Query(default=0.0, ge=0, le=1),
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> List[ScholarshipMatch]:
    """Generate scholarship matches for a student.

    Queries the commons graph for scholarship sources and computes match scores.
    """
    # Verify student exists
    student_result = falkordb.query(
        "MATCH (s:Student {id: $id}) RETURN s",
        {'id': student_id}
    )
    if not student_result.result_set:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get all scholarship sources from commons
    scholarships = falkordb.get_all_scholarship_sources()

    matches = []
    for row in scholarships.result_set:
        node = row[0]
        props = node.properties

        # Simple matching - in production, use student profile for scoring
        match_score = 0.8  # Placeholder score

        if match_score >= min_score:
            source = ScholarshipSource(
                id=props.get('id', ''),
                name=props.get('name', ''),
                amount_min=props.get('amount_min', 0),
                amount_max=props.get('amount_max', 0),
                criteria=props.get('criteria', ''),
                deadline=props.get('deadline', datetime.now().date()),
                verified=props.get('verified', True),
                url=props.get('url', ''),
                renewable=props.get('renewable', False),
            )

            matches.append(ScholarshipMatch(
                source=source,
                match_score=match_score,
                reasons=["Profile eligible based on commons data"],
            ))

    return matches


@app.get("/scholarships", response_model=List[ScholarshipSource], tags=["Scholarships"])
async def list_scholarships(
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> List[ScholarshipSource]:
    """List all scholarship sources from the commons graph."""
    result = falkordb.get_all_scholarship_sources()

    scholarships = []
    for row in result.result_set:
        node = row[0]
        props = node.properties
        scholarships.append(ScholarshipSource(
            id=props.get('id', ''),
            name=props.get('name', ''),
            amount_min=props.get('amount_min', 0),
            amount_max=props.get('amount_max', 0),
            criteria=props.get('criteria', ''),
            deadline=props.get('deadline', datetime.now().date()),
            verified=props.get('verified', True),
            url=props.get('url', ''),
            renewable=props.get('renewable', False),
        ))

    return scholarships


# =============================================================================
# School Endpoints
# =============================================================================

@app.get("/schools", response_model=List[School], tags=["Schools"])
async def list_schools(
    school_type: Optional[str] = Query(default=None),
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> List[School]:
    """List schools from the commons graph."""
    if school_type:
        result = falkordb.get_schools_by_type(school_type)
    else:
        result = falkordb.get_all_schools()

    schools = []
    for row in result.result_set:
        node = row[0]
        props = node.properties
        schools.append(School(
            id=props.get('id', ''),
            name=props.get('name', ''),
            school_type=props.get('type', ''),
            location=props.get('location', ''),
            selectivity=props.get('selectivity', ''),
        ))

    return schools


@app.get("/schools/{school_id}", response_model=School, tags=["Schools"])
async def get_school(
    school_id: str,
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> School:
    """Get a specific school by ID."""
    result = falkordb.get_school(school_id)

    if not result.result_set:
        raise HTTPException(status_code=404, detail="School not found")

    node = result.result_set[0][0]
    props = node.properties

    return School(
        id=props.get('id', ''),
        name=props.get('name', ''),
        school_type=props.get('type', ''),
        location=props.get('location', ''),
        selectivity=props.get('selectivity', ''),
    )


# =============================================================================
# Graphiti Memory Endpoints
# =============================================================================

@app.post("/memory/episodes", response_model=EpisodeResponse, status_code=201, tags=["Memory"])
async def create_episode(
    episode: EpisodeCreate,
    graphiti: GraphitiClient = Depends(get_graphiti),
) -> EpisodeResponse:
    """Add a conversation episode to the temporal knowledge graph.

    Episodes are processed to extract entities and relationships,
    maintaining temporal validity of facts.
    """
    episode_id = await graphiti.add_episode(
        name=episode.name,
        episode_body=episode.body,
        source_description=episode.source_description,
        group_id=episode.student_id,
    )

    if not episode_id:
        raise HTTPException(status_code=500, detail="Failed to create episode")

    return EpisodeResponse(
        id=episode_id,
        name=episode.name,
        created=True,
    )


@app.post("/memory/facts", response_model=FactResponse, status_code=201, tags=["Memory"])
async def create_fact(
    fact: FactCreate,
    graphiti: GraphitiClient = Depends(get_graphiti),
) -> FactResponse:
    """Add a temporal fact to the knowledge graph.

    Facts are tracked with bi-temporal timestamps for point-in-time queries.
    """
    fact_id = await graphiti.add_fact(
        subject=fact.subject,
        predicate=fact.predicate,
        obj=fact.object,
        source=fact.source,
    )

    if not fact_id:
        raise HTTPException(status_code=500, detail="Failed to create fact")

    return FactResponse(
        id=fact_id,
        subject=fact.subject,
        predicate=fact.predicate,
        created=True,
    )


@app.post("/memory/search", response_model=List[SearchResult], tags=["Memory"])
async def search_memory(
    query: SearchQuery,
    graphiti: GraphitiClient = Depends(get_graphiti),
) -> List[SearchResult]:
    """Search the temporal knowledge graph.

    Uses hybrid retrieval combining semantic search, BM25, and graph traversal.
    """
    group_ids = [query.student_id] if query.student_id else None

    results = await graphiti.search(
        query=query.query,
        num_results=query.num_results,
        group_ids=group_ids,
    )

    return [
        SearchResult(
            fact=r.get('fact', ''),
            name=r.get('name', ''),
            valid_at=r.get('valid_at'),
            invalid_at=r.get('invalid_at'),
            score=r.get('score', 0.0),
        )
        for r in results
    ]


@app.get(
    "/memory/students/{student_id}/history",
    response_model=List[SearchResult],
    tags=["Memory"],
)
async def get_student_history(
    student_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    graphiti: GraphitiClient = Depends(get_graphiti),
) -> List[SearchResult]:
    """Get conversation history for a student."""
    results = await graphiti.get_student_history(student_id, limit)

    return [
        SearchResult(
            fact=r.get('fact', ''),
            name=r.get('name', ''),
            valid_at=r.get('valid_at'),
            invalid_at=r.get('invalid_at'),
            score=r.get('score', 0.0),
        )
        for r in results
    ]


# =============================================================================
# Application Endpoints (for completeness with reference implementation)
# =============================================================================

@app.post("/applications", response_model=Application, status_code=201, tags=["Applications"])
async def create_application(
    application: Application,
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> Application:
    """Submit a new application for a student."""
    # Verify student exists
    student_result = falkordb.query(
        "MATCH (s:Student {id: $id}) RETURN s",
        {'id': application.student_id}
    )
    if not student_result.result_set:
        raise HTTPException(status_code=400, detail="Student does not exist")

    # Create application node
    falkordb.query(
        """
        CREATE (a:Application {
            id: $id,
            student_id: $student_id,
            school_id: $school_id,
            status: $status
        })
        RETURN a
        """,
        {
            'id': application.id,
            'student_id': application.student_id,
            'school_id': application.school_id,
            'status': application.app_status,
        }
    )

    return application


@app.get("/applications", response_model=List[Application], tags=["Applications"])
async def list_applications(
    student_id: Optional[str] = Query(default=None),
    falkordb: FalkorDBClient = Depends(get_falkordb),
) -> List[Application]:
    """List applications, optionally filtered by student."""
    if student_id:
        result = falkordb.query(
            "MATCH (a:Application {student_id: $student_id}) RETURN a",
            {'student_id': student_id}
        )
    else:
        result = falkordb.query("MATCH (a:Application) RETURN a")

    applications = []
    for row in result.result_set:
        node = row[0]
        props = node.properties
        applications.append(Application(
            id=props.get('id', ''),
            student_id=props.get('student_id', ''),
            school_id=props.get('school_id', ''),
            app_status=props.get('status', 'draft'),
        ))

    return applications
