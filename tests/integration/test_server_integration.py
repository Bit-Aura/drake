import pytest
import asyncio
from fastapi.testclient import TestClient
from drake.proxy.server import app, expand_workflow, expanded_tools_registry, mcp
from drake.core.database import async_session, init_db, init_db_sync, Workflow, EndpointStep

from datetime import datetime

client = TestClient(app)

def test_cors_headers() -> None:
    """
    Test that the CORS middleware allows explicitly configured origins 
    and handles credentials correctly, without using illegal wildcards.
    """
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_expand_workflow_race_condition() -> None:
    """
    Test that the async lock correctly prevents TOCTOU race conditions
    when multiple concurrent requests try to expand the same workflow.
    """
    init_db_sync()
    await init_db()
    
    wf_id = "test_race_wf"
    
    async with async_session() as session:
        # Check if exists to prevent unique constraint failures
        existing = await session.get(Workflow, wf_id)
        if not existing:
            wf = Workflow(
                id=wf_id,
                system_name="test_race_wf_system",
                display_name="Test Race WF",
                risk_level="low",
                cluster_size=1,
                confidence=1.0,
                generated_description="test",
                community_id="c_123",
                approved=1,
                execution_count=0
            )
            session.add(wf)
            
            step = EndpointStep(
                operation_id="op_test_race",
                method="GET",
                url="/test/race",
                workflow_id=wf_id,
                step_order=1,
                required_params="[]",
                request_schema="{}",
                created_at=datetime.utcnow()
            )
            session.add(step)
            await session.commit()
    
    # Clear registry if present from previous runs
    if wf_id in expanded_tools_registry:
        del expanded_tools_registry[wf_id]
        
    initial_tools_count = len(await mcp.list_tools())
    
    # Fire 20 concurrent requests to expand_workflow
    results = await asyncio.gather(*(expand_workflow(wf_id) for _ in range(20)))
    
    # One should succeed expanding, others should return "Already expanded"
    expanded_count = sum(1 for r in results if r.get("status") == "success" and "Successfully expanded" in r.get("message", ""))
    ignored_count = sum(1 for r in results if r.get("status") == "success" and "Already expanded" in r.get("message", ""))
    
    assert expanded_count == 1, "Race condition detected! Multiple tasks bypassed the lock and expanded the workflow."
    assert ignored_count == 19, "Other concurrent tasks did not correctly detect already expanded state."
    
    final_tools_count = len(await mcp.list_tools())
    assert final_tools_count == initial_tools_count + 1, "Tools should only be added exactly once."
    
    # Cleanup
    del expanded_tools_registry[wf_id]
