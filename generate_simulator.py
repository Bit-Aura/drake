import sqlite3
import json
import re
import os

def generate():
    # Ensure destination directory exists
    os.makedirs("tests/fixtures/real_world_specs", exist_ok=True)
    
    conn = sqlite3.connect('data/governance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT url, method, operation_id, required_params FROM endpoint_steps")
    rows = cursor.fetchall()

    paths = {}
    for url, method, operation_id, required_params in rows:
        if not url:
            continue
            
        method = method.lower()
        if url not in paths:
            paths[url] = {}
            
        # Parse path parameters from URL (e.g., {ChassisId})
        path_params = re.findall(r"\{([a-zA-Z0-9_]+)\}", url)
        parameters = []
        for p in path_params:
            parameters.append({
                "name": p,
                "in": "path",
                "required": True,
                "schema": {"type": "string"}
            })

        paths[url][method] = {
            "operationId": operation_id,
            "summary": f"Auto-generated simulator for {operation_id}",
            "parameters": parameters,
            "responses": {
                "200": {
                    "description": "Auto Simulator Response",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "Message": {"type": "string", "example": f"Simulated data for {operation_id}"},
                                    "Status": {"type": "string", "example": "OK"}
                                }
                            }
                        }
                    }
                }
            }
        }

    openapi = {
        "openapi": "3.0.1",
        "info": {
            "title": "Drake Auto-Generated Simulator Server",
            "version": "1.0.0"
        },
        "paths": paths
    }

    with open("tests/fixtures/real_world_specs/auto_simulator.json", "w") as f:
        json.dump(openapi, f, indent=2)

    print(f"Generated auto_simulator.json with {len(paths)} endpoints.")

if __name__ == '__main__':
    generate()
