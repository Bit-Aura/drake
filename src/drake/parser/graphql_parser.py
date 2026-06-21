import logging
from pathlib import Path
from drake.core.models import ContractA, EndpointContract

logger = logging.getLogger(__name__)

class GraphQLParser:
    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def parse_and_flatten(self) -> ContractA:
        logger.info(f"Parsing GraphQL schema from {self.file_path}")
        endpoints = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Extremely simplistic parsing for demonstration
            # In a real scenario, use a proper GraphQL parser like graphql-core
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("type Query {") or line.startswith("type Mutation {"):
                    pass # Just identifying sections
                elif ":" in line and not line.startswith("type") and not line.startswith("}"):
                    # e.g., "getUser(id: ID!): User"
                    parts = line.split("(")
                    if len(parts) > 1:
                        name = parts[0].strip()
                        method = "QUERY"  # default assumption
                        
                        endpoints.append(
                            EndpointContract(
                                operation_id=f"GRAPHQL_{name}",
                                method=method,
                                url=f"/{name}",
                                required_params=[],
                                tags=["GraphQL"],
                                summary=f"GraphQL {name}",
                                protocol="GraphQL",
                                source_file=self.file_path.name
                            )
                        )
        except Exception as e:
            logger.error(f"Failed to parse GraphQL: {e}")
            
        if not endpoints:
            # Fallback mock if nothing found
            endpoints.append(
                EndpointContract(
                    operation_id="GRAPHQL_mock",
                    method="QUERY",
                    url="/graphql_mock",
                    protocol="GraphQL",
                    source_file=self.file_path.name
                )
            )

        return ContractA(
            spec_title=f"GraphQL: {self.file_path.name}",
            spec_version="1.0",
            openapi_version="N/A",
            source_file=self.file_path.name,
            total_endpoints=len(endpoints),
            endpoints=endpoints
        )
