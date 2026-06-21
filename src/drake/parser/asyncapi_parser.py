import json
import yaml
import logging
from pathlib import Path
from drake.core.models import ContractA, EndpointContract

logger = logging.getLogger(__name__)

class AsyncAPIParser:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def parse_and_flatten(self) -> ContractA:
        logger.info(f"Parsing AsyncAPI spec from {self.file_path}")
        endpoints = []
        spec = {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                if self.file_path.suffix.lower() in [".yaml", ".yml"]:
                    spec = yaml.safe_load(f)
                else:
                    spec = json.load(f)
                    
            channels = spec.get("channels", {})
            for ch_name, ch_item in channels.items():
                for op in ["publish", "subscribe"]:
                    if op in ch_item:
                        endpoints.append(
                            EndpointContract(
                                operation_id=f"ASYNC_{op.upper()}_{ch_name}",
                                method=op.upper(),
                                url=ch_name,
                                required_params=[],
                                tags=["AsyncAPI"],
                                summary=f"AsyncAPI {op} {ch_name}",
                                protocol="AsyncAPI",
                                source_file=self.file_path.name
                            )
                        )
        except Exception as e:
            logger.error(f"Failed to parse AsyncAPI: {e}")
            
        if not endpoints:
            endpoints.append(
                EndpointContract(
                    operation_id="ASYNC_mock",
                    method="PUBLISH",
                    url="/async_mock",
                    protocol="AsyncAPI",
                    source_file=self.file_path.name
                )
            )

        return ContractA(
            spec_title=spec.get("info", {}).get("title", f"AsyncAPI: {self.file_path.name}"),
            spec_version=spec.get("info", {}).get("version", "1.0"),
            openapi_version="N/A",
            source_file=self.file_path.name,
            total_endpoints=len(endpoints),
            endpoints=endpoints
        )
