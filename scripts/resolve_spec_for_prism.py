import yaml
import json
from pathlib import Path

def resolve_external_refs(obj):
    if isinstance(obj, dict):
        if "$ref" in obj and isinstance(obj["$ref"], str):
            ref = obj["$ref"]
            if not ref.startswith("#"):
                # External reference! Replace with a generic object schema
                return {"type": "object"}
        return {k: resolve_external_refs(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_external_refs(i) for i in obj]
    return obj

def main():              
    spec_path = Path("tests/fixtures/openapi-7.xx.yaml")
    output_path = Path("tests/fixtures/mock_spec.json")
    
    print(f"Loading {spec_path}...")
    with open(spec_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
        
    print("Resolving external references...")
    resolved = resolve_external_refs(spec)
    
    print(f"Writing to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2)
        
    print("Done!")

if __name__ == "__main__":
    main()
