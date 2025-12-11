"""
FalkorDB Client for Student Ambassador Platform

Provides a connection wrapper for FalkorDB graph database operations.
"""

import os
from typing import Any, Optional
from falkordb import FalkorDB


class FalkorDBClient:
    """Client for interacting with FalkorDB graph database."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        password: Optional[str] = None,
        graph_name: str = "student_ambassador"
    ):
        """
        Initialize FalkorDB client.

        Args:
            host: FalkorDB host address
            port: FalkorDB port (default 6379)
            password: Optional password for authentication
            graph_name: Name of the graph to use
        """
        self.host = host
        self.port = port
        self.password = password
        self.graph_name = graph_name
        self._client: Optional[FalkorDB] = None
        self._graph = None

    def connect(self) -> None:
        """Establish connection to FalkorDB."""
        self._client = FalkorDB(
            host=self.host,
            port=self.port,
            password=self.password
        )
        self._graph = self._client.select_graph(self.graph_name)

    def close(self) -> None:
        """Close the database connection."""
        if self._client:
            self._client = None
            self._graph = None

    @property
    def graph(self):
        """Get the graph instance, connecting if necessary."""
        if self._graph is None:
            self.connect()
        return self._graph

    def query(self, cypher: str, params: Optional[dict] = None) -> Any:
        """
        Execute a Cypher query.

        Args:
            cypher: Cypher query string
            params: Optional query parameters

        Returns:
            Query result
        """
        if params:
            return self.graph.query(cypher, params)
        return self.graph.query(cypher)

    def execute_many(self, queries: list[str]) -> list[Any]:
        """
        Execute multiple Cypher queries.

        Args:
            queries: List of Cypher query strings

        Returns:
            List of query results
        """
        results = []
        for query in queries:
            if query.strip():
                result = self.query(query)
                results.append(result)
        return results

    def delete_all(self) -> None:
        """Delete all nodes and relationships in the graph."""
        self.query("MATCH (n) DETACH DELETE n")

    # ==========================================================================
    # School Operations
    # ==========================================================================

    def create_school(
        self,
        school_id: str,
        name: str,
        school_type: str,
        location: str,
        selectivity: str
    ) -> Any:
        """
        Create a School node.

        Args:
            school_id: Unique identifier
            name: School name
            school_type: Type (public, private, community)
            location: Geographic location
            selectivity: Admission selectivity level

        Returns:
            Query result
        """
        query = """
        CREATE (s:School {
            id: $id,
            name: $name,
            type: $type,
            location: $location,
            selectivity: $selectivity
        })
        RETURN s
        """
        return self.query(query, {
            'id': school_id,
            'name': name,
            'type': school_type,
            'location': location,
            'selectivity': selectivity
        })

    def get_school(self, school_id: str) -> Any:
        """Get a school by ID."""
        query = "MATCH (s:School {id: $id}) RETURN s"
        return self.query(query, {'id': school_id})

    def get_schools_by_type(self, school_type: str) -> Any:
        """Get all schools of a specific type."""
        query = "MATCH (s:School {type: $type}) RETURN s"
        return self.query(query, {'type': school_type})

    def get_all_schools(self) -> Any:
        """Get all schools."""
        return self.query("MATCH (s:School) RETURN s")

    # ==========================================================================
    # ScholarshipSource Operations
    # ==========================================================================

    def create_scholarship_source(
        self,
        source_id: str,
        name: str,
        amount_min: float,
        amount_max: float,
        criteria: str,
        deadline: str,
        verified: bool = True,
        url: str = "",
        renewable: bool = False
    ) -> Any:
        """
        Create a ScholarshipSource node.

        Args:
            source_id: Unique identifier
            name: Scholarship name
            amount_min: Minimum award amount
            amount_max: Maximum award amount
            criteria: Eligibility criteria
            deadline: Application deadline (YYYY-MM-DD)
            verified: Whether source is verified
            url: Application URL
            renewable: Whether scholarship is renewable

        Returns:
            Query result
        """
        query = """
        CREATE (ss:ScholarshipSource {
            id: $id,
            name: $name,
            amount_min: $amount_min,
            amount_max: $amount_max,
            criteria: $criteria,
            deadline: date($deadline),
            verified: $verified,
            url: $url,
            renewable: $renewable
        })
        RETURN ss
        """
        return self.query(query, {
            'id': source_id,
            'name': name,
            'amount_min': amount_min,
            'amount_max': amount_max,
            'criteria': criteria,
            'deadline': deadline,
            'verified': verified,
            'url': url,
            'renewable': renewable
        })

    def get_scholarship_source(self, source_id: str) -> Any:
        """Get a scholarship source by ID."""
        query = "MATCH (ss:ScholarshipSource {id: $id}) RETURN ss"
        return self.query(query, {'id': source_id})

    def get_scholarships_by_amount_range(
        self,
        min_amount: float,
        max_amount: float
    ) -> Any:
        """Get scholarships within an amount range."""
        query = """
        MATCH (ss:ScholarshipSource)
        WHERE ss.amount_min >= $min AND ss.amount_max <= $max
        RETURN ss
        ORDER BY ss.amount_max DESC
        """
        return self.query(query, {'min': min_amount, 'max': max_amount})

    def get_all_scholarship_sources(self) -> Any:
        """Get all scholarship sources."""
        return self.query("MATCH (ss:ScholarshipSource) RETURN ss")

    def get_upcoming_scholarships(self, days: int = 90) -> Any:
        """Get scholarships with deadlines within the specified days."""
        query = """
        MATCH (ss:ScholarshipSource)
        WHERE ss.deadline >= date() AND ss.deadline <= date() + duration({days: $days})
        RETURN ss
        ORDER BY ss.deadline ASC
        """
        return self.query(query, {'days': days})

    # ==========================================================================
    # Relationship Operations
    # ==========================================================================

    def create_school_behavior(
        self,
        school_id: str,
        behavior_id: str,
        confidence: float,
        sample_size: int
    ) -> Any:
        """
        Create an EXHIBITS_BEHAVIOR relationship between School and BehaviorType.

        Args:
            school_id: School node ID
            behavior_id: BehaviorType node ID
            confidence: Confidence score (0.0-1.0)
            sample_size: Number of data points

        Returns:
            Query result
        """
        query = """
        MATCH (s:School {id: $school_id})
        MATCH (b:BehaviorType {id: $behavior_id})
        CREATE (s)-[r:EXHIBITS_BEHAVIOR {
            confidence: $confidence,
            sample_size: $sample_size
        }]->(b)
        RETURN r
        """
        return self.query(query, {
            'school_id': school_id,
            'behavior_id': behavior_id,
            'confidence': confidence,
            'sample_size': sample_size
        })

    def get_school_behaviors(self, school_id: str) -> Any:
        """Get all behaviors exhibited by a school."""
        query = """
        MATCH (s:School {id: $id})-[r:EXHIBITS_BEHAVIOR]->(b:BehaviorType)
        RETURN b.pattern as pattern, b.description as description,
               r.confidence as confidence, r.sample_size as sample_size
        """
        return self.query(query, {'id': school_id})

    def get_schools_with_behavior(self, behavior_pattern: str) -> Any:
        """Get all schools that exhibit a specific behavior pattern."""
        query = """
        MATCH (s:School)-[r:EXHIBITS_BEHAVIOR]->(b:BehaviorType {pattern: $pattern})
        RETURN s.name as school_name, s.type as school_type,
               r.confidence as confidence, r.sample_size as sample_size
        ORDER BY r.confidence DESC
        """
        return self.query(query, {'pattern': behavior_pattern})

    # ==========================================================================
    # Strategy Operations
    # ==========================================================================

    def get_strategies_for_school(self, school_id: str) -> Any:
        """Get effective strategies for a specific school."""
        query = """
        MATCH (st:Strategy)-[:TARGETS]->(s:School {id: $id})
        RETURN st.type as strategy_type, st.description as description,
               st.success_rate as success_rate, st.sample_size as sample_size
        ORDER BY st.success_rate DESC
        """
        return self.query(query, {'id': school_id})

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    def count_nodes(self, label: str) -> int:
        """Count nodes with a specific label."""
        result = self.query(f"MATCH (n:{label}) RETURN count(n) as count")
        if result.result_set:
            return result.result_set[0][0]
        return 0

    def count_relationships(self, rel_type: str) -> int:
        """Count relationships of a specific type."""
        result = self.query(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
        if result.result_set:
            return result.result_set[0][0]
        return 0

    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            result = self.query("RETURN 1 as health")
            return result.result_set[0][0] == 1
        except Exception:
            return False


def get_client(
    host: Optional[str] = None,
    port: Optional[int] = None,
    graph_name: str = "student_ambassador"
) -> FalkorDBClient:
    """
    Get a FalkorDB client instance using environment variables or defaults.

    Args:
        host: Override host (default: FALKORDB_HOST env or localhost)
        port: Override port (default: FALKORDB_PORT env or 6379)
        graph_name: Name of the graph to use

    Returns:
        Configured FalkorDBClient instance
    """
    return FalkorDBClient(
        host=host or os.getenv('FALKORDB_HOST', 'localhost'),
        port=port or int(os.getenv('FALKORDB_PORT', '6379')),
        password=os.getenv('FALKORDB_PASSWORD'),
        graph_name=graph_name
    )
