import pytest
from httpx import AsyncClient, ASGITransport
import json
from unittest.mock import patch, MagicMock, AsyncMock

from src.proxy.api import app
from src.core.database import init_db_sync, get_db_connection
from src.core.models import WorkflowMapping, WorkflowStep


@pytest.fixture(autouse=True)
def setup_db():
    init_db_sync()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM endpoint_steps")
        conn.execute("DELETE FROM endpoints")
        conn.execute(
            """
            INSERT INTO endpoints (operation_id, method, url, required_params, community_id, request_schema, response_schema)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("mock_operation_id", "GET", "/redfish/v1/Systems/System.Embedded.1", "[]", None, None, None)
        )
        conn.commit()


@pytest.mark.asyncio
async def test_generate_from_nl_success():
    mock_workflow = WorkflowMapping(
        name="server_health_and_firmware_update",
        description="Check server health and update firmware.",
        steps=[
            WorkflowStep(
                target_path="/redfish/v1/Systems/System.Embedded.1",
                method="GET",
                protocol="REST",
                input_mapping={}
            )
        ]
    )
    
    # We mock the instructor client
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_workflow)
    
    with patch("src.ai_clustering.nl_compiler.instructor.from_openai", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/workflows/generate-from-nl",
                headers={"X-API-Key": "default_dev_key"},
                json={"prompt": "Check server health and then update firmware if health is good"}
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "workflow_id" in data
        assert data["workflow"]["name"] == "server_health_and_firmware_update"
        assert len(data["workflow"]["steps"]) == 1
        
        wf_id = data["workflow_id"]
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM workflows WHERE id = ?", (wf_id,))
            wf = cursor.fetchone()
            assert wf is not None
            assert wf["approved"] == 0
            assert wf["system_name"] == "server_health_and_firmware_update"
            
            cursor = conn.execute("SELECT * FROM endpoint_steps WHERE workflow_id = ?", (wf_id,))
            steps = cursor.fetchall()
            assert len(steps) == 1
            assert steps[0]["url"] == "/redfish/v1/Systems/System.Embedded.1"

@pytest.mark.asyncio
async def test_generate_from_nl_failure():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=ValueError("LLM Error"))
    
    with patch("src.ai_clustering.nl_compiler.instructor.from_openai", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/workflows/generate-from-nl",
                headers={"X-API-Key": "default_dev_key"},
                json={"prompt": "Fail prompt"}
            )
            
        assert response.status_code == 500
        assert "LLM Error" in response.json()["detail"]
