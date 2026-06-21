import typer
from src.cli.theme import render_json, render_success, render_warning, render_panel
from rich.syntax import Syntax
import json

app = typer.Typer(help="Generate MCP Client Configurations")

def _handle_config_output(ctx: typer.Context, client_name: str, config: dict, path: str, write: bool, port: int) -> None:
    wrapper = ctx.obj
    
    if wrapper.context.json_output:
        # Just output the raw config payload
        render_json(config)
        return

    if write:
        wrapper.container.config_service.write_config(config, path)
        render_success(f"Successfully wrote {client_name} config to: {path}")
        render_warning(f"Make sure Drake server is running: drake server start --port {port}")
    else:
        # Output to console with instructions
        from src.cli.theme import console
        
        json_str = json.dumps(config, indent=2)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
        
        content = (
            f"[bold white]1. Copy the following JSON:[/bold white]\n"
        )
        
        console.print(render_panel(content, title=f"[{client_name}] MCP Configuration"))
        console.print(syntax)
        console.print()
        
        instructions = (
            f"[bold white]2. Paste into your configuration file:[/bold white]\n"
            f"   [cyan]{path}[/cyan]\n\n"
            f"[bold white]3. Ensure the Drake MCP server is running:[/bold white]\n"
            f"   [cyan]drake server start --port {port}[/cyan]"
        )
        console.print(render_panel(instructions, border_style="yellow"))

@app.command("claude-desktop")
def config_claude(
    ctx: typer.Context,
    port: int = typer.Option(8000, "--port", "-p", help="Port the Drake server is running on"),
    write: bool = typer.Option(False, "--write", "-w", help="Auto-write to the standard config path"),
) -> None:
    """Generate MCP configuration for Claude Desktop."""
    wrapper = ctx.obj
    config, path = wrapper.container.config_service.generate_claude_desktop_config(port)
    _handle_config_output(ctx, "Claude Desktop", config, path, write, port)

@app.command("cursor")
def config_cursor(
    ctx: typer.Context,
    port: int = typer.Option(8000, "--port", "-p", help="Port the Drake server is running on"),
    write: bool = typer.Option(False, "--write", "-w", help="Auto-write to .cursor/mcp.json"),
) -> None:
    """Generate MCP configuration for Cursor IDE."""
    wrapper = ctx.obj
    config, path = wrapper.container.config_service.generate_cursor_config(port)
    _handle_config_output(ctx, "Cursor", config, path, write, port)

@app.command("vscode")
def config_vscode(
    ctx: typer.Context,
    port: int = typer.Option(8000, "--port", "-p", help="Port the Drake server is running on"),
    write: bool = typer.Option(False, "--write", "-w", help="Auto-write to .vscode/mcp.json"),
) -> None:
    """Generate MCP configuration for VS Code."""
    wrapper = ctx.obj
    config, path = wrapper.container.config_service.generate_vscode_config(port)
    _handle_config_output(ctx, "VS Code", config, path, write, port)
