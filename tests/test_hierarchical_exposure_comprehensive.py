import pytest
import pytest_asyncio
import os
import hashlib
from unittest.mock import patch, AsyncMock

from src.proxy.server import mcp, expanded_tools_registry, expand_workflow
from src.core.database import init_db_sync, get_db_connection

@pytest_asyncio.fixture(autouse=True)
async def setup_and_teardown_db():
    init_db_sync()
    
    # Setup DB
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM endpoints")
        
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Workflow A with 3 steps
        wf_a = "wf_A_123"
        conn.execute(
            """
            INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (wf_a, "workflow_A", "Workflow A", "LOW", 3, 0.9, "Desc A", 1)
        )
        
        for i, op in enumerate(["Op1", "Op2", "Op3"], start=1):
            conn.execute(
                """
                INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (wf_a, i, op, "GET", f"/redfish/v1/A/{i}", '[{"name": "param_a"}]', "{}", now)
            )
            
        # Workflow B with 2 steps
        wf_b = "wf_B_456"
        conn.execute(
            """
            INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (wf_b, "workflow_B", "Workflow B", "LOW", 2, 0.9, "Desc B", 1)
        )
        
        for i, op in enumerate(["OpB1", "OpB2"], start=1):
            conn.execute(
                """
                INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (wf_b, i, op, "POST", f"/redfish/v1/B/{i}", '[{"name": "param_b"}]', "{}", now)
            )
            
        conn.commit()
    
    # Clear memory registry
    expanded_tools_registry.clear()
    
    # Clear fastmcp registry
    if hasattr(mcp, "_local_provider") and hasattr(mcp._local_provider, "_tools"):
        for tool_name in list(mcp._local_provider._tools.keys()):
            if tool_name.startswith("exec_step_"):
                mcp._local_provider.remove_tool(tool_name)

    yield
    
    # Teardown logic
    expanded_tools_registry.clear()
    if hasattr(mcp, "_local_provider") and hasattr(mcp._local_provider, "_tools"):
        for tool_name in list(mcp._local_provider._tools.keys()):
            if tool_name.startswith("exec_step_"):
                mcp._local_provider.remove_tool(tool_name)

@pytest.mark.asyncio
async def test_input_validation_rejection():
    # Attempt to expand non-existent workflow
    res = await expand_workflow("invalid_wf_999")
    
    assert res.get("error") is not None
    assert "not found" in res.get("error").lower()
    assert "invalid_wf_999" in res.get("error")

@pytest.mark.asyncio
async def test_dynamic_registration_assertion():
    # Expand Workflow A which has 3 steps
    res = await expand_workflow("wf_A_123")
    assert res.get("status") == "success"
    
    registered = res.get("registered_tools", [])
    assert len(registered) == 3
    
    # Ensure all 3 are in the registry
    tools_list = await mcp.list_tools()
    tool_names = [t.name for t in tools_list]
    
    for t_name in registered:
        assert t_name in tool_names

@pytest.mark.asyncio
async def test_isolation_and_relation_mapping():
    # Expand A
    res_a = await expand_workflow("wf_A_123")
    assert res_a.get("status") == "success"
    
    registered_a = res_a.get("registered_tools", [])
    
    # Ensure B is NOT expanded
    safe_hash_b = hashlib.md5("wf_B_456".encode()).hexdigest()[:8]
    b_tool_prefix = f"exec_step_{safe_hash_b}"
    
    tools_list = await mcp.list_tools()
    tool_names = [t.name for t in tools_list]
    
    for t_name in tool_names:
        assert not t_name.startswith(b_tool_prefix)
        
    for t_name in registered_a:
        assert t_name in tool_names

@pytest.mark.asyncio
async def test_end_to_end_execution():
    # Expand Workflow A
    with patch.dict(os.environ, {"DELL_EXECUTOR_TYPE": "mock"}):
        res = await expand_workflow("wf_A_123")
        assert res.get("status") == "success"
        
        registered = res.get("registered_tools", [])
        assert len(registered) == 3
        
        target_tool = registered[0] # Should be Op1
        
        # Mock executor
        with patch("src.proxy.executors.httpx_executor.MockExecutor.execute_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"status": "mocked_success"}
            
            # Execute dynamically registered tool
            await mcp.call_tool(target_tool, arguments={"param_a": "value_a"})
            
            mock_execute.assert_called_once()
            
            args, kwargs = mock_execute.call_args
            t_step = args[0]
            passed_kwargs = args[1]
            
            assert t_step.operation_id == "Op1"
            assert t_step.method == "GET"
            assert t_step.url == "/redfish/v1/A/1"
            assert passed_kwargs == {"param_a": "value_a"}
