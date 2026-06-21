import pytest
import os
import sqlite3
import tempfile
import subprocess
from tests.dynamic_test_generator import generate_tests_from_db, GENERATED_DIR

@pytest.fixture
def dummy_db():
    fd, path = tempfile.mkstemp()
    
    conn = sqlite3.connect(path)
    
    from sqlalchemy import create_engine
    from src.core.database import Base
    
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    
    conn.execute("""
    CREATE TABLE audit_events (
        id TEXT PRIMARY KEY,
        timestamp TEXT,
        event_type TEXT,
        status TEXT,
        description TEXT,
        workflow_name TEXT,
        actor TEXT,
        hash TEXT,
        previous_hash TEXT,
        metadata TEXT
    )
    """)
    
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Insert 1 complex approved workflow
    wf_id = "wf_bootstrap_999"
    conn.execute(
        """
        INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (wf_id, "check_server_health_update", "Check Health & Update", "HIGH", 3, 0.95, "Test WF", 1)
    )
    
    # Step 1: GET Chassis (Should trigger network)
    conn.execute(
        "INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (wf_id, 1, "get_chassis", "GET", "/redfish/v1/Chassis/1", "[]", now)
    )
    
    # Step 2: POST Reset (Should trigger network)
    conn.execute(
        "INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (wf_id, 2, "reset_chassis", "POST", "/redfish/v1/Chassis/1/Actions/Chassis.Reset", "[]", now)
    )
    
    # Step 3: GET Chassis again (Should hit CACHE, NOT network)
    conn.execute(
        "INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (wf_id, 3, "get_chassis_again", "GET", "/redfish/v1/Chassis/1", "[]", now)
    )
    
    conn.commit()
    conn.close()
    engine.dispose()

    yield path
    
    os.close(fd)
    os.remove(path)

def test_dynamic_test_generator_bootstrap(dummy_db):
    os.environ["DELL_TEST_DB_PATH"] = dummy_db
    # 1. Run generator
    generate_tests_from_db(dummy_db)
    
    # 2. Assert generated file exists
    expected_file = os.path.join(GENERATED_DIR, "test_wf_wf_bootstrap_999.py")
    assert os.path.exists(expected_file), f"Generated file {expected_file} does not exist"
    
    # 3. Read content and verify assertions structure
    with open(expected_file, "r") as f:
        content = f.read()
        
    assert "async def test_generated_workflow_wf_bootstrap_999_execution" in content
    assert "assert len(calls) >= 2" in content  # 3 steps, but 1 is cached
    assert "assert workflow_calls[0].args[0] == 'GET'" in content
    assert "assert workflow_calls[1].args[0] == 'POST'" in content
    assert "No new network call expected" in content
    
    # 4. Cleanup generated file so it doesn't affect the global pytest collection
    try:
        os.remove(expected_file)
    except Exception:
        pass
