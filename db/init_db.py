"""
Database Initialization for Student Ambassador Platform

This module handles:
- Loading schema and seed data into FalkorDB
- Verifying database setup
- Running test queries
"""

import os
from pathlib import Path
from typing import Optional

from db.falkordb_client import FalkorDBClient, get_client


def load_cypher_file(file_path: str) -> list[str]:
    """
    Load and parse a Cypher file into individual statements.

    Args:
        file_path: Path to the .cypher file

    Returns:
        List of Cypher statements
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Remove comments and split by semicolon
    lines = []
    for line in content.split('\n'):
        # Remove single-line comments
        if '//' in line:
            line = line[:line.index('//')]
        lines.append(line)

    content = '\n'.join(lines)

    # Split by semicolon and filter empty statements
    statements = [s.strip() for s in content.split(';') if s.strip()]

    return statements


def init_database(
    client: Optional[FalkorDBClient] = None,
    clear_existing: bool = True,
    load_seed_data: bool = True
) -> dict:
    """
    Initialize the FalkorDB database with schema and seed data.

    Args:
        client: Optional FalkorDBClient instance
        clear_existing: Whether to clear existing data
        load_seed_data: Whether to load seed data

    Returns:
        Dictionary with initialization results
    """
    if client is None:
        client = get_client()

    results = {
        'success': False,
        'cleared': False,
        'seed_loaded': False,
        'node_counts': {},
        'relationship_counts': {},
        'errors': []
    }

    try:
        # Verify connection
        if not client.health_check():
            results['errors'].append("Failed to connect to FalkorDB")
            return results

        # Clear existing data if requested
        if clear_existing:
            client.delete_all()
            results['cleared'] = True

        # Load seed data if requested
        if load_seed_data:
            db_dir = Path(__file__).parent
            seed_file = db_dir / 'seed_data.cypher'

            if seed_file.exists():
                statements = load_cypher_file(str(seed_file))
                for stmt in statements:
                    try:
                        client.query(stmt)
                    except Exception as e:
                        results['errors'].append(f"Error executing: {stmt[:50]}... - {str(e)}")

                results['seed_loaded'] = True
            else:
                results['errors'].append(f"Seed file not found: {seed_file}")

        # Count nodes
        for label in ['School', 'ScholarshipSource', 'BehaviorType', 'Strategy', 'AnonymizedProfile', 'Outcome']:
            count = client.count_nodes(label)
            results['node_counts'][label] = count

        # Count relationships
        for rel_type in ['EXHIBITS_BEHAVIOR', 'TARGETS', 'APPLIED_TO', 'MATCHED_TO', 'RECEIVED']:
            count = client.count_relationships(rel_type)
            results['relationship_counts'][rel_type] = count

        results['success'] = len(results['errors']) == 0

    except Exception as e:
        results['errors'].append(f"Initialization error: {str(e)}")

    return results


def verify_database(client: Optional[FalkorDBClient] = None) -> dict:
    """
    Verify database setup by running test queries.

    Args:
        client: Optional FalkorDBClient instance

    Returns:
        Dictionary with verification results
    """
    if client is None:
        client = get_client()

    results = {
        'success': True,
        'tests': []
    }

    # Test 1: Query Schools
    test = {'name': 'Query all schools', 'passed': False, 'result': None}
    try:
        result = client.get_all_schools()
        test['passed'] = len(result.result_set) > 0
        test['result'] = f"Found {len(result.result_set)} schools"
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Test 2: Query ScholarshipSources
    test = {'name': 'Query all scholarship sources', 'passed': False, 'result': None}
    try:
        result = client.get_all_scholarship_sources()
        test['passed'] = len(result.result_set) > 0
        test['result'] = f"Found {len(result.result_set)} scholarship sources"
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Test 3: Query specific school
    test = {'name': 'Query school by ID', 'passed': False, 'result': None}
    try:
        result = client.get_school('school_stanford')
        test['passed'] = len(result.result_set) == 1
        if result.result_set:
            node = result.result_set[0][0]
            test['result'] = f"Found: {node.properties.get('name', 'Unknown')}"
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Test 4: Query school behaviors
    test = {'name': 'Query school behaviors', 'passed': False, 'result': None}
    try:
        result = client.get_school_behaviors('school_stanford')
        test['passed'] = len(result.result_set) > 0
        test['result'] = f"Found {len(result.result_set)} behaviors for Stanford"
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Test 5: Query schools with behavior
    test = {'name': 'Query schools with specific behavior', 'passed': False, 'result': None}
    try:
        result = client.get_schools_with_behavior('meets_full_demonstrated_need')
        test['passed'] = len(result.result_set) > 0
        test['result'] = f"Found {len(result.result_set)} schools that meet full need"
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Test 6: Query strategies for school
    test = {'name': 'Query strategies for school', 'passed': False, 'result': None}
    try:
        result = client.get_strategies_for_school('school_usc')
        test['passed'] = len(result.result_set) > 0
        test['result'] = f"Found {len(result.result_set)} strategies for USC"
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Test 7: Create new school (write test)
    test = {'name': 'Create new school node', 'passed': False, 'result': None}
    try:
        result = client.create_school(
            school_id='school_test_temp',
            name='Test University',
            school_type='private',
            location='Test State',
            selectivity='moderate'
        )
        # Verify it was created
        verify = client.get_school('school_test_temp')
        test['passed'] = len(verify.result_set) == 1
        test['result'] = "Successfully created and verified new school"
        # Clean up
        client.query("MATCH (s:School {id: 'school_test_temp'}) DELETE s")
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Test 8: Create new scholarship source (write test)
    test = {'name': 'Create new scholarship source', 'passed': False, 'result': None}
    try:
        result = client.create_scholarship_source(
            source_id='scholarship_test_temp',
            name='Test Scholarship',
            amount_min=1000.0,
            amount_max=5000.0,
            criteria='Test criteria',
            deadline='2025-12-31',
            verified=True
        )
        # Verify it was created
        verify = client.get_scholarship_source('scholarship_test_temp')
        test['passed'] = len(verify.result_set) == 1
        test['result'] = "Successfully created and verified new scholarship source"
        # Clean up
        client.query("MATCH (ss:ScholarshipSource {id: 'scholarship_test_temp'}) DELETE ss")
    except Exception as e:
        test['result'] = str(e)
        results['success'] = False
    results['tests'].append(test)

    # Update overall success
    results['success'] = all(t['passed'] for t in results['tests'])

    return results


def print_verification_report(results: dict) -> None:
    """Print a formatted verification report."""
    print("\n" + "=" * 60)
    print("FalkorDB Database Verification Report")
    print("=" * 60 + "\n")

    for test in results['tests']:
        status = "PASS" if test['passed'] else "FAIL"
        print(f"[{status}] {test['name']}")
        print(f"       {test['result']}")
        print()

    print("-" * 60)
    overall = "ALL TESTS PASSED" if results['success'] else "SOME TESTS FAILED"
    print(f"Overall: {overall}")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    import sys

    print("Initializing Student Ambassador FalkorDB database...")

    client = get_client()

    # Initialize database
    init_results = init_database(client, clear_existing=True, load_seed_data=True)

    print("\nInitialization Results:")
    print(f"  Success: {init_results['success']}")
    print(f"  Data cleared: {init_results['cleared']}")
    print(f"  Seed loaded: {init_results['seed_loaded']}")

    if init_results['errors']:
        print("\n  Errors:")
        for error in init_results['errors']:
            print(f"    - {error}")

    print("\n  Node counts:")
    for label, count in init_results['node_counts'].items():
        print(f"    {label}: {count}")

    print("\n  Relationship counts:")
    for rel_type, count in init_results['relationship_counts'].items():
        print(f"    {rel_type}: {count}")

    # Run verification
    print("\nRunning verification tests...")
    verify_results = verify_database(client)
    print_verification_report(verify_results)

    sys.exit(0 if verify_results['success'] else 1)
