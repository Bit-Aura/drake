import pytest
from unittest.mock import patch, AsyncMock

from src.proxy.server import mcp, expanded_tools_registry
from src.core.database import init_db_sync, get_db_connection

@pytest.fixture(autouse=True)
def setup_db():
    init_db_sync()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM endpoints")
        
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Create mock workflow
        wf_id = "test_wf_123"
        conn.execute(
            """
            INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (wf_id, "test_workflow", "Test Workflow", "LOW", 1, 0.9, "Desc", 1)
        )
        
        # Create mock step
        conn.execute(
            """
            INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (wf_id, 1, "MockStep", "GET", "/redfish/v1/Systems/1", '[{"name": "force"}]', "{}", now)
        )
        conn.commit()
    
    # clear registry
    expanded_tools_registry.clear()
    
    # We should also ensure mcp tools are clean, but FastMCP local_provider might carry state.
    # To be safe, we can manually remove dynamic tools if possible
    if hasattr(mcp, "_local_provider") and hasattr(mcp._local_provider, "_tools"):
        for tool_name in list(mcp._local_provider._tools.keys()):
            if tool_name.startswith("exec_step_"):
                mcp._local_provider.remove_tool(tool_name)

@pytest.mark.asyncio
async def test_hierarchical_expansion_execution_and_cleanup():
    # 1. Test Initial State
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "expand_workflow" in tool_names
    assert "collapse_workflow" in tool_names
    
    import hashlib
    safe_hash = hashlib.sha256("test_wf_123".encode()).hexdigest()[:8]
    dynamic_tool_name = f"exec_step_{safe_hash}_1_MockStep"
    # Wait, the tool name is sliced to 64 chars, and sub replaces non-alphanumeric.
    import re
    dynamic_tool_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dynamic_tool_name)[:64]
    
    assert dynamic_tool_name not in tool_names

    # 2. Test Expansion
    # Call the tool function directly for testing
    from src.proxy.server import expand_workflow, collapse_workflow
    
    import os
    with patch.dict(os.environ, {"DELL_EXECUTOR_TYPE": "mock"}):
        expand_result = await expand_workflow("test_wf_123")
        assert expand_result["status"] == "success"
        assert dynamic_tool_name in expand_result["registered_tools"]
        
        # Verify it was added to MCP
        tools_after = await mcp.list_tools()
        tool_names_after = [t.name for t in tools_after]
        assert dynamic_tool_name in tool_names_after
        
        # 2.5 Test Idempotency
        expand_result_2 = await expand_workflow("test_wf_123")
        assert expand_result_2["status"] == "success"
        assert expand_result_2["message"] == "Already expanded"
        assert dynamic_tool_name in expand_result_2["registered_tools"]
    
        # 3. Test Execution
        # Mock the execute_step of MockExecutor
        with patch("src.proxy.executors.httpx_executor.MockExecutor.execute_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"status": "mocked_success"}
            
            # We simulate the MCP calling it
            await mcp.call_tool(dynamic_tool_name, arguments={"force": "true"})
            
            mock_execute.assert_called_once()
            # Ensure it passed kwargs
            args, kwargs = mock_execute.call_args
            assert args[1] == {"force": "true"}

    # 4. Test Cleanup
    collapse_result = await collapse_workflow("test_wf_123")
    assert collapse_result["status"] == "success"
    assert dynamic_tool_name in collapse_result["removed_tools"]
    
    # Verify it was removed from MCP
    tools_final = await mcp.list_tools()
    tool_names_final = [t.name for t in tools_final]
    assert dynamic_tool_name not in tool_names_final
    
    # Double check collapse on unexpanded
    collapse_result2 = await collapse_workflow("test_wf_123")
    assert collapse_result2["status"] == "ignored"
