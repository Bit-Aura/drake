import os
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GENERATED_DIR = os.path.join(os.path.dirname(__file__), "generated")

TEST_TEMPLATE = """\
# AUTO-GENERATED TEST FILE
import pytest
import os
from unittest.mock import patch, MagicMock, call

from src.proxy.server import mcp
from src.proxy.executors.httpx_executor import _execution_cache, _cache_lock

@pytest.mark.asyncio
async def test_generated_workflow_{workflow_id}_execution():
    from src.proxy.server import load_approved_tools_from_db
    await load_approved_tools_from_db()
    with patch("httpx.AsyncClient.request") as mock_request:
        # Mock Response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {{"mocked": "success"}}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        # Use mock executor and clear cache
        with patch.dict(os.environ, {{"DELL_EXECUTOR_TYPE": "mock", "DELL_CACHE_TTL": "60"}}):
            async with _cache_lock:
                _execution_cache.clear()
            
            # Execute tool
            res = await mcp.call_tool("{system_name}", arguments={{{dummy_args}}})
            
            assert not getattr(res, "is_error", False)
            assert "success" in str(getattr(res, "content", res))
            
            # Validate execution sequence
            calls = mock_request.call_args_list
            assert len(calls) >= {num_network_calls}, f"Expected at least {num_network_calls} network calls, got {{len(calls)}}"
            
{assertions}
"""

def generate_tests_from_db(db_path: str = None):
    if not db_path:
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "governance.db")
        
    os.makedirs(GENERATED_DIR, exist_ok=True)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Query approved workflows
        workflows = conn.execute("SELECT id, system_name FROM workflows WHERE approved = 1").fetchall()
        
        logger.info(f"Found {len(workflows)} approved workflows for test generation.")
        
        for wf in workflows:
            wf_id = wf["id"]
            system_name = wf["system_name"]
            
            steps = conn.execute(
                "SELECT method, url, required_params FROM endpoint_steps WHERE workflow_id = ? ORDER BY step_order ASC", 
                (wf_id,)
            ).fetchall()
            
            # Build assertions
            assertions = []
            num_network_calls = 0
            
            # Handle caching checks (GET requests with identical URL & params in the same workflow)
            seen_get_requests = set()
            
            for i, step in enumerate(steps):
                method = step["method"].upper()
                url = step["url"]
                
                # Check cache idempotency for GETs
                cache_key = f"{method}_{url}"
                if method == "GET" and cache_key in seen_get_requests:
                    # This should be cached, no network call added
                    assertions.append(f"            # Step {i+1} is a cached GET to {url}. No new network call expected.")
                else:
                    if method == "GET":
                        seen_get_requests.add(cache_key)
                        
                    assertions.append(f"            # Assert Step {i+1} Network Call")
                    assertions.append(f"            assert workflow_calls[{num_network_calls}].args[0] == '{method}'")
                    assertions.append(f"            assert '{url}' in workflow_calls[{num_network_calls}].args[1]")
                    assertions.append(f"            assert 'Authorization' in workflow_calls[{num_network_calls}].kwargs.get('headers', {{}})")
                    num_network_calls += 1
                    
            if num_network_calls > 0:
                assertions.insert(0, f"            workflow_calls = calls[-{num_network_calls}:]")
            else:
                assertions.insert(0, "            workflow_calls = []")

            # Render template
            content = TEST_TEMPLATE.format(
                workflow_id=wf_id.replace("-", "_"),
                system_name=system_name,
                dummy_args="",  # No args for basic execution
                num_network_calls=num_network_calls,
                assertions="\n".join(assertions)
            )
            
            out_file = os.path.join(GENERATED_DIR, f"test_wf_{wf_id.replace('-', '_')}.py")
            with open(out_file, "w") as f:
                f.write(content)
                
            logger.info(f"Generated test file: {out_file}")
            
    except Exception as e:
        logger.error(f"Failed to generate dynamic tests: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    generate_tests_from_db()
