# AUTO-GENERATED TEST FILE
import pytest
import os
from unittest.mock import patch, MagicMock, call

from src.proxy.server import mcp
from src.proxy.executors.httpx_executor import _execution_cache, _cache_lock

@pytest.mark.asyncio
async def test_generated_workflow_wf_bootstrap_999_execution():
    from src.proxy.server import load_approved_tools_from_db
    await load_approved_tools_from_db()
    with patch("httpx.AsyncClient.request") as mock_request:
        # Mock Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mocked": "success"}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        # Use mock executor and clear cache
        with patch.dict(os.environ, {"DELL_EXECUTOR_TYPE": "mock", "DELL_CACHE_TTL": "60"}):
            async with _cache_lock:
                _execution_cache.clear()
            
            # Execute tool
            res = await mcp.call_tool("check_server_health_update", arguments={})
            
            assert res.get("status") == "success"
            
            # Validate exact sequence of execution
            calls = mock_request.call_args_list
            assert len(calls) == 2, f"Expected 2 network calls, got {len(calls)}"
            
            # Assert Step 1 Network Call\n            assert calls[0].args[0] == 'GET'\n            assert '/redfish/v1/Chassis/1' in calls[0].args[1]\n            assert 'Authorization' in calls[0].kwargs.get('headers', {})\n            # Assert Step 2 Network Call\n            assert calls[1].args[0] == 'POST'\n            assert '/redfish/v1/Chassis/1/Actions/Chassis.Reset' in calls[1].args[1]\n            assert 'Authorization' in calls[1].kwargs.get('headers', {})\n            # Step 3 is a cached GET to /redfish/v1/Chassis/1. No new network call expected.
