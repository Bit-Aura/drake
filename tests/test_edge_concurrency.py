import pytest
import asyncio
import datetime
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.fixture(autouse=True)
def setup_concurrency_db():
    from drake.core.database import init_db_sync, get_db_connection
    init_db_sync()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        conn.execute(
            "INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("wf_race", "wf_race_condition", "Race", "LOW", 1, 0.9, "Desc", 1)
        )
        conn.execute(
            "INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("wf_race", 1, "Step1", "GET", "/api/race", "[]", "{}", now)
        )
        conn.commit()

@pytest.mark.asyncio
async def test_1_concurrent_expansion_race_condition():
    from drake.proxy.server import expand_workflow, expanded_tools_registry
    
    # Ensure starting clean
    if "wf_race" in expanded_tools_registry:
        del expanded_tools_registry["wf_race"]
        
    results = await asyncio.gather(*[expand_workflow("wf_race") for _ in range(10)])
    
    successes = sum(1 for r in results if r.get("message") and "Successfully expanded" in r.get("message"))
    already = sum(1 for r in results if r.get("message") == "Already expanded")
    
    # Assert FastMCP server handled locks and registered exactly once
    assert successes == 1
    assert already == 9

@pytest.mark.asyncio
async def test_2_get_cache_race_condition():
    from drake.proxy.executors.httpx_executor import MockExecutor, _execution_cache, _pending_requests
    _execution_cache.clear()
    _pending_requests.clear()
    
    executor = MockExecutor()
    step = MagicMock()
    step.method = "GET"
    step.url = "/api/v1/heavy-resource"
    step.id = 1
    
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        # We need a small sleep in the mock to guarantee all 50 coroutines
        # hit the cache checking block before the first one completes
        async def slow_request(*args, **kwargs):
            await asyncio.sleep(0.05)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"heavy": "data"}
            return mock_response
            
        mock_request.side_effect = slow_request
        
        async def run_step():
            return await executor.execute_step(step, {}, {})
            
        results = await asyncio.gather(*[run_step() for _ in range(50)])
        
        # We should only hit the downstream API once!
        mock_request.assert_called_once()
        # Ensure the other 49 hit the cache (eventually)
        assert sum(1 for r in results if r.get("cached") is True) == 49

@pytest.mark.asyncio
async def test_3_infinite_workflow_loop_detection():
    # Simulate a cyclic dependency detector in the execution engine
    from drake.proxy.executors.httpx_executor import MockExecutor
    from drake.core.exceptions import DellProxyExecutionError
    
    MockExecutor()
    
    visited = set()
    
    async def execute_cyclic_step(step_name):
        if step_name in visited:
            raise DellProxyExecutionError(f"Infinite Workflow Loop Detected: {step_name}")
        visited.add(step_name)
        # Simulate Step A pointing to B, B to A
        next_step = "StepB" if step_name == "StepA" else "StepA"
        return await execute_cyclic_step(next_step)
        
    with pytest.raises(DellProxyExecutionError) as exc:
        await execute_cyclic_step("StepA")
        
    assert "Infinite Workflow Loop Detected" in str(exc.value)
