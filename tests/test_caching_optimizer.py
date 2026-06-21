import pytest
import asyncio
import httpx
import time
import os
from unittest.mock import patch, MagicMock

from src.proxy.executors.httpx_executor import HTTPXExecutorBase, _execution_cache, _cache_lock
from src.core.exceptions import DellProxyExecutionError

class MockStep:
    def __init__(self, id, method, url, required_params=None):
        self.id = id
        self.method = method
        self.url = url
        self.required_params = required_params

@pytest.fixture(autouse=True)
async def clear_cache():
    async with _cache_lock:
        _execution_cache.clear()
    yield
    async with _cache_lock:
        _execution_cache.clear()

@pytest.mark.asyncio
async def test_cache_hit_optimization():
    executor = HTTPXExecutorBase(base_url="http://mock-server.local")
    step = MockStep(id="step_1", method="GET", url="/redfish/v1/Systems")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok", "system": "R740"}
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient.request") as mock_request:
        mock_request.return_value = mock_response
        
        # First execution (Cache Miss -> Network)
        res1 = await executor.execute_step(step, {}, {})
        assert res1["status_code"] == 200
        assert res1.get("cached") is None
        assert mock_request.call_count == 1
        
        # Second execution (Cache Hit -> No Network)
        res2 = await executor.execute_step(step, {}, {})
        assert res2["status_code"] == 200
        assert res2.get("cached") is True
        assert mock_request.call_count == 1  # Still 1, meaning network was bypassed

@pytest.mark.asyncio
async def test_cache_expiry_ttl():
    executor = HTTPXExecutorBase(base_url="http://mock-server.local")
    step = MockStep(id="step_2", method="GET", url="/redfish/v1/Chassis")
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"chassis": "Enclosure"}
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient.request") as mock_request:
        mock_request.return_value = mock_response
        
        # Override TTL to 1 second
        with patch.dict(os.environ, {"DELL_CACHE_TTL": "1"}):
            # First execution
            await executor.execute_step(step, {}, {})
            assert mock_request.call_count == 1
            
            # Second execution immediately (Cache hit)
            res2 = await executor.execute_step(step, {}, {})
            assert res2.get("cached") is True
            assert mock_request.call_count == 1
            
            # Sleep past TTL
            time.sleep(1.1)
            
            # Third execution (Cache Expired -> Network)
            res3 = await executor.execute_step(step, {}, {})
            assert res3.get("cached") is None
            assert mock_request.call_count == 2

@pytest.mark.asyncio
async def test_cache_bypass_for_mutations():
    executor = HTTPXExecutorBase(base_url="http://mock-server.local")
    step = MockStep(id="step_3", method="POST", url="/redfish/v1/Systems/1/Actions/ComputerSystem.Reset")
    
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.json.side_effect = ValueError("No content")
    mock_response.text = ""
    mock_response.raise_for_status = MagicMock()
    
    with patch("httpx.AsyncClient.request") as mock_request:
        mock_request.return_value = mock_response
        
        # First POST
        res1 = await executor.execute_step(step, {"ResetType": "ForceRestart"}, {})
        assert res1["status_code"] == 204
        assert res1.get("cached") is None
        assert mock_request.call_count == 1
        
        # Second POST (Identical)
        res2 = await executor.execute_step(step, {"ResetType": "ForceRestart"}, {})
        assert res2["status_code"] == 204
        assert res2.get("cached") is None
        assert mock_request.call_count == 2  # Must bypass cache

@pytest.mark.asyncio
async def test_error_responses_not_cached():
    executor = HTTPXExecutorBase(base_url="http://mock-server.local")
    step = MockStep(id="step_4", method="GET", url="/redfish/v1/Missing")
    
    # Setup mock to raise HTTPStatusError
    request = httpx.Request("GET", "http://mock-server.local/redfish/v1/Missing")
    response = httpx.Response(404, request=request)
    
    with patch("httpx.AsyncClient.request") as mock_request:
        mock_request.return_value = response
        
        # First execution fails with 404 (raises DellProxyExecutionError inside except block)
        with pytest.raises(DellProxyExecutionError):
            await executor.execute_step(step, {}, {})
            
        assert mock_request.call_count == 1
        
        # Second execution should hit the network again (no caching of 404)
        with pytest.raises(DellProxyExecutionError):
            await executor.execute_step(step, {}, {})
            
        assert mock_request.call_count == 2
