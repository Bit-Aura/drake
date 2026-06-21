import pytest
from pathlib import Path
from src.cli.services.cluster import ClusterCLIService
from src.core.models import ContractA
from unittest.mock import patch

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "real_world_specs"

def test_real_world_specs_ingestion():
    # Verify the realistic files exist
    idrac_spec = FIXTURES_DIR / "idrac_redfish_openapi.json"
    ome_rest_spec = FIXTURES_DIR / "ome_rest_openapi.json"
    ome_graphql_spec = FIXTURES_DIR / "ome_schema.graphql"
    
    assert idrac_spec.exists(), "iDRAC spec not found"
    assert ome_rest_spec.exists(), "OME REST spec not found"
    assert ome_graphql_spec.exists(), "OME GraphQL spec not found"
    
    # Mock the graph and DB pipeline to only test the ingestion and merging layer
    with patch("src.cli.services.cluster.init_db_sync"), patch("src.cli.services.cluster.run_pipeline") as mock_run:
        service = ClusterCLIService()
        
        # Ingest the three realistic specs representing a cross-product environment
        result = service.run_clustering([idrac_spec, ome_rest_spec, ome_graphql_spec], explain=False)
        
        assert result["status"] == "success"
        
        mock_run.assert_called_once()
        merged_contract: ContractA = mock_run.call_args[0][0]
        
        # Verify the contract merged successfully
        # iDRAC endpoints: 3 (GET /System.Embedded.1, GET /DellAttributes, PATCH /DellAttributes, POST /SimpleUpdate)
        # Wait, idrac has: GET System, GET DellAttr, PATCH DellAttr, POST SimpleUpdate = 4 endpoints
        # OME REST endpoints: 4 (GET /Groups, POST /Groups, GET /Devices, GET /Alerts)
        # OME GraphQL endpoints: 5 queries/mutations
        
        assert merged_contract.total_endpoints > 0
        
        # Verify specific iDRAC signatures
        system_ep = next((ep for ep in merged_contract.endpoints if "/redfish/v1/Systems/System.Embedded.1" in ep.url), None)
        assert system_ep is not None
        assert system_ep.protocol == "REST"
        assert system_ep.method == "GET"
        
        update_ep = next((ep for ep in merged_contract.endpoints if "SimpleUpdate" in ep.url), None)
        assert update_ep is not None
        assert update_ep.method == "POST"
        
        # Verify specific OME REST signatures
        groups_ep = next((ep for ep in merged_contract.endpoints if "/api/GroupService/Groups" in ep.url and ep.method == "POST"), None)
        assert groups_ep is not None
        # Verify parameter parsing (the Name property should be required in request body)
        assert any(p.name == "body" for p in groups_ep.required_params), "Body should be required for POST Group"
        
        # Verify specific OME GraphQL signatures
        graphql_ep = next((ep for ep in merged_contract.endpoints if "DeviceService_GetDevices" in ep.url), None)
        assert graphql_ep is not None
        assert graphql_ep.protocol == "GraphQL"
        assert graphql_ep.method == "QUERY"
        
        discovery_ep = next((ep for ep in merged_contract.endpoints if "DeviceService_DiscoverDevice" in ep.url), None)
        assert discovery_ep is not None
        assert discovery_ep.protocol == "GraphQL"
        
        # Check source files are properly tagged
        sources = {ep.source_file for ep in merged_contract.endpoints}
        assert "idrac_redfish_openapi.json" in sources
        assert "ome_rest_openapi.json" in sources
        assert "ome_schema.graphql" in sources
