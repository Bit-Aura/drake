import pytest
import os
import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from src.proxy.server import app, mcp, load_approved_tools_from_db
from src.core.database import init_db_sync, get_db_connection
from src.core.exceptions import DellProxyExecutionError
from src.core.compatibility.orchestrator import CompatibilityPolicyViolation
from fastmcp.exceptions import NotFoundError

@pytest.fixture(autouse=True)
def setup_lifecycle_db():
    init_db_sync()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # 1. Happy Path (Approved)
        conn.execute(
            """
            INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_happy", "wf_happy_path", "Happy Path", "LOW", 1, 0.9, "Desc", 1)
        )
        conn.execute(
            """
            INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_happy", 1, "MockStep1", "GET", "/api/happy", '[]', "{}", now)
        )
        
        # 2. Pending State
        conn.execute(
            """
            INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_pending", "wf_pending_state", "Pending State", "LOW", 1, 0.9, "Desc", 0)
        )
        conn.execute(
            """
            INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_pending", 1, "MockStep2", "GET", "/api/pending", '[]', "{}", now)
        )

        # 3. Policy Violation (DELETE)
        conn.execute(
            """
            INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_policy", "wf_policy_block", "Policy Block", "HIGH", 1, 0.9, "Desc", 1)
        )
        conn.execute(
            """
            INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_policy", 1, "MockStep3", "DELETE", "/api/system/reset", '[]', "{}", now)
        )

        # 4. Parameter Validation
        conn.execute(
            """
            INSERT INTO workflows (id, system_name, display_name, risk_level, cluster_size, confidence, generated_description, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_param", "wf_param_validation", "Param Validation", "LOW", 1, 0.9, "Desc", 1)
        )
        conn.execute(
            """
            INSERT INTO endpoint_steps (workflow_id, step_order, operation_id, method, url, required_params, variable_bindings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("wf_param", 1, "MockStep4", "GET", "/api/param", '[{"name": "target_ip", "required": true}]', "{}", now)
        )

        conn.commit()

    # Clear previously registered dynamic tools in fastmcp
    if hasattr(mcp, "_local_provider") and hasattr(mcp._local_provider, "_tools"):
        for tool_name in list(mcp._local_provider._tools.keys()):
            if not tool_name.startswith("expand_") and not tool_name.startswith("collapse_"):
                mcp._local_provider.remove_tool(tool_name)

@pytest.fixture
async def loaded_mcp():
    await load_approved_tools_from_db()
    return mcp

@pytest.mark.asyncio
async def test_1_happy_path_approved_workflow(loaded_mcp):
    with patch("httpx.AsyncClient.request") as mock_request:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response
        
        with patch.dict(os.environ, {"DELL_EXECUTOR_TYPE": "mock", "DELL_COMPATIBILITY_POLICY": "DISABLED"}):
            # FastMCP call_tool returns a list of text objects typically, but our dynamic tool returns dict
            # Actually call_tool returns a list of TextContent/ImageContent objects.
            res = await loaded_mcp.call_tool("wf_happy_path", arguments={})
            
            assert res is not None
            mock_request.assert_called_once()
            assert mock_request.call_args[0][0] == "GET"
            assert "/api/happy" in mock_request.call_args[0][1]

@pytest.mark.asyncio
async def test_2_governance_block_pending_state(loaded_mcp):
    with patch("httpx.AsyncClient.request") as mock_request:
        with pytest.raises(NotFoundError):
            await loaded_mcp.call_tool("wf_pending_state", arguments={})
        
        mock_request.assert_not_called()

@pytest.mark.asyncio
async def test_3_policy_violation_security_block(loaded_mcp):
    from src.core.compatibility.models import CompatibilityStatus
    
    with patch("src.core.compatibility.engine.CompatibilityEngine.validate_workflow") as mock_engine:
        # Engine validates and returns blocked status
        mock_report = MagicMock()
        mock_report.status = CompatibilityStatus.BLOCK
        mock_report.confidence_score = 100
        mock_report.findings = []
        mock_report.violations = []
        mock_report.id = "mock_report_123"
        mock_report.compatibility_score = 0
        mock_report.risk_score = 100
        mock_report.blast_radius = "HIGH"
        mock_report.timestamp = datetime.datetime.now(datetime.timezone.utc)
        mock_engine.return_value = mock_report
        
        with patch("src.core.compatibility.orchestrator.CompatibilityRepository.save_report", new_callable=AsyncMock):
            with patch("httpx.AsyncClient.request") as mock_request:
                with patch.dict(os.environ, {"DELL_EXECUTOR_TYPE": "mock", "DELL_COMPATIBILITY_POLICY": "STRICT"}):
                    from fastmcp.exceptions import ToolError
                    with pytest.raises(ToolError) as exc:
                        await loaded_mcp.call_tool("wf_policy_block", arguments={})
                    
                    assert "STRICT Policy blocked execution" in str(exc.value)

@pytest.mark.asyncio
async def test_4_parameter_validation_block(loaded_mcp):
    with patch("httpx.AsyncClient.request") as mock_request:
        # Pydantic or TypeError missing required arg 'target_ip'
        with pytest.raises(Exception) as exc:
            await loaded_mcp.call_tool("wf_param_validation", arguments={})
            
        assert exc is not None
        mock_request.assert_not_called()

@pytest.mark.asyncio
async def test_5_downstream_failure_handling(loaded_mcp):
    import httpx
    from src.proxy.executors.httpx_executor import _execution_cache
    _execution_cache.clear()
    with patch("httpx.AsyncClient.request") as mock_request:
        # Simulate 500 error from downstream mock API
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        mock_request.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response
        )
        
        with patch.dict(os.environ, {"DELL_EXECUTOR_TYPE": "mock", "DELL_COMPATIBILITY_POLICY": "DISABLED"}):
            result = await loaded_mcp.call_tool("wf_happy_path", arguments={})
            
            result_str = str(result)
            assert "partial_failure" in result_str
            assert "Internal Server Error" in result_str or "Workflow step execution failed" in result_str or "after exhausting retries" in result_str
            mock_request.assert_called()
