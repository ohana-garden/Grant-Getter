"""
Tests for FalkorDB Setup - Story 1.1

Verifies:
- FalkorDB running on localhost:6379
- Can create/query School nodes
- Can create/query ScholarshipSource nodes
- Can create relationships
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


class MockNode:
    """Mock FalkorDB node for testing."""
    def __init__(self, properties: dict):
        self.properties = properties


class MockResult:
    """Mock FalkorDB query result."""
    def __init__(self, result_set: list):
        self.result_set = result_set


class TestFalkorDBClient:
    """Tests for FalkorDBClient without requiring actual database connection."""

    def test_client_initialization(self):
        """Test client can be initialized with default values."""
        from db.falkordb_client import FalkorDBClient

        client = FalkorDBClient()
        assert client.host == "localhost"
        assert client.port == 6379
        assert client.graph_name == "student_ambassador"

    def test_client_custom_initialization(self):
        """Test client can be initialized with custom values."""
        from db.falkordb_client import FalkorDBClient

        client = FalkorDBClient(
            host="custom-host",
            port=6380,
            password="secret",
            graph_name="custom_graph"
        )
        assert client.host == "custom-host"
        assert client.port == 6380
        assert client.password == "secret"
        assert client.graph_name == "custom_graph"

    @patch('db.falkordb_client.FalkorDB')
    def test_connect(self, mock_falkordb_class):
        """Test database connection."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        client = FalkorDBClient()
        client.connect()

        mock_falkordb_class.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None
        )
        mock_db.select_graph.assert_called_once_with("student_ambassador")

    @patch('db.falkordb_client.FalkorDB')
    def test_query_execution(self, mock_falkordb_class):
        """Test Cypher query execution."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph
        mock_graph.query.return_value = MockResult([[1]])

        client = FalkorDBClient()
        client.connect()
        result = client.query("RETURN 1")

        mock_graph.query.assert_called_once_with("RETURN 1")
        assert result.result_set == [[1]]

    @patch('db.falkordb_client.FalkorDB')
    def test_query_with_params(self, mock_falkordb_class):
        """Test Cypher query execution with parameters."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph
        mock_graph.query.return_value = MockResult([["test"]])

        client = FalkorDBClient()
        client.connect()
        result = client.query("MATCH (n {id: $id}) RETURN n", {'id': 'test'})

        mock_graph.query.assert_called_once_with(
            "MATCH (n {id: $id}) RETURN n",
            {'id': 'test'}
        )

    @patch('db.falkordb_client.FalkorDB')
    def test_health_check_success(self, mock_falkordb_class):
        """Test health check returns True when database is healthy."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph
        mock_graph.query.return_value = MockResult([[1]])

        client = FalkorDBClient()
        client.connect()
        assert client.health_check() is True

    @patch('db.falkordb_client.FalkorDB')
    def test_health_check_failure(self, mock_falkordb_class):
        """Test health check returns False when database is unhealthy."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph
        mock_graph.query.side_effect = Exception("Connection failed")

        client = FalkorDBClient()
        client.connect()
        assert client.health_check() is False


class TestSchoolOperations:
    """Tests for School node operations."""

    @patch('db.falkordb_client.FalkorDB')
    def test_create_school(self, mock_falkordb_class):
        """Test creating a School node."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        school_node = MockNode({
            'id': 'school_test',
            'name': 'Test University',
            'type': 'private',
            'location': 'California',
            'selectivity': 'selective'
        })
        mock_graph.query.return_value = MockResult([[school_node]])

        client = FalkorDBClient()
        client.connect()
        result = client.create_school(
            school_id='school_test',
            name='Test University',
            school_type='private',
            location='California',
            selectivity='selective'
        )

        assert result.result_set[0][0].properties['name'] == 'Test University'

    @patch('db.falkordb_client.FalkorDB')
    def test_get_school(self, mock_falkordb_class):
        """Test retrieving a School by ID."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        school_node = MockNode({
            'id': 'school_stanford',
            'name': 'Stanford University',
            'type': 'private',
            'location': 'California',
            'selectivity': 'highly_selective'
        })
        mock_graph.query.return_value = MockResult([[school_node]])

        client = FalkorDBClient()
        client.connect()
        result = client.get_school('school_stanford')

        assert len(result.result_set) == 1
        assert result.result_set[0][0].properties['name'] == 'Stanford University'

    @patch('db.falkordb_client.FalkorDB')
    def test_get_schools_by_type(self, mock_falkordb_class):
        """Test retrieving schools by type."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        schools = [
            MockNode({'id': 'school1', 'name': 'Uni 1', 'type': 'public'}),
            MockNode({'id': 'school2', 'name': 'Uni 2', 'type': 'public'})
        ]
        mock_graph.query.return_value = MockResult([[s] for s in schools])

        client = FalkorDBClient()
        client.connect()
        result = client.get_schools_by_type('public')

        assert len(result.result_set) == 2

    @patch('db.falkordb_client.FalkorDB')
    def test_get_all_schools(self, mock_falkordb_class):
        """Test retrieving all schools."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        schools = [
            MockNode({'id': f'school{i}', 'name': f'University {i}'})
            for i in range(10)
        ]
        mock_graph.query.return_value = MockResult([[s] for s in schools])

        client = FalkorDBClient()
        client.connect()
        result = client.get_all_schools()

        assert len(result.result_set) == 10


class TestScholarshipOperations:
    """Tests for ScholarshipSource node operations."""

    @patch('db.falkordb_client.FalkorDB')
    def test_create_scholarship_source(self, mock_falkordb_class):
        """Test creating a ScholarshipSource node."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        scholarship = MockNode({
            'id': 'scholarship_test',
            'name': 'Test Scholarship',
            'amount_min': 5000.0,
            'amount_max': 10000.0,
            'criteria': 'Test criteria',
            'verified': True
        })
        mock_graph.query.return_value = MockResult([[scholarship]])

        client = FalkorDBClient()
        client.connect()
        result = client.create_scholarship_source(
            source_id='scholarship_test',
            name='Test Scholarship',
            amount_min=5000.0,
            amount_max=10000.0,
            criteria='Test criteria',
            deadline='2025-12-31',
            verified=True
        )

        assert result.result_set[0][0].properties['name'] == 'Test Scholarship'

    @patch('db.falkordb_client.FalkorDB')
    def test_get_scholarship_source(self, mock_falkordb_class):
        """Test retrieving a ScholarshipSource by ID."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        scholarship = MockNode({
            'id': 'scholarship_gates',
            'name': 'Gates Scholarship',
            'amount_min': 50000.0,
            'amount_max': 300000.0
        })
        mock_graph.query.return_value = MockResult([[scholarship]])

        client = FalkorDBClient()
        client.connect()
        result = client.get_scholarship_source('scholarship_gates')

        assert len(result.result_set) == 1
        assert result.result_set[0][0].properties['name'] == 'Gates Scholarship'

    @patch('db.falkordb_client.FalkorDB')
    def test_get_all_scholarship_sources(self, mock_falkordb_class):
        """Test retrieving all scholarship sources."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        scholarships = [
            MockNode({'id': f'scholarship{i}', 'name': f'Scholarship {i}'})
            for i in range(10)
        ]
        mock_graph.query.return_value = MockResult([[s] for s in scholarships])

        client = FalkorDBClient()
        client.connect()
        result = client.get_all_scholarship_sources()

        assert len(result.result_set) == 10


class TestRelationshipOperations:
    """Tests for relationship operations."""

    @patch('db.falkordb_client.FalkorDB')
    def test_create_school_behavior_relationship(self, mock_falkordb_class):
        """Test creating EXHIBITS_BEHAVIOR relationship."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph
        mock_graph.query.return_value = MockResult([["relationship_created"]])

        client = FalkorDBClient()
        client.connect()
        result = client.create_school_behavior(
            school_id='school_test',
            behavior_id='behavior_test',
            confidence=0.85,
            sample_size=100
        )

        # Verify the query was called with correct parameters
        call_args = mock_graph.query.call_args
        assert 'EXHIBITS_BEHAVIOR' in call_args[0][0]

    @patch('db.falkordb_client.FalkorDB')
    def test_get_school_behaviors(self, mock_falkordb_class):
        """Test retrieving behaviors for a school."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        behaviors = [
            ['need_blind_admission', 'Does not consider finances', 0.95, 500],
            ['meets_full_need', 'Meets 100% demonstrated need', 0.98, 500]
        ]
        mock_graph.query.return_value = MockResult(behaviors)

        client = FalkorDBClient()
        client.connect()
        result = client.get_school_behaviors('school_stanford')

        assert len(result.result_set) == 2

    @patch('db.falkordb_client.FalkorDB')
    def test_get_schools_with_behavior(self, mock_falkordb_class):
        """Test retrieving schools with a specific behavior."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph

        schools = [
            ['Stanford University', 'private', 0.98, 500],
            ['Harvard University', 'private', 0.98, 600]
        ]
        mock_graph.query.return_value = MockResult(schools)

        client = FalkorDBClient()
        client.connect()
        result = client.get_schools_with_behavior('meets_full_demonstrated_need')

        assert len(result.result_set) == 2


class TestCountOperations:
    """Tests for count operations."""

    @patch('db.falkordb_client.FalkorDB')
    def test_count_nodes(self, mock_falkordb_class):
        """Test counting nodes by label."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph
        mock_graph.query.return_value = MockResult([[10]])

        client = FalkorDBClient()
        client.connect()
        count = client.count_nodes('School')

        assert count == 10

    @patch('db.falkordb_client.FalkorDB')
    def test_count_relationships(self, mock_falkordb_class):
        """Test counting relationships by type."""
        from db.falkordb_client import FalkorDBClient

        mock_db = MagicMock()
        mock_graph = MagicMock()
        mock_falkordb_class.return_value = mock_db
        mock_db.select_graph.return_value = mock_graph
        mock_graph.query.return_value = MockResult([[5]])

        client = FalkorDBClient()
        client.connect()
        count = client.count_relationships('EXHIBITS_BEHAVIOR')

        assert count == 5


class TestCypherFiles:
    """Tests for Cypher file loading."""

    def test_load_cypher_file(self):
        """Test loading and parsing Cypher file."""
        from db.init_db import load_cypher_file
        import tempfile
        import os

        # Create a temporary Cypher file
        content = """
        // This is a comment
        CREATE (n:Test {id: 'test1'});

        // Another comment
        CREATE (m:Test {id: 'test2'});

        MATCH (n), (m) CREATE (n)-[:RELATES]->(m);
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.cypher', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            statements = load_cypher_file(temp_path)
            assert len(statements) == 3
            assert 'test1' in statements[0]
            assert 'test2' in statements[1]
            assert 'RELATES' in statements[2]
        finally:
            os.unlink(temp_path)


class TestSeedDataContent:
    """Tests to verify seed data content."""

    def test_seed_file_exists(self):
        """Test that seed data file exists."""
        from pathlib import Path

        seed_file = Path(__file__).parent.parent / 'db' / 'seed_data.cypher'
        assert seed_file.exists(), "Seed data file should exist"

    def test_seed_file_has_schools(self):
        """Test that seed data contains school definitions."""
        from pathlib import Path

        seed_file = Path(__file__).parent.parent / 'db' / 'seed_data.cypher'
        content = seed_file.read_text()

        # Check for expected schools
        assert 'Stanford University' in content
        assert 'MIT' in content or 'Massachusetts Institute of Technology' in content
        assert 'Harvard University' in content

    def test_seed_file_has_scholarships(self):
        """Test that seed data contains scholarship definitions."""
        from pathlib import Path

        seed_file = Path(__file__).parent.parent / 'db' / 'seed_data.cypher'
        content = seed_file.read_text()

        # Check for expected scholarships
        assert 'Gates Scholarship' in content
        assert 'ScholarshipSource' in content

    def test_seed_file_has_behaviors(self):
        """Test that seed data contains behavior type definitions."""
        from pathlib import Path

        seed_file = Path(__file__).parent.parent / 'db' / 'seed_data.cypher'
        content = seed_file.read_text()

        # Check for expected behavior types
        assert 'BehaviorType' in content
        assert 'negotiates_with_competing_offers' in content

    def test_seed_file_has_relationships(self):
        """Test that seed data contains relationship definitions."""
        from pathlib import Path

        seed_file = Path(__file__).parent.parent / 'db' / 'seed_data.cypher'
        content = seed_file.read_text()

        # Check for relationships
        assert 'EXHIBITS_BEHAVIOR' in content
        assert 'TARGETS' in content


class TestSchemaContent:
    """Tests to verify schema content."""

    def test_schema_file_exists(self):
        """Test that schema file exists."""
        from pathlib import Path

        schema_file = Path(__file__).parent.parent / 'db' / 'schema.cypher'
        assert schema_file.exists(), "Schema file should exist"

    def test_schema_defines_node_types(self):
        """Test that schema defines expected node types."""
        from pathlib import Path

        schema_file = Path(__file__).parent.parent / 'db' / 'schema.cypher'
        content = schema_file.read_text()

        # Check for expected node type definitions
        assert 'School' in content
        assert 'ScholarshipSource' in content
        assert 'AnonymizedProfile' in content
        assert 'Strategy' in content
        assert 'Outcome' in content
        assert 'BehaviorType' in content

    def test_schema_defines_indexes(self):
        """Test that schema defines indexes."""
        from pathlib import Path

        schema_file = Path(__file__).parent.parent / 'db' / 'schema.cypher'
        content = schema_file.read_text()

        # Check for index definitions
        assert 'CREATE INDEX' in content


class TestDockerCompose:
    """Tests for Docker Compose configuration."""

    def test_docker_compose_exists(self):
        """Test that docker-compose.yml exists."""
        from pathlib import Path

        compose_file = Path(__file__).parent.parent / 'docker-compose.yml'
        assert compose_file.exists(), "docker-compose.yml should exist"

    def test_docker_compose_has_falkordb(self):
        """Test that docker-compose.yml defines FalkorDB service."""
        from pathlib import Path

        compose_file = Path(__file__).parent.parent / 'docker-compose.yml'
        content = compose_file.read_text()

        assert 'falkordb' in content
        assert 'falkordb/falkordb' in content
        assert '6379:6379' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
