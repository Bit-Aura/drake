"""
Dell MCP — Phase 1 Parser: Full Test Suite
==========================================
Tests for the OpenAPIParser class.
"""

from pathlib import Path
import pytest

from drake.core.models import ContractA, EndpointContract
from drake.parser.openapi_parser import OpenAPIParser


class TestOpenAPIParser:
    def test_loads_valid_yaml(self, mini_spec_path: Path) -> None:
        parser = OpenAPIParser(mini_spec_path)
        raw = parser.load_spec()
        assert isinstance(raw, dict)
        assert "openapi" in raw
        assert "paths" in raw

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        ghost = tmp_path / "does_not_exist.yaml"
        parser = OpenAPIParser(ghost)
        with pytest.raises(FileNotFoundError):
            parser.load_spec()

    def test_parses_endpoints_correctly(self, mini_spec_path: Path) -> None:
        parser = OpenAPIParser(mini_spec_path)
        contract = parser.parse_and_flatten()
        assert isinstance(contract, ContractA)
        assert contract.total_endpoints > 0
        assert contract.total_endpoints == len(contract.endpoints)

        endpoints = contract.endpoints
        for ep in endpoints:
            assert isinstance(ep, EndpointContract)
            assert ep.operation_id

        # Verify path parameter is parsed correctly
        get_account = next(
            (
                ep
                for ep in endpoints
                if ep.url == "/redfish/v1/AccountService/Accounts/{ManagerAccountId}"
                and ep.method == "GET"
            ),
            None,
        )
        assert get_account is not None
        param_names = [p.name for p in get_account.required_params]
        assert "ManagerAccountId" in param_names

    def test_exports_contract_a(self, mini_spec_path: Path, tmp_path: Path) -> None:
        parser = OpenAPIParser(mini_spec_path)
        output = tmp_path / "contract_a.json"
        parser.export_contract_a(output)

        assert output.exists()
        raw_json = output.read_text(encoding="utf-8")
        reloaded = ContractA.model_validate_json(raw_json)
        assert reloaded.total_endpoints > 0
        assert reloaded.total_endpoints == len(reloaded.endpoints)
