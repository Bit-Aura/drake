import os
from pathlib import Path
from typing import Dict, Any, Tuple
from drake.cli.exceptions import DellCLIError

class ConfigCLIService:  # noqa: E302
    """Service for generating MCP client connection configurations."""

    def generate_claude_desktop_config(self, port: int) -> Tuple[Dict[str, Any], str]:
        """Generate Claude Desktop config and return the standard file path for instructions."""
        config = {
            "mcpServers": {
                "dell-drake": {
                    "command": "uv",
                    "args": [
                        "run",
                        "uvicorn",
                        "drake.proxy.server:app",
                        "--port",
                        str(port)
                    ],
                    "env": {
                        "DELL_EXECUTOR_TYPE": "httpx" # Default to mock for safety  # noqa: E261
                    }
                }
            }
        }

        # Determine standard path for OS
        if os.name == "nt": # Windows  # noqa: E261
            appdata = os.getenv("APPDATA", "")
            path = str(Path(appdata) / "Claude" / "claude_desktop_config.json")
        else: # macOS / Linux  # noqa: E261
            path = str(Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json")  # noqa: E501

        return config, path

    def generate_cursor_config(self, port: int) -> Tuple[Dict[str, Any], str]:
        """Generate Cursor config and return the standard file path."""
        # For Cursor, we can output SSE URL instead of command since it's just a proxy server
        config = {
            "mcpServers": {
                "dell-drake": {
                    "url": f"http://127.0.0.1:{port}/mcp/sse"
                }
            }
        }
        path = str(Path(".cursor") / "mcp.json")
        return config, path

    def generate_vscode_config(self, port: int) -> Tuple[Dict[str, Any], str]:
        """Generate VS Code config and return the standard file path."""
        config = {
            "mcpServers": {
                "dell-drake": {
                    "url": f"http://127.0.0.1:{port}/mcp/sse"
                }
            }
        }
        path = str(Path(".vscode") / "mcp.json")
        return config, path

    def write_config(self, config: Dict[str, Any], path_str: str) -> None:
        """Write the config to the specified path."""
        try:
            import json
            path = Path(path_str)
            path.parent.mkdir(parents=True, exist_ok=True)

            # If it exists, we might want to merge, but for now just overwrite/create
            existing_config = {}
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        existing_config = json.load(f)
                except Exception:
                    pass

            # Merge logic for mcpServers
            if "mcpServers" not in existing_config:
                existing_config["mcpServers"] = {}

            existing_config["mcpServers"].update(config.get("mcpServers", {}))

            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing_config, f, indent=2)

        except Exception as e:
            raise DellCLIError(
                title="Config Write Failed",
                cause=str(e),
                impact=f"Could not automatically write config to {path_str}.",
                action="Copy the JSON output and paste it manually into the file."
            )
