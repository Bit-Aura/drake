import os, glob

files = ['tests/test_nl_compiler.py', 'tests/test_microservice.py', 'tests/test_governance_api.py', 'tests/integration/test_compatibility_runtime.py']

for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    if content.startswith('import os\n'):
        content = content[10:]
        
    if 'import os' not in content:
        # insert import os after future
        content = content.replace('from __future__ import annotations', 'from __future__ import annotations\nimport os')
        
    with open(f, 'w') as file:
        file.write(content)
