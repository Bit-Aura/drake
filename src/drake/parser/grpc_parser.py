import logging
from pathlib import Path
from drake.core.models import ContractA, EndpointContract

logger = logging.getLogger(__name__)

class gRPCParser:  # noqa: E302
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def parse_and_flatten(self) -> ContractA:
        logger.info(f"Parsing gRPC protobuf from {self.file_path}")
        endpoints = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Simplistic parsing for 'rpc Method(Input) returns (Output)'
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("rpc "):
                    parts = line.split("(")
                    name = parts[0].replace("rpc ", "").strip()
                    endpoints.append(
                        EndpointContract(
                            operation_id=f"GRPC_{name}",
                            method="RPC",
                            url=f"/{name}",
                            required_params=[],
                            tags=["gRPC"],
                            summary=f"gRPC RPC {name}",
                            protocol="gRPC",
                            source_file=self.file_path.name
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to parse gRPC: {e}")

        if not endpoints:
            endpoints.append(
                EndpointContract(
                    operation_id="GRPC_mock",
                    method="RPC",
                    url="/grpc_mock",
                    protocol="gRPC",
                    source_file=self.file_path.name
                )
            )

        return ContractA(
            spec_title=f"gRPC: {self.file_path.name}",
            spec_version="1.0",
            openapi_version="N/A",
            source_file=self.file_path.name,
            total_endpoints=len(endpoints),
            endpoints=endpoints
        )
