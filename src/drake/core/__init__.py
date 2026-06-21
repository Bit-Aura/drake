"""
Dell MCP — Core Package
========================
Exports shared Pydantic models, configuration, and exceptions.
"""

from drake.core.config import DEFAULT_CONFIG, ParserConfig
from drake.core.exceptions import (
    ContractSerializationError,
    DellMCPBaseError,
    ParserError,
    SpecFileNotFoundError,
    SpecParseError,
    UnsupportedSpecVersionError,
)
from drake.core.models import ContractA, EndpointContract, RequiredParameter

__all__ = [
    # Config
    "DEFAULT_CONFIG",
    "ParserConfig",
    # Exceptions
    "DellMCPBaseError",
    "ParserError",
    "SpecFileNotFoundError",
    "SpecParseError",
    "UnsupportedSpecVersionError",
    "ContractSerializationError",
    # Models
    "RequiredParameter",
    "EndpointContract",
    "ContractA",
]
