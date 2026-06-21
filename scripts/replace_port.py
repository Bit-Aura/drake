import os

replacements = {
    'scripts/interactive_agent.py': [
        ('http://localhost:8000/mcp/sse', 'http://127.0.0.1:8001/mcp/sse')
    ],
    'src/cli/services/diagnostics.py': [
        ('os.getenv("PORT", "8000")', 'os.getenv("PORT", "8001")'),
        ('http://localhost:{port}', 'http://127.0.0.1:{port}')
    ],
    'src/cli/services/system.py': [
        ('http://localhost:8000/api/v1/mcp/reload', 'http://127.0.0.1:8001/api/v1/mcp/reload')
    ],
    'src/cli/services/runtime.py': [
        ('os.getenv("PORT", "8000")', 'os.getenv("PORT", "8001")'),
        ('http://localhost:{port}', 'http://127.0.0.1:{port}')
    ],
    'src/cli/commands/server.py': [
        ('8000, "--port", "-p"', '8001, "--port", "-p"')
    ],
    'src/cli/commands/pipeline.py': [
        ('typer.Option(8000, "--port"', 'typer.Option(8001, "--port"')
    ],
    'src/cli/commands/config.py': [
        ('typer.Option(8000, "--port"', 'typer.Option(8001, "--port"')
    ],
    'docs/AGENT_CLI_GUIDE.md': [
        ('http://localhost:8000/mcp/sse', 'http://127.0.0.1:8001/mcp/sse')
    ],
    'scripts/verify_mcp_end_to_end.py': [
        ('http://localhost:8000/api/v1/mcp/reload', 'http://127.0.0.1:8001/api/v1/mcp/reload'),
        ('http://localhost:8000/mcp/sse', 'http://127.0.0.1:8001/mcp/sse')
    ],
    'docs/CLI_REFERENCE.md': [
        ('port 8000', 'port 8001'),
        ('http://localhost:8000', 'http://127.0.0.1:8001'),
        ('--port 8000', '--port 8001')
    ]
}

for filepath, reps in replacements.items():
    if not os.path.exists(filepath):
        print(f'Missing: {filepath}')
        continue
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    for old_s, new_s in reps:
        if old_s in content:
            content = content.replace(old_s, new_s)
            modified = True
            print(f'Replaced in {filepath}: {old_s} -> {new_s}')
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
